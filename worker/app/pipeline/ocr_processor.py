"""OCR processing — extracts text from PDF pages using PyMuPDF."""

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import fitz

logger = logging.getLogger(__name__)

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

# Shared thread pool for CPU-bound fitz work
_executor = ThreadPoolExecutor(max_workers=2)


def _process_page_sync(pdf_bytes: bytes, page_number: int, dpi: int) -> dict:
    """Synchronous page processing: OCR + render to PNG in one pass.

    Returns dict with page_number, text, has_table, has_diagram, classification,
    confidence, and image_bytes (PNG).
    """
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
            "image_bytes": b"",
        }

    page = doc[page_number]

    # Extract text
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
    classification = _classify_page(text, has_table, has_diagram)
    confidence = 0.95 if text.strip() else 0.0

    # Render page image as PNG
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    image_bytes = pix.tobytes("png")

    doc.close()

    return {
        "page_number": page_number,
        "text": text,
        "has_table": has_table,
        "has_diagram": has_diagram,
        "classification": classification,
        "confidence": confidence,
        "image_bytes": image_bytes,
    }


async def process_page_async(pdf_bytes: bytes, page_number: int, dpi: int = 300) -> dict:
    """Process a single page in a thread pool (non-blocking)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor, _process_page_sync, pdf_bytes, page_number, dpi
    )


def _classify_page(text: str, has_table: bool, has_diagram: bool) -> str:
    """Classify a page based on content heuristics."""
    if not text.strip():
        if has_diagram:
            return "general_illustration"
        return "text"

    if has_table and _TABLE_PATTERNS.search(text):
        return "torque_spec_table"

    if _SCHEMATIC_KEYWORDS.search(text) and has_diagram:
        return "hydraulic_schematic"

    if _ELECTRICAL_KEYWORDS.search(text) and has_diagram:
        return "electrical_diagram"

    if re.search(r"(troubleshoot|diagnostic|fault|error\s*code)", text, re.I):
        if has_diagram:
            return "diagnostic_flowchart"

    if re.search(r"(part\s*no|part\s*number|item\s*\d|qty)", text, re.I):
        if has_diagram:
            return "parts_exploded_view"

    if _ELECTRICAL_KEYWORDS.search(text) and not has_diagram:
        return "wiring_harness"

    if has_diagram and _DIAGRAM_KEYWORDS.search(text):
        return "general_illustration"

    return "text"
