"""OCR processing — extracts text from PDF pages using PyMuPDF."""

import asyncio
import gc
import logging
import re
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Process, Queue

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

_EMPTY_RESULT = {
    "text": "",
    "has_table": False,
    "has_diagram": False,
    "classification": "text",
    "confidence": 0.0,
    "image_bytes": b"",
}


def _process_page_in_subprocess(result_queue: Queue, pdf_bytes: bytes, page_number: int, dpi: int):
    """Run in a subprocess so it can be hard-killed on timeout."""
    try:
        result = _process_single_page(pdf_bytes, page_number, dpi)
        result_queue.put(result)
    except Exception as e:
        result_queue.put({"error": str(e)})


def _process_single_page(pdf_bytes: bytes, page_number: int, dpi: int) -> dict:
    """Process one page: extract text, classify, render PNG."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_number >= len(doc):
        doc.close()
        return dict(_EMPTY_RESULT, page_number=page_number)

    page = doc[page_number]

    # Extract text
    text = page.get_text("text")

    # Detect tables (find_tables can hang on complex pages, use heuristic fallback)
    has_table = False
    try:
        if len(text) < 50_000:
            tables = page.find_tables()
            has_table = len(tables.tables) > 0
        else:
            has_table = bool(_TABLE_PATTERNS.search(text))
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


async def process_page_async(pdf_bytes: bytes, page_number: int, dpi: int = 150) -> dict:
    """Process a single page in a subprocess with hard-kill timeout.

    Uses a real subprocess so that if the page hangs (complex table detection,
    huge pixmap rendering), we can kill it — unlike threads which cannot be
    interrupted.

    Retry strategy: try at requested DPI, retry at 72 DPI, then placeholder.
    """
    loop = asyncio.get_event_loop()

    for attempt_dpi in [dpi, 72]:
        result = await _run_page_in_process(loop, pdf_bytes, page_number, attempt_dpi, timeout=90)
        if result is not None:
            return result
        logger.warning(
            "Page %d failed at %d DPI, %s",
            page_number,
            attempt_dpi,
            "retrying at 72 DPI" if attempt_dpi != 72 else "using placeholder",
        )

    # Both attempts failed — return placeholder
    logger.error("Page %d failed all attempts, inserting placeholder", page_number)
    return dict(_EMPTY_RESULT, page_number=page_number)


async def _run_page_in_process(loop, pdf_bytes: bytes, page_number: int, dpi: int, timeout: int):
    """Run page processing in a subprocess with a hard kill timeout.

    Returns the result dict on success, or None if the subprocess timed out / crashed.
    """
    q: Queue = Queue()
    proc = Process(target=_process_page_in_subprocess, args=(q, pdf_bytes, page_number, dpi))
    proc.start()

    try:
        # Poll the queue in a non-blocking way so we don't block the event loop
        result = await asyncio.wait_for(
            loop.run_in_executor(None, q.get, True, timeout),
            timeout=timeout + 5,
        )

        if isinstance(result, dict) and "error" in result and "text" not in result:
            logger.warning("Page %d errored at %d DPI: %s", page_number, dpi, result["error"])
            return None

        return result

    except (asyncio.TimeoutError, Exception) as e:
        logger.warning("Page %d timed out / crashed at %d DPI: %s", page_number, dpi, e)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)
        return None
    finally:
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)
        proc.close()
        q.close()


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
