"""Manual ingestion orchestrator task."""

import asyncio
import json
import logging
import traceback
from functools import partial
from uuid import UUID

from ..pipeline.chunker import Chunker
from ..pipeline.embedder import Embedder
from ..pipeline.ocr_processor import OCRProcessor
from ..pipeline.pdf_splitter import PDFSplitter

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


async def ingest_manual(ctx: dict, manual_id: str, tenant_id: str) -> dict:
    """Orchestrate the full manual ingestion pipeline.

    Steps:
    1. Update status to 'processing'
    2. Download PDF from storage
    3. Count pages, update total_pages
    4. For each page: OCR extract text → insert into pages table → upload page image
    5. Chunk all pages → insert chunks into chunks table
    6. Embed all chunks → upsert to Qdrant, update vector_id on chunks
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
        response = await loop.run_in_executor(
            None,
            partial(s3.get_object, Bucket=bucket, Key=storage_key),
        )
        pdf_bytes = response["Body"].read()

        # 3. Count pages and update total_pages
        splitter = PDFSplitter(dpi=config.PDF_DPI)
        page_count = splitter.get_page_count(pdf_bytes)

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE manuals SET total_pages = $1, updated_at = NOW() WHERE id = $2",
                page_count,
                UUID(manual_id),
            )

        # 4. Process each page: OCR + classify + store
        await _publish_progress(ctx, manual_id, "ocr", page=0, total=page_count)
        ocr = OCRProcessor(max_concurrent=config.MAX_CONCURRENT_PAGES)
        page_numbers = list(range(page_count))
        ocr_results = await ocr.process_batch(pdf_bytes, page_numbers)

        # Render page images and upload + insert page records
        page_images = splitter.split(pdf_bytes)
        pages_data = []  # For chunking: [{page_id, page_number, text, classification}]

        for idx, (ocr_result, page_img) in enumerate(zip(ocr_results, page_images)):
            pn = ocr_result["page_number"]
            await _publish_progress(ctx, manual_id, "ocr", page=idx + 1, total=page_count)

            # Upload page image to storage
            image_key = f"manuals/{tenant_id}/{manual_id}/pages/{pn}.png"
            await loop.run_in_executor(
                None,
                partial(
                    s3.put_object,
                    Bucket=bucket,
                    Key=image_key,
                    Body=page_img.image_bytes,
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
                    pn,
                    ocr_result["classification"],
                    ocr_result["text"],
                    image_key,
                    ocr_result["has_table"],
                    ocr_result["has_diagram"],
                )
                page_id = str(row["id"])

            pages_data.append({
                "page_id": page_id,
                "page_number": pn,
                "text": ocr_result["text"],
                "classification": ocr_result["classification"],
            })

        # 5. Chunk all pages
        await _publish_progress(ctx, manual_id, "chunking", page=page_count, total=page_count)
        chunker = Chunker(
            chunk_size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP
        )
        all_chunks = chunker.chunk_manual(pages_data)

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

        # 6. Embed all chunks and upsert to Qdrant
        await _publish_progress(ctx, manual_id, "embedding", page=page_count, total=page_count)
        if chunk_records:
            embedder = Embedder(
                qdrant=ctx["qdrant"],
                together_api_key=ctx["together_api_key"],
                batch_size=config.EMBED_BATCH_SIZE,
            )
            vector_results = await embedder.embed_and_store(
                chunks=chunk_records,
                collection=ctx["collection_name"],
                tenant_id=tenant_id,
                manual_id=manual_id,
            )

            # Update chunks with vector_id
            async with pool.acquire() as conn:
                for vr in vector_results:
                    await conn.execute(
                        "UPDATE chunks SET vector_id = $1 WHERE id = $2",
                        vr["vector_id"],
                        UUID(vr["chunk_id"]),
                    )

        # 7. Update status to 'ready'
        await _publish_progress(ctx, manual_id, "ready", page=page_count, total=page_count)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE manuals SET upload_status = 'ready', updated_at = NOW() WHERE id = $1",
                UUID(manual_id),
            )

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
        except Exception as db_err:
            logger.error("Failed to update manual %s status to 'failed': %s", manual_id, db_err)

        return {
            "status": "failed",
            "manual_id": manual_id,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
