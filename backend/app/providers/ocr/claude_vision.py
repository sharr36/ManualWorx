"""Claude Vision OCR provider — high-quality fallback for difficult pages."""

import asyncio
import base64
import io
import logging

import fitz  # PyMuPDF — render PDF pages to images

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

# Claude's optimal image size — larger images waste tokens and slow things down.
_MAX_DIMENSION = 1568
_TIMEOUT_SECONDS = 30
_RENDER_DPI = 200  # Good balance for Claude Vision (lower than Tesseract)


def _render_and_resize(pdf_bytes: bytes, page_number: int) -> bytes:
    """Render a PDF page to a resized JPEG for Claude Vision."""
    from PIL import Image

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_number >= len(doc):
        doc.close()
        raise ValueError(f"Page {page_number} out of range (document has {len(doc)} pages)")

    page = doc[page_number]
    zoom = _RENDER_DPI / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()

    # Resize if too large
    img = Image.open(io.BytesIO(img_bytes))
    w, h = img.size
    if max(w, h) > _MAX_DIMENSION:
        scale = _MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Convert to JPEG for smaller payload
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue()


class ClaudeVisionProvider(OCRProvider):
    """OCR using Claude Vision API with timeout and image resizing safeguards."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Claude Vision OCR")
        self.api_key = api_key
        self.model = model

    async def _call_vision(self, image_bytes: bytes, prompt: str) -> str:
        """Send an image to Claude Vision with a strict timeout."""
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        b64 = base64.b64encode(image_bytes).decode("utf-8")

        try:
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": b64,
                                    },
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                ),
                timeout=_TIMEOUT_SECONDS,
            )
            return response.content[0].text
        except asyncio.TimeoutError:
            logger.warning("Claude Vision timed out after %ds", _TIMEOUT_SECONDS)
            return ""
        except Exception:
            logger.exception("Claude Vision API call failed")
            return ""

    async def extract_text(self, pdf_bytes: bytes, page_number: int) -> OCRResult:
        loop = asyncio.get_running_loop()
        try:
            image_bytes = await loop.run_in_executor(
                None, _render_and_resize, pdf_bytes, page_number
            )
        except Exception:
            logger.exception("Failed to render page %d for Claude Vision", page_number)
            return OCRResult(text="", confidence=0.0)

        prompt = (
            "Extract ALL text from this scanned document page exactly as it appears. "
            "Preserve paragraph structure, headings, bullet points, and part numbers. "
            "Do not summarize or interpret — output the raw text only."
        )
        text = await self._call_vision(image_bytes, prompt)

        confidence = 0.9 if text.strip() else 0.0
        return OCRResult(text=text, confidence=confidence)

    async def extract_tables(self, pdf_bytes: bytes, page_number: int) -> list[Table]:
        loop = asyncio.get_running_loop()
        try:
            image_bytes = await loop.run_in_executor(
                None, _render_and_resize, pdf_bytes, page_number
            )
        except Exception:
            logger.exception("Failed to render page %d for Claude Vision tables", page_number)
            return []

        prompt = (
            "Extract all tables from this document page. For each table, output it in this "
            "exact format:\n"
            "TABLE_START\n"
            "HEADERS: col1 | col2 | col3\n"
            "ROW: val1 | val2 | val3\n"
            "ROW: val4 | val5 | val6\n"
            "TABLE_END\n"
            "If there are no tables, output: NO_TABLES"
        )
        response = await self._call_vision(image_bytes, prompt)

        if not response or "NO_TABLES" in response:
            return []

        tables = []
        for table_block in response.split("TABLE_START"):
            table_block = table_block.strip()
            if not table_block or "HEADERS:" not in table_block:
                continue

            lines = table_block.split("\n")
            headers: list[str] = []
            rows: list[TableRow] = []

            for line in lines:
                line = line.strip()
                if line.startswith("HEADERS:"):
                    headers = [h.strip() for h in line[8:].split("|")]
                elif line.startswith("ROW:"):
                    cells = [c.strip() for c in line[4:].split("|")]
                    rows.append(TableRow(cells=cells))

            if headers:
                tables.append(Table(headers=headers, rows=rows))

        return tables

    async def analyze_layout(self, pdf_bytes: bytes, page_number: int) -> LayoutResult:
        loop = asyncio.get_running_loop()
        try:
            image_bytes = await loop.run_in_executor(
                None, _render_and_resize, pdf_bytes, page_number
            )
        except Exception:
            logger.exception("Failed to render page %d for Claude Vision layout", page_number)
            return LayoutResult(blocks=[], reading_order=[])

        prompt = (
            "Analyze the layout of this document page. For each content block, output:\n"
            "BLOCK_TYPE: heading|paragraph|list|table|figure\n"
            "BLOCK_TEXT: <the text content>\n"
            "---\n"
            "List blocks in reading order."
        )
        response = await self._call_vision(image_bytes, prompt)

        if not response:
            return LayoutResult(blocks=[], reading_order=[])

        blocks = []
        for section in response.split("---"):
            section = section.strip()
            if not section:
                continue

            block_type = "paragraph"
            block_text = ""

            for line in section.split("\n"):
                line = line.strip()
                if line.startswith("BLOCK_TYPE:"):
                    bt = line[11:].strip().lower()
                    if bt in ("heading", "paragraph", "list", "table", "figure"):
                        block_type = bt
                elif line.startswith("BLOCK_TEXT:"):
                    block_text = line[11:].strip()

            if block_text:
                blocks.append(LayoutBlock(text=block_text, block_type=block_type))

        return LayoutResult(blocks=blocks, reading_order=list(range(len(blocks))))
