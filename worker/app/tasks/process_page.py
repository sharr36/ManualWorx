"""Single page processing task."""


async def process_page(ctx: dict, page_data: dict) -> dict:
    """Process a single PDF page: OCR → classify → store.

    Args:
        page_data: {manual_id, page_number, image_bytes_key}
    """
    # TODO: Implement in Phase 1
    # 1. Download page image from storage
    # 2. Run OCR (extract text + tables)
    # 3. Classify page type (text, schematic, table, etc.)
    # 4. Store results in pages table
    # 5. Return page metadata
    return {"status": "not_implemented"}
