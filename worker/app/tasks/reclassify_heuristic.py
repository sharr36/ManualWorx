"""Re-run heuristic classification on all pages of a manual."""

import logging
from uuid import UUID

from ..pipeline.ocr_processor import _classify_page, _TABLE_PATTERNS

logger = logging.getLogger(__name__)


async def reclassify_heuristic(ctx: dict, manual_id: str) -> dict:
    """Re-run the heuristic page classifier on existing pages.

    For scanned pages (where extracted_text came from Tesseract),
    has_diagram is forced to False since the full-page scan image
    doesn't indicate an actual diagram.
    """
    pool = ctx["pool"]

    async with pool.acquire() as conn:
        pages = await conn.fetch(
            """SELECT p.id, p.page_number, p.extracted_text, p.classification,
                      p.has_table, p.has_diagram
               FROM pages p
               WHERE p.manual_id = $1
               ORDER BY p.page_number""",
            UUID(manual_id),
        )

    if not pages:
        return {"status": "no_pages", "manual_id": manual_id}

    updated = 0
    for p in pages:
        text = p["extracted_text"] or ""
        has_table = p["has_table"] or False

        # Detect if this was a scanned page: if the page has substantial text
        # but was classified as a schematic/diagram type, it's likely a
        # scanned text page that was misclassified.
        # More robust: check if has_diagram was set on a page with lots of text
        # (real diagram pages typically have very little text).
        has_diagram = p["has_diagram"] or False

        # For pages with significant text content (>200 chars), don't trust
        # has_diagram — scanned pages always have has_diagram=True because
        # the entire page is one big image.
        if has_diagram and len(text.strip()) > 200:
            has_diagram = False

        new_class = _classify_page(text, has_table, has_diagram)

        if new_class != p["classification"]:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE pages SET classification = $1, has_diagram = $2 WHERE id = $3",
                    new_class,
                    has_diagram,
                    p["id"],
                )
            updated += 1

    logger.info("[%s] Heuristic reclassification: %d/%d pages updated",
                manual_id[:8], updated, len(pages))

    return {
        "status": "ok",
        "manual_id": manual_id,
        "total_pages": len(pages),
        "updated": updated,
    }
