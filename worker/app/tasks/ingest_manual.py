"""Manual ingestion orchestrator task."""

import asyncio
import json
import logging
import traceback
from functools import partial
from uuid import UUID

from ..pipeline.chunker import Chunker
from ..pipeline.embedder import Embedder
from ..pipeline.ocr_processor import process_page_async

logger = logging.getLogger(__name__)


async def _publish_progress(ctx: dict, manual_id: str, stage: str, page: int = 0, total: int = 0):
    """Publish ingestion progress to Redis pub/sub."""
    redis = ctx.get("redis")
    if not redis:
        return
    try:
        msg = json.dumps({"stage": stage, "page": page, "total": total, "manual_id": manual_id})
        await redis.publish(f"progress:{manual_id}", msg)
    except Exception as e:
        logger.warning("Failed to publish progress for manual %s: %s", manual_id, e)


def _get_page_count_sync(pdf_bytes: bytes) -> int:
    """Get page count synchronously (for thread pool)."""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    count = len(doc)
    doc.close()
    return count


async def ingest_manual(ctx: dict, manual_id: str, tenant_id: str) -> dict:
    """Orchestrate the full manual ingestion pipeline.

    Steps:
    1. Update status to 'processing'
    2. Download PDF from storage
    3. Count pages, update total_pages
    4. For each page: OCR + render → insert page → upload image (one at a time)
    5. Chunk all pages → insert chunks
    6. Embed all chunks → upsert to Qdrant
    7. Update status to 'ready' (or 'failed' on error)
    """
    pool = ctx["pool"]
    s3 = ctx["s3"]
    bucket = ctx["bucket"]
    config = ctx["config"]

    logger.info("Starting ingestion for manual %s (tenant %s)", manual_id, tenant_id)

    try:
        # 1. Update status to 'processing'
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE manuals SET upload_status = 'processing', updated_at = NOW() WHERE id = $1",
                UUID(manual_id),
            )

        # 2. Download PDF from storage
        await _publish_progress(ctx, manual_id, "downloading")
        storage_key = f"manuals/{tenant_id}/{manual_id}/original.pdf"
        loop = asyncio.get_event_loop()
        logger.info("[%s] Downloading PDF from storage: %s", manual_id[:8], storage_key)
        response = await loop.run_in_executor(
            None,
            partial(s3.get_object, Bucket=bucket, Key=storage_key),
        )
        pdf_bytes = response["Body"].read()
        logger.info("[%s] Downloaded PDF: %.1f MB", manual_id[:8], len(pdf_bytes) / 1_048_576)

        # 3. Count pages and update total_pages
        page_count = await loop.run_in_executor(None, _get_page_count_sync, pdf_bytes)
        logger.info("[%s] PDF has %d pages", manual_id[:8], page_count)

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE manuals SET total_pages = $1, updated_at = NOW() WHERE id = $2",
                page_count,
                UUID(manual_id),
            )

        # 4. Process each page: OCR + render + upload + insert (one at a time)
        await _publish_progress(ctx, manual_id, "ocr", page=0, total=page_count)
        pages_data = []

        for page_num in range(page_count):
            logger.info("[%s] Processing page %d/%d", manual_id[:8], page_num + 1, page_count)
            await _publish_progress(ctx, manual_id, "ocr", page=page_num + 1, total=page_count)

            # OCR + render in thread pool (non-blocking)
            result = await process_page_async(pdf_bytes, page_num, dpi=config.PDF_DPI)

            # Upload page image to storage
            image_key = f"manuals/{tenant_id}/{manual_id}/pages/{page_num}.png"
            image_bytes = result.pop("image_bytes")
            if image_bytes:
                await loop.run_in_executor(
                    None,
                    partial(
                        s3.put_object,
                        Bucket=bucket,
                        Key=image_key,
                        Body=image_bytes,
                        ContentType="image/png",
                    ),
                )

            # Insert page record
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO pages (manual_id, page_number, classification, extracted_text,
                                       image_url, has_table, has_diagram)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (manual_id, page_number) DO UPDATE
                        SET classification = EXCLUDED.classification,
                            extracted_text = EXCLUDED.extracted_text,
                            image_url = EXCLUDED.image_url,
                            has_table = EXCLUDED.has_table,
                            has_diagram = EXCLUDED.has_diagram
                    RETURNING id
                    """,
                    UUID(manual_id),
                    page_num,
                    result["classification"],
                    result["text"],
                    image_key,
                    result["has_table"],
                    result["has_diagram"],
                )
                page_id = str(row["id"])

            pages_data.append({
                "page_id": page_id,
                "page_number": page_num,
                "text": result["text"],
                "classification": result["classification"],
            })

            # Free memory immediately
            del image_bytes, result

        logger.info("[%s] All %d pages processed", manual_id[:8], page_count)

        # 5. Chunk all pages
        await _publish_progress(ctx, manual_id, "chunking", page=page_count, total=page_count)
        chunker = Chunker(
            chunk_size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP
        )
        all_chunks = chunker.chunk_manual(pages_data)
        logger.info("[%s] Created %d chunks", manual_id[:8], len(all_chunks))

        # Insert chunks into database
        chunk_records = []
        async with pool.acquire() as conn:
            for chunk in all_chunks:
                row = await conn.fetchrow(
                    """
                    INSERT INTO chunks (page_id, chunk_index, chunk_text, token_count)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    UUID(chunk["page_id"]),
                    chunk["chunk_index"],
                    chunk["chunk_text"],
                    chunk["token_count"],
                )
                chunk["chunk_id"] = str(row["id"])
                chunk_records.append(chunk)

        # 6. Embed all chunks and upsert to Qdrant (with retry + timeout)
        await _publish_progress(ctx, manual_id, "embedding", page=page_count, total=page_count)
        if chunk_records and ctx.get("qdrant") is not None:
            logger.info("[%s] Embedding %d chunks", manual_id[:8], len(chunk_records))
            embedder = Embedder(
                qdrant=ctx["qdrant"],
                together_api_key=ctx["together_api_key"],
                batch_size=config.EMBED_BATCH_SIZE,
            )
            vector_results = None
            for embed_attempt in range(1, 4):
                try:
                    vector_results = await asyncio.wait_for(
                        embedder.embed_and_store(
                            chunks=chunk_records,
                            collection=ctx["collection_name"],
                            tenant_id=tenant_id,
                            manual_id=manual_id,
                        ),
                        timeout=300,  # 5 minute max for embedding step
                    )
                    break
                except asyncio.TimeoutError:
                    logger.error(
                        "Embedding attempt %d/3 timed out for manual %s",
                        embed_attempt, manual_id,
                    )
                    if embed_attempt == 3:
                        raise RuntimeError(f"Embedding timed out after 3 attempts for manual {manual_id}")
                    await asyncio.sleep(5 * embed_attempt)
                except Exception as embed_err:
                    if embed_attempt == 3:
                        raise
                    delay = 5 * embed_attempt
                    logger.warning(
                        "Embedding attempt %d/3 failed for manual %s: %s. Retrying in %ds...",
                        embed_attempt, manual_id, embed_err, delay,
                    )
                    await asyncio.sleep(delay)

            # Update chunks with vector_id
            if vector_results:
                async with pool.acquire() as conn:
                    for vr in vector_results:
                        await conn.execute(
                            "UPDATE chunks SET vector_id = $1 WHERE id = $2",
                            vr["vector_id"],
                            UUID(vr["chunk_id"]),
                        )
            logger.info("[%s] Embedding complete", manual_id[:8])
        elif chunk_records:
            logger.warning("Skipping embedding for manual %s — Qdrant not available", manual_id)

        # 7. Update status to 'ready'
        await _publish_progress(ctx, manual_id, "ready", page=page_count, total=page_count)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE manuals SET upload_status = 'ready', updated_at = NOW() WHERE id = $1",
                UUID(manual_id),
            )

        logger.info("[%s] Ingestion complete: %d pages, %d chunks", manual_id[:8], page_count, len(chunk_records))

        # 8. Enqueue AI page classification (refines heuristic results in background)
        page_ids_for_classify = [p["page_id"] for p in pages_data]
        if page_ids_for_classify:
            try:
                from arq.connections import ArqRedis
                arq_redis: ArqRedis | None = ctx.get("redis")
                if arq_redis:
                    await arq_redis.enqueue_job(
                        "classify_pages", manual_id, page_ids_for_classify
                    )
            except Exception as e:
                logger.warning("Failed to enqueue classification job: %s", e)

        return {
            "status": "ready",
            "manual_id": manual_id,
            "pages": page_count,
            "chunks": len(chunk_records),
        }

    except Exception as e:
        logger.error("Ingestion failed for manual %s: %s", manual_id, e, exc_info=True)
        # Update status to 'failed'
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE manuals SET upload_status = 'failed', updated_at = NOW() WHERE id = $1",
                    UUID(manual_id),
                )
            await _publish_progress(ctx, manual_id, "failed")
        except Exception as db_err:
            logger.error("Failed to update manual %s status to 'failed': %s", manual_id, db_err)

        return {
            "status": "failed",
            "manual_id": manual_id,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
