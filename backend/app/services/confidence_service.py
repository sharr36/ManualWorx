"""Confidence scoring service — per-claim extraction, scoring, and attribution."""

import json
from uuid import UUID, uuid4

import anthropic
import asyncpg

from ..config import settings
from ..database import set_tenant_context


CLAIM_EXTRACTION_PROMPT = """Analyze the following AI response about heavy equipment service manuals.
Extract each distinct factual claim into a structured list.

RESPONSE TEXT:
{response_text}

SOURCE PAGES USED:
{source_summary}

For each claim, determine:
1. claim_text: The exact claim or fact stated
2. claim_type: One of "spec" (measurements, torque values, pressures), "description" (explanations), "procedure_step" (repair/maintenance steps), "warning" (safety warnings/cautions)
3. safety_critical: true if the claim relates to safety, torque specs, pressures, or procedures where errors could cause injury or equipment damage
4. source_pages: Array of page numbers that support this claim (empty if inferred)
5. confidence: 0.0-1.0 based on how well the source pages support this specific claim

Return ONLY a JSON array. Example:
[
  {{"claim_text": "Main relief valve torque is 45 N·m", "claim_type": "spec", "safety_critical": true, "source_pages": [42], "confidence": 0.95}},
  {{"claim_text": "Remove the hydraulic filter before draining", "claim_type": "procedure_step", "safety_critical": false, "source_pages": [15, 16], "confidence": 0.85}}
]"""

CONTRADICTION_CHECK_PROMPT = """Compare these claims extracted from a service manual AI response.
Identify any contradictions between claims, or between a claim and its source page text.

CLAIMS:
{claims_json}

SOURCE PAGE TEXTS:
{source_texts}

Return a JSON array of contradiction objects. If no contradictions, return [].
Each contradiction should have:
- claim_indices: [index1, index2] of the conflicting claims (0-based)
- description: Brief explanation of the contradiction
- severity: "critical" (safety/spec conflict) or "minor" (description inconsistency)

Example: [{{"claim_indices": [0, 3], "description": "Claim 0 says 45 N·m but claim 3 says 50 N·m for the same bolt", "severity": "critical"}}]"""


