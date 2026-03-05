"""Unstructured.io self-hosted OCR provider."""

import asyncio
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

_TIMEOUT_SECONDS = 120  # hi_res can be slow


class UnstructuredProvider(OCRProvider):
    """OCR using a self-hosted Unstructured API instance."""

    def __init__(self, api_url: str, api_key: str = ""):
        if not api_url:
            raise ValueError("UNSTRUCTURED_API_URL is required")
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    async def _partition(
        self, pdf_bytes: bytes, page_number: int, strategy: str = "hi_res"
    ) -> list[dict]:
        """Call the Unstructured /general/v0/general endpoint."""
        headers = {}
        if self.api_key:
            headers["unstructured-api-key"] = self.api_key

        # Unstructured expects a file upload
        files = {
            "files": ("document.pdf", pdf_bytes, "application/pdf"),
        }
        data = {
            "strategy": strategy,
            "pdf_infer_table_structure": "true",
            "languages": '["eng"]',
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{self.api_url}/general/v0/general",
                files=files,
                data=data,
                headers=headers,
            )
            response.raise_for_status()
            elements = response.json()

        # Filter to requested page (Unstructured uses 1-based page numbers)
        target_page = page_number + 1
        return [
            el for el in elements
            if el.get("metadata", {}).get("page_number") == target_page
        ]

    async def extract_text(self, pdf_bytes: bytes, page_number: int) -> OCRResult:
        try:
            elements = await self._partition(pdf_bytes, page_number)
        except Exception:
            logger.exception("Unstructured OCR failed for page %d", page_number)
            return OCRResult(text="", confidence=0.0)

        texts = []
        for el in elements:
            text = el.get("text", "").strip()
            if text:
                texts.append(text)

        full_text = "\n\n".join(texts)
        confidence = 0.85 if full_text.strip() else 0.0
        return OCRResult(text=full_text, confidence=confidence)

    async def extract_tables(self, pdf_bytes: bytes, page_number: int) -> list[Table]:
        try:
            elements = await self._partition(pdf_bytes, page_number)
        except Exception:
            logger.exception("Unstructured table extraction failed for page %d", page_number)
            return []

        tables = []
        for el in elements:
            if el.get("type") != "Table":
                continue

            metadata = el.get("metadata", {})
            html_table = metadata.get("text_as_html", "")

            if html_table:
                table = self._parse_html_table(html_table)
                if table:
                    tables.append(table)

        return tables

    @staticmethod
    def _parse_html_table(html: str) -> Table | None:
        """Parse a simple HTML table into our Table format."""
        import re

        rows_raw = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
        if not rows_raw:
            return None

        headers: list[str] = []
        rows: list[TableRow] = []

        for i, row_html in enumerate(rows_raw):
            # Extract th or td cells
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
            elements = await self._partition(pdf_bytes, page_number)
        except Exception:
            logger.exception("Unstructured layout analysis failed for page %d", page_number)
            return LayoutResult(blocks=[], reading_order=[])

        type_map = {
            "Title": "heading",
            "Header": "heading",
            "NarrativeText": "paragraph",
            "ListItem": "list",
            "Table": "table",
            "Image": "figure",
            "FigureCaption": "paragraph",
        }

        blocks = []
        for el in elements:
            el_type = el.get("type", "")
            text = el.get("text", "").strip()
            if not text and el_type != "Image":
                continue

            block_type = type_map.get(el_type, "paragraph")

            bbox = None
            coords = el.get("metadata", {}).get("coordinates", {})
            if coords and coords.get("points"):
                points = coords["points"]
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                bbox = BoundingBox(
                    x=min(xs), y=min(ys),
                    width=max(xs) - min(xs), height=max(ys) - min(ys),
                )

            blocks.append(LayoutBlock(
                text=text or "[image]",
                block_type=block_type,
                bbox=bbox,
            ))

        return LayoutResult(blocks=blocks, reading_order=list(range(len(blocks))))
