"""PyMuPDF OCR provider — local PDF text extraction."""

import fitz  # PyMuPDF

from .base import (
    BoundingBox,
    LayoutBlock,
    LayoutResult,
    OCRProvider,
    OCRResult,
    Table,
    TableRow,
)


class PyMuPDFProvider(OCRProvider):
    """Extract text and tables from PDFs using PyMuPDF (fitz)."""

    async def extract_text(self, pdf_bytes: bytes, page_number: int) -> OCRResult:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_number >= len(doc):
            return OCRResult(text="", confidence=0.0)

        page = doc[page_number]
        text = page.get_text("text")
        doc.close()

        return OCRResult(
            text=text,
            confidence=0.95 if text.strip() else 0.0,
        )

    async def extract_tables(self, pdf_bytes: bytes, page_number: int) -> list[Table]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_number >= len(doc):
            return []

        page = doc[page_number]
        tables = []

        # Use PyMuPDF table detection
        try:
            found = page.find_tables()
            for table_data in found:
                extracted = table_data.extract()
                if not extracted or len(extracted) < 2:
                    continue

                headers = [str(cell) if cell else "" for cell in extracted[0]]
                rows = []
                for row_data in extracted[1:]:
                    cells = [str(cell) if cell else "" for cell in row_data]
                    rows.append(TableRow(cells=cells))

                tables.append(Table(headers=headers, rows=rows))
        except Exception:
            pass

        doc.close()
        return tables

    async def analyze_layout(self, pdf_bytes: bytes, page_number: int) -> LayoutResult:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_number >= len(doc):
            return LayoutResult(blocks=[], reading_order=[])

        page = doc[page_number]
        blocks_raw = page.get_text("dict")["blocks"]
        blocks = []

        for i, block in enumerate(blocks_raw):
            bbox = BoundingBox(
                x=block["bbox"][0],
                y=block["bbox"][1],
                width=block["bbox"][2] - block["bbox"][0],
                height=block["bbox"][3] - block["bbox"][1],
            )

            if block["type"] == 0:  # text block
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "")
                    text += "\n"

                block_type = "paragraph"
                if text.strip() and len(text.strip()) < 100:
                    # Heuristic: short text blocks are likely headings
                    first_span = (
                        block.get("lines", [{}])[0].get("spans", [{}])[0]
                        if block.get("lines")
                        else {}
                    )
                    if first_span.get("size", 0) > 14:
                        block_type = "heading"

                blocks.append(LayoutBlock(text=text.strip(), block_type=block_type, bbox=bbox))
            elif block["type"] == 1:  # image block
                blocks.append(LayoutBlock(text="[image]", block_type="figure", bbox=bbox))

        doc.close()

        # Reading order: top-to-bottom, left-to-right
        reading_order = list(range(len(blocks)))
        return LayoutResult(blocks=blocks, reading_order=reading_order)
