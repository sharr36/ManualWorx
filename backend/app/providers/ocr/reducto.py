"""Reducto API OCR provider — high-quality document parsing service."""

import logging

import httpx

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

_TIMEOUT_SECONDS = 60


class ReductoProvider(OCRProvider):
    """OCR using the Reducto document parsing API."""

    def __init__(self, api_key: str, api_url: str = "https://platform.reducto.ai"):
        if not api_key:
            raise ValueError("REDUCTO_API_KEY is required")
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")

    async def _parse_document(self, pdf_bytes: bytes) -> list[dict]:
        """Upload and parse a document via Reducto's API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        # Upload the file
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            # Step 1: Upload
            upload_resp = await client.post(
                f"{self.api_url}/upload",
                headers=headers,
                files={"file": ("document.pdf", pdf_bytes, "application/pdf")},
            )
            upload_resp.raise_for_status()
            upload_data = upload_resp.json()
            document_url = upload_data.get("document_url") or upload_data.get("url", "")

            # Step 2: Parse
            parse_resp = await client.post(
                f"{self.api_url}/parse",
                headers=headers,
                json={
                    "document_url": document_url,
                    "advanced_options": {
                        "ocr_system": "highres",
                        "table_output_format": "html",
                    },
                },
            )
            parse_resp.raise_for_status()
            result = parse_resp.json()

        return result.get("result", {}).get("chunks", [])

    def _filter_page(self, chunks: list[dict], page_number: int) -> list[dict]:
        """Filter chunks to a specific page (0-based)."""
        target = page_number + 1  # Reducto uses 1-based pages
        return [
            c for c in chunks
            if c.get("metadata", {}).get("page_number") == target
            or c.get("page_number") == target
        ]

    async def extract_text(self, pdf_bytes: bytes, page_number: int) -> OCRResult:
        try:
            chunks = await self._parse_document(pdf_bytes)
            page_chunks = self._filter_page(chunks, page_number)
        except Exception:
            logger.exception("Reducto OCR failed for page %d", page_number)
            return OCRResult(text="", confidence=0.0)

        texts = []
        for chunk in page_chunks:
            content = chunk.get("content", "").strip()
            if content:
                texts.append(content)

        full_text = "\n\n".join(texts)
        confidence = 0.92 if full_text.strip() else 0.0
        return OCRResult(text=full_text, confidence=confidence)

    async def extract_tables(self, pdf_bytes: bytes, page_number: int) -> list[Table]:
        try:
            chunks = await self._parse_document(pdf_bytes)
            page_chunks = self._filter_page(chunks, page_number)
        except Exception:
            logger.exception("Reducto table extraction failed for page %d", page_number)
            return []

        tables = []
        for chunk in page_chunks:
            chunk_type = chunk.get("type", "")
            if chunk_type != "table":
                continue

            html = chunk.get("content", "")
            if html:
                table = self._parse_html_table(html)
                if table:
                    tables.append(table)

        return tables

    @staticmethod
    def _parse_html_table(html: str) -> Table | None:
        """Parse an HTML table into our Table format."""
        import re

        rows_raw = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
        if not rows_raw:
            return None

        headers: list[str] = []
        rows: list[TableRow] = []

        for i, row_html in enumerate(rows_raw):
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.DOTALL)
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]

            if i == 0:
                headers = cells
            else:
                rows.append(TableRow(cells=cells))

        if not headers:
            return None
        return Table(headers=headers, rows=rows)

    async def analyze_layout(self, pdf_bytes: bytes, page_number: int) -> LayoutResult:
        try:
            chunks = await self._parse_document(pdf_bytes)
            page_chunks = self._filter_page(chunks, page_number)
        except Exception:
            logger.exception("Reducto layout analysis failed for page %d", page_number)
            return LayoutResult(blocks=[], reading_order=[])

        type_map = {
            "title": "heading",
            "heading": "heading",
            "text": "paragraph",
            "list": "list",
            "table": "table",
            "figure": "figure",
            "image": "figure",
        }

        blocks = []
        for chunk in page_chunks:
            chunk_type = chunk.get("type", "text")
            content = chunk.get("content", "").strip()
            if not content and chunk_type not in ("figure", "image"):
                continue

            block_type = type_map.get(chunk_type, "paragraph")

            bbox = None
            bb = chunk.get("metadata", {}).get("bounding_box") or chunk.get("bounding_box")
            if bb:
                bbox = BoundingBox(
                    x=bb.get("x", 0), y=bb.get("y", 0),
                    width=bb.get("width", 0), height=bb.get("height", 0),
                )

            blocks.append(LayoutBlock(
                text=content or "[image]",
                block_type=block_type,
                bbox=bbox,
            ))

        return LayoutResult(blocks=blocks, reading_order=list(range(len(blocks))))
