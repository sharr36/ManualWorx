"""Query orchestration service — ties retrieval and AI together."""

import json
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from ..config import settings
from ..database import set_tenant_context
from .ai_service import AIService
from .confidence_service import ConfidenceService
from .retrieval_service import RetrievalService


class QueryService:
    """Orchestrates retrieval, AI reasoning, and response generation."""

    def __init__(self):
        self.retrieval = RetrievalService()
        self.ai = AIService()
        self.confidence = ConfidenceService()

    async def create_query(
        self,
        pool: asyncpg.Pool,
        redis,
        tenant_id: UUID,
        query_text: str,
        query_mode: str,
        manual_ids: list[str] | None = None,
        skill_level: str | None = None,
        session_id: UUID | None = None,
    ) -> dict:
        """Execute a full query pipeline: retrieve → reason → respond.

        Returns:
            Full query response dict with sources and confidence.
        """
        start = time.monotonic()

        # 1. Retrieve relevant chunks (with re-ranking when enabled)
        if settings.RERANK_ENABLED:
            chunks = await self.retrieval.retrieve_with_rerank(
                pool, tenant_id, query_text, manual_ids, top_k=settings.MAX_PAGES_PER_QUERY
            )
        else:
            chunks = await self.retrieval.retrieve_chunks(
                pool, tenant_id, query_text, manual_ids, top_k=settings.MAX_PAGES_PER_QUERY
            )

        # 2. Generate AI response
        ai_result = await self.ai.generate_response(
            query_text=query_text,
            query_mode=query_mode,
            context_chunks=chunks,
            skill_level=skill_level,
        )

        total_latency = int((time.monotonic() - start) * 1000)

        # 3. Calculate cost estimate
        input_cost = ai_result["input_tokens"] * 0.003 / 1000  # Sonnet pricing
        output_cost = ai_result["output_tokens"] * 0.015 / 1000
        cost_estimate = round(input_cost + output_cost, 6)

        # Collect retrieved page IDs
        retrieved_page_ids = list({c["page_id"] for c in chunks})

        # Parse manual_ids to UUID array
        manual_uuid_array = None
        if manual_ids:
            manual_uuid_array = [UUID(mid) for mid in manual_ids]

        # 4. Store query in database
        query_id = uuid4()
        if not session_id:
            session_id = uuid4()

        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            await conn.execute(
                """
                INSERT INTO queries (id, tenant_id, session_id, query_text, query_mode,
                                     manual_ids, retrieved_page_ids, response_text,
                                     model_used, input_tokens, output_tokens,
                                     cost_estimate, latency_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                query_id,
                tenant_id,
                session_id,
                query_text,
                query_mode,
                manual_uuid_array,
                [UUID(pid) for pid in retrieved_page_ids],
                ai_result["response_text"],
                ai_result["model_used"],
                ai_result["input_tokens"],
                ai_result["output_tokens"],
                cost_estimate,
                total_latency,
            )

        # 5. Per-claim confidence scoring (async, non-blocking)
        claim_result = None
        try:
            claim_result = await self.confidence.score_response(
                pool=pool,
                tenant_id=tenant_id,
                query_id=query_id,
                response_text=ai_result["response_text"],
                sources=ai_result["sources"],
                context_chunks=chunks,
            )
        except Exception:
            pass  # Claim scoring is non-critical

        # Use aggregated claim confidence if available
        final_confidence = ai_result["confidence_score"]
        final_level = ai_result["confidence_level"]
        if claim_result and claim_result.get("claims"):
            final_confidence = claim_result["overall_confidence"]
            # Re-derive level from aggregated score
            final_level = self.ai._get_confidence_level(final_confidence)

        # 6. Query refinement suggestions (when confidence is low)
        refinements = []
        claims_list = claim_result.get("claims", []) if claim_result else []
        if final_confidence < 0.8 or (claim_result and claim_result.get("contradiction_count", 0) > 0):
            try:
                refinements = await self.ai.suggest_refinements(
                    query_text=query_text,
                    response_text=ai_result["response_text"],
                    confidence_score=final_confidence,
                    claims=claims_list,
                )
            except Exception:
                pass

        # 7. Increment usage counter
        if redis:
            month_key = datetime.now().strftime("%Y-%m")
            usage_key = f"usage:{tenant_id}:{month_key}:queries"
            try:
                await redis.incr(usage_key)
                await redis.expire(usage_key, 86400 * 35)  # 35 days TTL
            except Exception:
                pass

        return {
            "id": str(query_id),
            "session_id": str(session_id),
            "query_text": query_text,
            "query_mode": query_mode,
            "response_text": ai_result["response_text"],
            "confidence_score": final_confidence,
            "confidence_level": final_level,
            "sources": ai_result["sources"],
            "claims": claims_list,
            "contradiction_count": claim_result.get("contradiction_count", 0) if claim_result else 0,
            "safety_claims": claim_result.get("safety_claims", 0) if claim_result else 0,
            "refinements": refinements,
            "model_used": ai_result["model_used"],
            "input_tokens": ai_result["input_tokens"],
            "output_tokens": ai_result["output_tokens"],
            "cost_estimate": cost_estimate,
            "latency_ms": total_latency,
            "created_at": datetime.now().isoformat(),
        }

    async def create_query_stream(
        self,
        pool: asyncpg.Pool,
        redis,
        tenant_id: UUID,
        query_text: str,
        query_mode: str,
        manual_ids: list[str] | None = None,
        skill_level: str | None = None,
        session_id: UUID | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a query response as SSE events.

        Same retrieval pipeline as create_query(), but streams tokens
        via generate_response_stream(). After streaming completes,
        stores the full response in DB.
        """
        start = time.monotonic()

        # 1. Retrieve relevant chunks (with re-ranking when enabled)
        if settings.RERANK_ENABLED:
            chunks = await self.retrieval.retrieve_with_rerank(
                pool, tenant_id, query_text, manual_ids, top_k=settings.MAX_PAGES_PER_QUERY
            )
        else:
            chunks = await self.retrieval.retrieve_chunks(
                pool, tenant_id, query_text, manual_ids, top_k=settings.MAX_PAGES_PER_QUERY
            )

        # 2. Stream AI response, collecting the done event for DB storage
        done_data = None
        async for event in self.ai.generate_response_stream(
            query_text=query_text,
            query_mode=query_mode,
            context_chunks=chunks,
            skill_level=skill_level,
        ):
            yield event
            # Capture the done event payload for persistence
            if '"type": "done"' in event:
                try:
                    payload = json.loads(event.replace("data: ", "").strip())
                    done_data = payload
                except Exception:
                    pass

        if not done_data:
            return

        total_latency = int((time.monotonic() - start) * 1000)

        # 3. Store in database
        input_cost = done_data.get("input_tokens", 0) * 0.003 / 1000
        output_cost = done_data.get("output_tokens", 0) * 0.015 / 1000
        cost_estimate = round(input_cost + output_cost, 6)

        retrieved_page_ids = list({c["page_id"] for c in chunks})
        manual_uuid_array = [UUID(mid) for mid in manual_ids] if manual_ids else None

        query_id = uuid4()
        if not session_id:
            session_id = uuid4()

        try:
            async with pool.acquire() as conn:
                await set_tenant_context(conn, tenant_id)
                await conn.execute(
                    """
                    INSERT INTO queries (id, tenant_id, session_id, query_text, query_mode,
                                         manual_ids, retrieved_page_ids, response_text,
                                         model_used, input_tokens, output_tokens,
                                         cost_estimate, latency_ms)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """,
                    query_id,
                    tenant_id,
                    session_id,
                    query_text,
                    query_mode,
                    manual_uuid_array,
                    [UUID(pid) for pid in retrieved_page_ids],
                    done_data.get("response_text", ""),
                    done_data.get("model_used", settings.DEFAULT_MODEL),
                    done_data.get("input_tokens", 0),
                    done_data.get("output_tokens", 0),
                    cost_estimate,
                    total_latency,
                )
        except Exception:
            pass  # Don't fail the stream if DB write fails

        # 4. Per-claim scoring + refinement suggestions (post-stream)
        try:
            claim_result = await self.confidence.score_response(
                pool=pool,
                tenant_id=tenant_id,
                query_id=query_id,
                response_text=done_data.get("response_text", ""),
                sources=done_data.get("sources", []),
                context_chunks=chunks,
            )
            claims = claim_result.get("claims", [])

            refinements = []
            overall = claim_result.get("overall_confidence", 1.0)
            if overall < 0.8 or claim_result.get("contradiction_count", 0) > 0:
                refinements = await self.ai.suggest_refinements(
                    query_text=query_text,
                    response_text=done_data.get("response_text", ""),
                    confidence_score=overall,
                    claims=claims,
                )

            yield f"data: {json.dumps({'type': 'claims', 'claims': claims, 'overall_confidence': overall, 'contradiction_count': claim_result.get('contradiction_count', 0), 'safety_claims': claim_result.get('safety_claims', 0), 'refinements': refinements})}\n\n"
        except Exception:
            pass

        # 5. Increment usage counter
        if redis:
            month_key = datetime.now().strftime("%Y-%m")
            usage_key = f"usage:{tenant_id}:{month_key}:queries"
            try:
                await redis.incr(usage_key)
                await redis.expire(usage_key, 86400 * 35)
            except Exception:
                pass

    async def followup_query(
        self,
        pool: asyncpg.Pool,
        redis,
        tenant_id: UUID,
        query_id: UUID,
        query_text: str,
        skill_level: str | None = None,
    ) -> dict:
        """Submit a follow-up question in the same session context."""
        # Fetch the original query for context
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            original = await conn.fetchrow(
                """
                SELECT session_id, query_text, response_text, manual_ids, query_mode
                FROM queries WHERE id = $1 AND tenant_id = $2
                """,
                query_id,
                tenant_id,
            )

        if not original:
            raise ValueError("Original query not found")

        # Build prior context
        prior_context = f"Q: {original['query_text']}\nA: {original['response_text']}"

        # Get manual_ids from original query
        manual_ids = [str(m) for m in original["manual_ids"]] if original["manual_ids"] else None

        # Retrieve fresh context for the follow-up
        chunks = await self.retrieval.retrieve_chunks(
            pool, tenant_id, query_text, manual_ids, top_k=settings.MAX_PAGES_PER_QUERY
        )

        # Generate follow-up response
        ai_result = await self.ai.generate_followup(
            query_text=query_text,
            prior_context=prior_context,
            context_chunks=chunks,
        )

        # Store as new query linked to same session
        return await self.create_query(
            pool=pool,
            redis=redis,
            tenant_id=tenant_id,
            query_text=query_text,
            query_mode=original["query_mode"],
            manual_ids=manual_ids,
            skill_level=skill_level,
            session_id=original["session_id"],
        )

    async def get_query(
        self, pool: asyncpg.Pool, tenant_id: UUID, query_id: UUID
    ) -> dict | None:
        """Retrieve a query and its response."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            row = await conn.fetchrow(
                """
                SELECT id, tenant_id, session_id, query_text, query_mode,
                       manual_ids, retrieved_page_ids, response_text,
                       model_used, input_tokens, output_tokens,
                       cost_estimate, latency_ms, created_at
                FROM queries
                WHERE id = $1 AND tenant_id = $2
                """,
                query_id,
                tenant_id,
            )

        if not row:
            return None

        # Fetch source pages
        sources = []
        if row["retrieved_page_ids"]:
            async with pool.acquire() as conn:
                for pid in row["retrieved_page_ids"][:10]:
                    page = await conn.fetchrow(
                        """
                        SELECT p.id, p.page_number, p.classification,
                               LEFT(p.extracted_text, 200) as text_preview,
                               m.title as manual_title
                        FROM pages p
                        JOIN manuals m ON p.manual_id = m.id
                        WHERE p.id = $1
                        """,
                        pid,
                    )
                    if page:
                        sources.append({
                            "page_id": str(page["id"]),
                            "page_number": page["page_number"],
                            "classification": page["classification"],
                            "text_preview": page["text_preview"] or "",
                            "relevance_score": 0.0,
                            "manual_title": page["manual_title"],
                        })

        return {
            "id": str(row["id"]),
            "session_id": str(row["session_id"]) if row["session_id"] else None,
            "query_text": row["query_text"],
            "query_mode": row["query_mode"],
            "response_text": row["response_text"],
            "confidence_score": None,  # Not stored, computed at query time
            "sources": sources,
            "model_used": row["model_used"],
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "cost_estimate": float(row["cost_estimate"]) if row["cost_estimate"] else None,
            "latency_ms": row["latency_ms"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    async def list_queries(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """List recent queries for a tenant."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            rows = await conn.fetch(
                """
                SELECT id, query_text, query_mode, response_text,
                       model_used, latency_ms, created_at
                FROM queries
                WHERE tenant_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                tenant_id,
                limit,
                offset,
            )

        return [
            {
                "id": str(r["id"]),
                "query_text": r["query_text"],
                "query_mode": r["query_mode"],
                "response_preview": (r["response_text"] or "")[:200],
                "model_used": r["model_used"],
                "latency_ms": r["latency_ms"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
