"""OCR processing — extracts text from PDF pages using PyMuPDF."""

import asyncio
import re


# Heuristic patterns for page classification
_TABLE_PATTERNS = re.compile(r"(\|\s*\w+\s*\|)|(\d+\s*[Nn]\.?[Mm])|(\d+\s*ft[\.\s-]?lb)")
_SCHEMATIC_KEYWORDS = re.compile(
    r"(hydraulic|schematic|circuit|valve|pump|cylinder|flow)", re.I
)
_ELECTRICAL_KEYWORDS = re.compile(
    r"(wiring|harness|connector|pin\s*\d|ECM|fuse|relay|voltage)", re.I
)
_DIAGRAM_KEYWORDS = re.compile(
    r"(fig\w*\s*\d|figure\s*\d|diagram|illustration|exploded|view)", re.I
)


class OCRProcessor:
    """Extract text from PDF pages using PyMuPDF (fitz) with batch concurrency."""

    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent

    async def process_page(self, pdf_bytes: bytes, page_number: int) -> dict:
        """Extract text from a single page and classify it.

        Returns:
            Dict with page_number, text, has_table, has_diagram, classification, confidence.
        """
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_number >= len(doc):
            doc.close()
            return {
                "page_number": page_number,
                "text": "",
                "has_table": False,
                "has_diagram": False,
                "classification": "text",
                "confidence": 0.0,
            }

        page = doc[page_number]
        text = page.get_text("text")

        # Detect tables
        has_table = False
        try:
            tables = page.find_tables()
            has_table = len(tables.tables) > 0
        except Exception:
            has_table = bool(_TABLE_PATTERNS.search(text))

        # Check for images (potential diagrams)
        image_count = len(page.get_images(full=True))
        has_diagram = image_count > 0

        # Classify the page
        classification = self._classify_page(text, has_table, has_diagram)

        # Confidence based on text extraction quality
        confidence = 0.95 if text.strip() else 0.0

        doc.close()

        return {
            "page_number": page_number,
            "text": text,
            "has_table": has_table,
            "has_diagram": has_diagram,
            "classification": classification,
            "confidence": confidence,
        }

    async def process_batch(
        self, pdf_bytes: bytes, page_numbers: list[int]
    ) -> list[dict]:
        """Process multiple pages with concurrency control."""
        sem = asyncio.Semaphore(self.max_concurrent)

        async def _process(pn: int) -> dict:
            async with sem:
                return await self.process_page(pdf_bytes, pn)

        tasks = [_process(pn) for pn in page_numbers]
        return await asyncio.gather(*tasks)

    def _classify_page(
        self, text: str, has_table: bool, has_diagram: bool
    ) -> str:
        """Classify a page based on content heuristics."""
        if not text.strip():
            if has_diagram:
                return "general_illustration"
            return "text"

        # Check for torque spec tables
        if has_table and _TABLE_PATTERNS.search(text):
            return "torque_spec_table"

        # Check for hydraulic schematics
        if _SCHEMATIC_KEYWORDS.search(text) and has_diagram:
            return "hydraulic_schematic"

        # Check for electrical diagrams
        if _ELECTRICAL_KEYWORDS.search(text) and has_diagram:
            return "electrical_diagram"

        # Check for diagnostic flowcharts
        if re.search(r"(troubleshoot|diagnostic|fault|error\s*code)", text, re.I):
            if has_diagram:
                return "diagnostic_flowchart"

        # Check for parts exploded views
        if re.search(r"(part\s*no|part\s*number|item\s*\d|qty)", text, re.I):
            if has_diagram:
                return "parts_exploded_view"

        # Check for wiring harness
        if _ELECTRICAL_KEYWORDS.search(text) and not has_diagram:
            return "wiring_harness"

        # General diagram
        if has_diagram and _DIAGRAM_KEYWORDS.search(text):
            return "general_illustration"

        return "text"