class ConfidenceService:
    """Per-claim confidence scoring with source attribution and contradiction detection."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def score_response(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        query_id: UUID,
        response_text: str,
        sources: list[dict],
        context_chunks: list[dict] | None = None,
    ) -> dict:
        """Extract claims from a response and score each one.

        Args:
            pool: Database connection pool.
            tenant_id: Tenant UUID.
            query_id: Query this response belongs to.
            response_text: The AI-generated response text.
            sources: Source citation dicts from the AI service.
            context_chunks: Original context chunks for deeper attribution.

        Returns:
            {claims: [...], overall_confidence, contradiction_count, safety_claims}
        """
        # Build source summary for the extraction prompt
        source_summary = self._build_source_summary(sources)

        # Extract claims using Claude
        claims = await self._extract_claims(response_text, source_summary)

        if not claims:
            return {
                "claims": [],
                "overall_confidence": 0.0,
                "contradiction_count": 0,
                "safety_claims": 0,
            }

        # Check for contradictions if we have source text
        contradictions = []
        if context_chunks:
            contradictions = await self._check_contradictions(claims, context_chunks)

        # Apply contradiction penalties
        for contradiction in contradictions:
            for idx in contradiction.get("claim_indices", []):
                if idx < len(claims):
                    claims[idx]["confidence"] = max(
                        claims[idx]["confidence"] * 0.5, 0.1
                    )
                    claims[idx]["contradictions"] = claims[idx].get("contradictions", [])
                    claims[idx]["contradictions"].append(contradiction["description"])

        # Determine corroboration (claim supported by 2+ source pages)
        for claim in claims:
            claim["corroborated"] = len(claim.get("source_pages", [])) >= 2

        # Store claims in database
        await self._store_claims(pool, tenant_id, query_id, claims)

        # Calculate aggregated confidence
        overall = self.aggregate_confidence(claims)

        safety_claims = sum(1 for c in claims if c.get("safety_critical"))

        return {
            "claims": claims,
            "overall_confidence": overall,
            "contradiction_count": len(contradictions),
            "safety_claims": safety_claims,
        }

    async def get_claim_breakdown(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        query_id: UUID,
    ) -> list[dict]:
        """Retrieve stored claim analysis for a query."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            rows = await conn.fetch(
                """
                SELECT id, claim_text, claim_type, safety_critical,
                       confidence_score, confidence_level, sources,
                       corroborated, contradictions
                FROM response_claims
                WHERE query_id = $1 AND tenant_id = $2
                ORDER BY confidence_score DESC
                """,
                query_id,
                tenant_id,
            )

        return [
            {
                "id": str(r["id"]),
                "claim_text": r["claim_text"],
                "claim_type": r["claim_type"],
                "safety_critical": r["safety_critical"],
                "confidence_score": float(r["confidence_score"]) if r["confidence_score"] else 0.0,
                "confidence_level": r["confidence_level"],
                "sources": r["sources"] if r["sources"] else [],
                "corroborated": r["corroborated"],
                "contradictions": r["contradictions"] if r["contradictions"] else [],
            }
            for r in rows
        ]

    def aggregate_confidence(self, claims: list[dict]) -> float:
        """Aggregate per-claim confidence into an overall score.

        Safety-critical claims are weighted 2x. Contradictions lower the score.
        """
        if not claims:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0

        for claim in claims:
            weight = 2.0 if claim.get("safety_critical") else 1.0
            score = claim.get("confidence", 0.5)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return round(weighted_sum / total_weight, 3)

    async def _extract_claims(
        self, response_text: str, source_summary: str
    ) -> list[dict]:
        """Use Claude to extract structured claims from a response."""
        prompt = CLAIM_EXTRACTION_PROMPT.format(
            response_text=response_text,
            source_summary=source_summary,
        )

        try:
            response = await self.client.messages.create(
                model=getattr(settings, "RERANK_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            # Extract JSON array
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                claims = json.loads(text[start:end])
                # Validate and normalize
                validated = []
                for c in claims:
                    validated.append({
                        "claim_text": str(c.get("claim_text", "")),
                        "claim_type": c.get("claim_type", "description"),
                        "safety_critical": bool(c.get("safety_critical", False)),
                        "source_pages": c.get("source_pages", []),
                        "confidence": max(0.0, min(1.0, float(c.get("confidence", 0.5)))),
                        "corroborated": False,
                        "contradictions": [],
                    })
                return validated
        except Exception:
            pass

        return []

    async def _check_contradictions(
        self, claims: list[dict], context_chunks: list[dict]
    ) -> list[dict]:
        """Check for contradictions between claims and/or source material."""
        if len(claims) < 2:
            return []

        claims_json = json.dumps(
            [{"index": i, "text": c["claim_text"], "type": c["claim_type"]}
             for i, c in enumerate(claims)],
            indent=2,
        )

        source_texts = "\n".join(
            f"Page {c.get('page_number', '?')}: {c.get('chunk_text', '')[:300]}"
            for c in context_chunks[:10]
        )

        prompt = CONTRADICTION_CHECK_PROMPT.format(
            claims_json=claims_json,
            source_texts=source_texts,
        )

        try:
            response = await self.client.messages.create(
                model=getattr(settings, "RERANK_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception:
            pass

        return []

    async def _store_claims(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        query_id: UUID,
        claims: list[dict],
    ) -> None:
        """Persist extracted claims to the response_claims table."""
        from manualworx_shared.constants import CONFIDENCE_THRESHOLDS, ConfidenceLevel

        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            for claim in claims:
                score = claim.get("confidence", 0.5)

                # Map to confidence level
                level = ConfidenceLevel.INFERENCE
                for lvl, (low, high) in CONFIDENCE_THRESHOLDS.items():
                    if low <= score <= high:
                        level = lvl
                        break

                await conn.execute(
                    """
                    INSERT INTO response_claims
                        (id, tenant_id, query_id, claim_text, claim_type,
                         safety_critical, confidence_score, confidence_level,
                         sources, corroborated, contradictions)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                    uuid4(),
                    tenant_id,
                    query_id,
                    claim["claim_text"],
                    claim["claim_type"],
                    claim.get("safety_critical", False),
                    score,
                    level,
                    json.dumps(claim.get("source_pages", [])),
                    claim.get("corroborated", False),
                    json.dumps(claim.get("contradictions", [])),
                )

    def _build_source_summary(self, sources: list[dict]) -> str:
        """Build a text summary of sources for the extraction prompt."""
        if not sources:
            return "No sources available."

        lines = []
        for s in sources:
            page = s.get("page_number", "?")
            cls = s.get("classification", "text")
            preview = s.get("text_preview", "")[:200]
            title = s.get("manual_title", "Manual")
            lines.append(f"Page {page} [{cls}] from \"{title}\": {preview}")

        return "\n".join(lines)
