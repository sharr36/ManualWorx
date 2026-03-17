"""Re-OCR pages that have empty text, then rechunk + embed."""

import asyncio
import gc
import logging
from uuid import UUID

from ..pipeline.chunker import Chunker
from ..pipeline.embedder import Embedder
from ..pipeline.ocr_processor import process_page_async

logger = logging.getLogger(__name__)


async def reocr_empty_pages(ctx: dict, manual_id: str) -> dict:
    """Re-OCR only pages with empty/short text, update them, then rechunk + embed.

    Much faster than full reprocess when pages exist but OCR originally failed.
    """
    pool = ctx["pool"]
    config = ctx["config"]
    s3 = ctx["s3"]
    bucket = ctx["bucket"]

    logger.info("[%s] Starting re-OCR of empty pages", manual_id[:8])

    # 1. Get manual info
    async with pool.acquire() as conn:
        manual = await conn.fetchrow(
            "SELECT id, tenant_id FROM manuals WHERE id = $1", UUID(manual_id)
        )
    if not manual:
        return {"status": "error", "error": "Manual not found"}

    tenant_id = str(manual["tenant_id"])

    # 2. Download PDF
    loop = asyncio.get_event_loop()
    from functools import partial
    storage_key = f"manuals/{tenant_id}/{manual_id}/original.pdf"
    response = await loop.run_in_executor(
        None, partial(s3.get_object, Bucket=bucket, Key=storage_key)
    )
    pdf_bytes = response["Body"].read()

    # 3. Find pages with empty text
    async with pool.acquire() as conn:
        all_pages = await conn.fetch(
            """SELECT id, page_number, extracted_text, classification, has_diagram
               FROM pages WHERE manual_id = $1 ORDER BY page_number""",
            UUID(manual_id),
        )

    empty_pages = [p for p in all_pages if not (p["extracted_text"] or "").strip()]
    logger.info("[%s] Found %d empty pages out of %d total",
                manual_id[:8], len(empty_pages), len(all_pages))

    if not empty_pages:
        return {"status": "no_empty_pages", "manual_id": manual_id}

    # 4. Re-OCR empty pages
    reocr_count = 0
    for p in empty_pages:
        page_num = p["page_number"]
        result = await process_page_async(pdf_bytes, page_num, dpi=config.PDF_DPI)

        if result["text"].strip():
            reocr_count += 1
            # Update page in DB
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE pages SET extracted_text = $1, classification = $2,
                           has_table = $3, has_diagram = $4
                       WHERE id = $5""",
                    result["text"],
                    result["classification"],
                    result["has_table"],
                    result["has_diagram"],
                    p["id"],
                )

            # Update page image if we got one
            image_bytes = result.get("image_bytes")
            if image_bytes:
                image_key = f"manuals/{tenant_id}/{manual_id}/pages/{page_num}.png"
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

        del result
        gc.collect()

        if reocr_count % 50 == 0 and reocr_count > 0:
            logger.info("[%s] Re-OCR progress: %d/%d pages updated",
                        manual_id[:8], reocr_count, len(empty_pages))

    logger.info("[%s] Re-OCR complete: %d pages now have text", manual_id[:8], reocr_count)

    # 5. Now rechunk everything (delete old chunks, create new ones, embed)
    # Reload all pages with updated text
    async with pool.acquire() as conn:
        all_pages = await conn.fetch(
            """SELECT id, page_number, extracted_text, classification, has_diagram
               FROM pages WHERE manual_id = $1 ORDER BY page_number""",
            UUID(manual_id),
        )

    pages_data = [
        {
            "page_id": str(p["id"]),
            "page_number": p["page_number"],
            "text": p["extracted_text"] or "",
            "classification": p["classification"] or "text",
            "has_diagram": p["has_diagram"],
        }
        for p in all_pages
    ]

    # Delete old chunks
    async with pool.acquire() as conn:
        await conn.execute(
            """DELETE FROM chunks WHERE page_id IN (
                   SELECT id FROM pages WHERE manual_id = $1
               )""",
            UUID(manual_id),
        )

    # Chunk
    chunker = Chunker(chunk_size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP)
    all_chunks = chunker.chunk_manual(pages_data)
    logger.info("[%s] Created %d chunks", manual_id[:8], len(all_chunks))

    # Insert chunks
    chunk_records = []
    async with pool.acquire() as conn:
        for chunk in all_chunks:
            row = await conn.fetchrow(
                """INSERT INTO chunks (page_id, chunk_index, chunk_text, token_count)
                   VALUES ($1, $2, $3, $4) RETURNING id""",
                UUID(chunk["page_id"]),
                chunk["chunk_index"],
                chunk["chunk_text"],
                chunk["token_count"],
            )
            chunk["chunk_id"] = str(row["id"])
            chunk_records.append(chunk)

    # Embed
    embedded = 0
    if chunk_records and ctx.get("qdrant") is not None:
        try:
            embedder = Embedder(
                qdrant=ctx["qdrant"],
                together_api_key=ctx["together_api_key"],
                batch_size=config.EMBED_BATCH_SIZE,
            )
            vector_results = await asyncio.wait_for(
                embedder.embed_and_store(
                    chunks=chunk_records,
                    collection=ctx["collection_name"],
                    tenant_id=tenant_id,
                    manual_id=manual_id,
                ),
                timeout=600,
            )
            async with pool.acquire() as conn:
                for vr in vector_results:
                    await conn.execute(
                        "UPDATE chunks SET vector_id = $1 WHERE id = $2",
                        vr["vector_id"],
                        UUID(vr["chunk_id"]),
                    )
            embedded = len(vector_results)
        except Exception as e:
            logger.error("[%s] Embedding failed: %s", manual_id[:8], e)

    return {
        "status": "ok",
        "manual_id": manual_id,
        "total_pages": len(all_pages),
        "pages_reocrd": reocr_count,
        "chunks_created": len(chunk_records),
        "chunks_embedded": embedded,
    }
