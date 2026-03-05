"""Tesseract OCR provider with proper preprocessing for scanned documents."""

import asyncio
import io
import logging

import fitz  # PyMuPDF — used to render PDF pages to images

from .base import (
    BoundingBox,
    LayoutBlock,
    LayoutResult,
    OCRProvider,
    OCRResult,
    Table,
    TableRow,
)

logger = logging.getLogger(__name__)

# Target DPI for rendering — Tesseract needs 300+ for good results.
_RENDER_DPI = 300


def _render_page_to_image(pdf_bytes: bytes, page_number: int) -> bytes:
    """Render a PDF page to a high-DPI PNG image."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_number >= len(doc):
        doc.close()
        raise ValueError(f"Page {page_number} out of range (document has {len(doc)} pages)")

    page = doc[page_number]
    zoom = _RENDER_DPI / 72  # 72 DPI is the PDF default
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def _preprocess_and_ocr(img_bytes: bytes) -> tuple[str, float]:
    """Preprocess image and run Tesseract. Returns (text, confidence)."""
    # Lazy imports — only needed when Tesseract is actually used.
    from PIL import Image, ImageFilter
    import pytesseract

    img = Image.open(io.BytesIO(img_bytes))

    # Convert to grayscale
    img = img.convert("L")

    # Sharpen to improve OCR on slightly blurry scans
    img = img.filter(ImageFilter.SHARPEN)

    # Binarize with adaptive-like threshold (Otsu via Tesseract handles this,
    # but a simple threshold helps with very noisy scans)
    img = img.point(lambda x: 0 if x < 128 else 255, "1")

    # Run Tesseract with optimised config for technical documents
    custom_config = (
        "--oem 3 "  # LSTM + legacy engine
        "--psm 6 "  # Assume uniform block of text
        "-l eng "  # English
    )

    data = pytesseract.image_to_data(img, config=custom_config, output_type=pytesseract.Output.DICT)

    # Build text and compute average confidence (ignoring empty entries)
    words = []
    confidences = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if text:
            words.append(text)
            conf = float(data["conf"][i])
            if conf > 0:
                confidences.append(conf)

    full_text = " ".join(words)
    avg_confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

    return full_text, avg_confidence


def _extract_tables_sync(img_bytes: bytes) -> list[Table]:
    """Attempt table extraction from image using Tesseract TSV output."""
    from PIL import Image
    import pytesseract

    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    custom_config = "--oem 3 --psm 6 -l eng"

    data = pytesseract.image_to_data(img, config=custom_config, output_type=pytesseract.Output.DICT)

    # Group words by block_num to detect table-like structures.
    # This is a heuristic — Tesseract doesn't natively detect tables well.
    blocks: dict[int, list[str]] = {}
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if text:
            block = data["block_num"][i]
            blocks.setdefault(block, []).append(text)

    # Not enough structure to identify tables from Tesseract alone.
    return []


class TesseractProvider(OCRProvider):
    """OCR using Tesseract with PyMuPDF rendering and image preprocessing."""

    async def extract_text(self, pdf_bytes: bytes, page_number: int) -> OCRResult:
        loop = asyncio.get_running_loop()

        try:
            img_bytes = await loop.run_in_executor(
                None, _render_page_to_image, pdf_bytes, page_number
            )
            text, confidence = await loop.run_in_executor(
                None, _preprocess_and_ocr, img_bytes
            )
        except Exception:
            logger.exception("Tesseract OCR failed for page %d", page_number)
            return OCRResult(text="", confidence=0.0)

        return OCRResult(text=text, confidence=confidence)

    async def extract_tables(self, pdf_bytes: bytes, page_number: int) -> list[Table]:
        loop = asyncio.get_running_loop()
        try:
            img_bytes = await loop.run_in_executor(
                None, _render_page_to_image, pdf_bytes, page_number
            )
            return await loop.run_in_executor(None, _extract_tables_sync, img_bytes)
        except Exception:
            logger.exception("Tesseract table extraction failed for page %d", page_number)
            return []

    async def analyze_layout(self, pdf_bytes: bytes, page_number: int) -> LayoutResult:
        """Basic layout analysis using Tesseract block detection."""
        loop = asyncio.get_running_loop()

        try:
            img_bytes = await loop.run_in_executor(
                None, _render_page_to_image, pdf_bytes, page_number
            )
        except Exception:
            logger.exception("Tesseract layout analysis failed for page %d", page_number)
            return LayoutResult(blocks=[], reading_order=[])

        def _analyze(img_data: bytes) -> LayoutResult:
            from PIL import Image
            import pytesseract

            img = Image.open(io.BytesIO(img_data)).convert("L")
            custom_config = "--oem 3 --psm 6 -l eng"
            data = pytesseract.image_to_data(
                img, config=custom_config, output_type=pytesseract.Output.DICT
            )

            # Group by block
            block_texts: dict[int, list[str]] = {}
            block_bboxes: dict[int, list[tuple[int, int, int, int]]] = {}
            for i, text in enumerate(data["text"]):
                text = text.strip()
                if not text:
                    continue
                bn = data["block_num"][i]
                block_texts.setdefault(bn, []).append(text)
                block_bboxes.setdefault(bn, []).append(
                    (data["left"][i], data["top"][i], data["width"][i], data["height"][i])
                )

            blocks = []
            for bn in sorted(block_texts.keys()):
                combined = " ".join(block_texts[bn])
                bboxes = block_bboxes[bn]
                x = min(b[0] for b in bboxes)
                y = min(b[1] for b in bboxes)
                x2 = max(b[0] + b[2] for b in bboxes)
                y2 = max(b[1] + b[3] for b in bboxes)
                bbox = BoundingBox(x=x, y=y, width=x2 - x, height=y2 - y)
                block_type = "heading" if len(combined) < 100 else "paragraph"
                blocks.append(LayoutBlock(text=combined, block_type=block_type, bbox=bbox))

            return LayoutResult(blocks=blocks, reading_order=list(range(len(blocks))))

        return await loop.run_in_executor(None, _analyze, img_bytes)
