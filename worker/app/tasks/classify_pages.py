"""Page classification task — refines heuristic classifications using Claude vision."""

import asyncio
import logging
from functools import partial
from uuid import UUID

logger = logging.getLogger(__name__)

from ..pipeline.page_classifier import PageClassifier


async def classify_pages(ctx: dict, manual_id: str, page_ids: list[str]) -> dict:
    """Classify pages by content type using Claude vision.

    Downloads page images from storage, runs the AI classifier,
    and updates the classification in the database. If the classification
    changes, also updates chunk payloads in Qdrant.

    Args:
        manual_id: Manual ID for storage path resolution.
        page_ids: List of page IDs to classify.
    """
    pool = ctx["pool"]
    s3 = ctx["s3"]
    bucket = ctx["bucket"]
    config = ctx["config"]

    if not config.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set — cannot run AI classification")
        return {"status": "error", "error": "ANTHROPIC_API_KEY not configured"}

    if not s3:
        logger.error("S3 client not initialized — cannot fetch page images for classification")
        return {"status": "error", "error": "S3 storage not configured"}

    classifier = PageClassifier(
        api_key=config.ANTHROPIC_API_KEY,
        model=config.CLASSIFICATION_MODEL,
    )

    loop = asyncio.get_event_loop()
    updated = 0

    # Fetch page records to get page numbers, text, and tenant context
    async with pool.acquire() as conn:
        pages = await conn.fetch(
            """
            SELECT p.id, p.page_number, p.classification, p.extracted_text, p.image_url,
                   m.tenant_id
            FROM pages p
            JOIN manuals m ON p.manual_id = m.id
            WHERE p.id = ANY($1::uuid[])
            ORDER BY p.page_number
            """,
            [UUID(pid) for pid in page_ids],
        )

    if not pages:
        return {"status": "no_pages", "count": 0}

    tenant_id = str(pages[0]["tenant_id"])

    # Build page data with images for batch classification
    page_data_list = []
    images_fetched = 0
    images_failed = 0
    for page in pages:
        image_key = page["image_url"]
        if not image_key:
            image_key = f"manuals/{tenant_id}/{manual_id}/pages/{page['page_number']}.png"

        try:
            response = await loop.run_in_executor(
                None,
                partial(s3.get_object, Bucket=bucket, Key=image_key),
            )
            image_bytes = response["Body"].read()
            if len(image_bytes) < 100:
                logger.warning("Page %d image suspiciously small (%d bytes): %s",
                               page["page_number"], len(image_bytes), image_key)
                images_failed += 1
            else:
                images_fetched += 1
        except Exception as e:
            logger.error("Failed to fetch page %d image from S3 key '%s': %s: %s",
                         page["page_number"], image_key, type(e).__name__, e)
            image_bytes = b""
            images_failed += 1

        page_data_list.append({
            "page_id": str(page["id"]),
            "page_number": page["page_number"],
            "old_classification": page["classification"],
            "text": page["extracted_text"] or "",
            "image_bytes": image_bytes,
        })

    logger.info("[%s] Fetched %d/%d page images (%d failed) for classification",
                manual_id[:8], images_fetched, len(pages), images_failed)

    # Classify pages in batches
    classify_input = [
        {"image_bytes": p["image_bytes"], "text": p["text"]}
        for p in page_data_list
    ]
    classifications = await classifier.classify_batch(
        classify_input, max_concurrent=config.MAX_CONCURRENT_PAGES
    )

    # Update database and Qdrant for changed classifications
    qdrant = ctx.get("qdrant")
    collection_name = ctx.get("collection_name", "manualworx_chunks")

    for page_data, new_classification in zip(page_data_list, classifications):
        if new_classification == page_data["old_classification"]:
            continue

        # Update page classification in DB
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE pages SET classification = $1 WHERE id = $2",
                new_classification,
                UUID(page_data["page_id"]),
            )

        # Update chunk payloads in Qdrant if classification changed
        if qdrant:
            try:
                async with pool.acquire() as conn:
                    chunk_rows = await conn.fetch(
                        "SELECT vector_id FROM chunks WHERE page_id = $1 AND vector_id IS NOT NULL",
                        UUID(page_data["page_id"]),
                    )

                for chunk_row in chunk_rows:
                    qdrant.set_payload(
                        collection_name=collection_name,
                        payload={"classification": new_classification},
                        points=[chunk_row["vector_id"]],
                    )
            except Exception as e:
                logger.warning("Failed to update Qdrant payload for page %s: %s", page_data["page_id"], e)

        updated += 1

    # Log classification distribution
    from collections import Counter
    old_dist = Counter(pd["old_classification"] for pd in page_data_list)
    new_dist = Counter(classifications)
    logger.info("[%s] Classification complete: %d/%d pages updated. Old: %s → New: %s",
                manual_id[:8], updated, len(page_ids), dict(old_dist), dict(new_dist))

    # Auto-enqueue annotation for newly-classified schematic pages
    schematic_types = {
        "hydraulic_schematic", "electrical_diagram",
        "wiring_harness", "diagnostic_flowchart",
        "parts_exploded_view", "general_illustration",
    }
    newly_schematic = [
        pd["page_id"] for pd, cls in zip(page_data_list, classifications)
        if cls in schematic_types and pd["old_classification"] not in schematic_types
    ]
    if newly_schematic:
        logger.info("[%s] Enqueuing annotation for %d newly-classified schematic pages",
                    manual_id[:8], len(newly_schematic))
        try:
            from arq.connections import ArqRedis
            arq_redis: ArqRedis | None = ctx.get("redis")
            if arq_redis:
                for pid in newly_schematic:
                    await arq_redis.enqueue_job("annotate_diagram", pid)
        except Exception as e:
            logger.warning("Failed to enqueue schematic annotation: %s", e)

    return {
        "status": "completed",
        "manual_id": manual_id,
        "total": len(page_ids),
        "updated": updated,
        "schematics_queued": len(newly_schematic),
    }
