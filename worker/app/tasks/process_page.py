"""Single page processing task — can be used for re-processing individual pages."""

import asyncio
import logging
from functools import partial
from uuid import UUID

logger = logging.getLogger(__name__)

from ..pipeline.ocr_processor import OCRProcessor
from ..pipeline.pdf_splitter import PDFSplitter


async def process_page(ctx: dict, page_data: dict) -> dict:
    """Process a single PDF page: OCR → classify → store.

    Args:
        page_data: {manual_id, tenant_id, page_number, storage_key}
    """
    pool = ctx["pool"]
    s3 = ctx["s3"]
    bucket = ctx["bucket"]
    config = ctx["config"]

    manual_id = page_data["manual_id"]
    tenant_id = page_data["tenant_id"]
    page_number = page_data["page_number"]
    storage_key = page_data["storage_key"]

    # Download PDF
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        partial(s3.get_object, Bucket=bucket, Key=storage_key),
    )
    pdf_bytes = response["Body"].read()

    # OCR the specific page
    ocr = OCRProcessor(max_concurrent=1)
    result = await ocr.process_page(pdf_bytes, page_number)

    # Render page image
    splitter = PDFSplitter(dpi=config.PDF_DPI)
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    mat = fitz.Matrix(config.PDF_DPI / 72.0, config.PDF_DPI / 72.0)
    pix = doc[page_number].get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    doc.close()

    # Upload page image
    image_key = f"manuals/{tenant_id}/{manual_id}/pages/{page_number}.png"
    await loop.run_in_executor(
        None,
        partial(
            s3.put_object,
            Bucket=bucket,
            Key=image_key,
            Body=png_bytes,
            ContentType="image/png",
        ),
    )

    # Upsert page record
    async with pool.acquire() as conn:
        await conn.execute(
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
            """,
            UUID(manual_id),
            page_number,
            result["classification"],
            result["text"],
            image_key,
            result["has_table"],
            result["has_diagram"],
        )

    return {
        "status": "ok",
        "page_number": page_number,
        "classification": result["classification"],
        "text_length": len(result["text"]),
    }
