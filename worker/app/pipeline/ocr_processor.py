"""OCR processing — extracts text from PDF pages using PyMuPDF + Tesseract fallback."""

import asyncio
import gc
import io
import logging
import re
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Process, Queue

import fitz
from PIL import Image

logger = logging.getLogger(__name__)

# Heuristic patterns for page classification
_TABLE_PATTERNS = re.compile(r"(\|\s*\w+\s*\|)|(\d+\s*[Nn]\.?[Mm])|(\d+\s*ft[\.\s-]?lb)")

# Hydraulic-ONLY terms (removed "circuit" — shared with electrical)
_SCHEMATIC_KEYWORDS = re.compile(
    r"(hydraulic|valve|pump|cylinder|psi|bar\b|spool|manifold|reservoir|flow\s*control|relief\s*valve)", re.I
)
# Electrical-specific terms (expanded to catch connectors, pinouts, wire colors)
_ELECTRICAL_KEYWORDS = re.compile(
    r"(wir(?:ing|e)|harness|connector|pin\s*\d|ECM|fuse|relay|voltage|solenoid|"
    r"battery|alternator|ground|amp|ohm|resistor|switch|terminal|"
    r"color\s*code|(?:blk|red|wht|grn|blu|yel|org|brn|pnk|pur)\b)", re.I
)
# Shared terms that could be either — used for tiebreaking
_SHARED_SCHEMATIC = re.compile(
    r"(circuit|schematic|flow|diagram|pressure|sensor)", re.I
)
_DIAGRAM_KEYWORDS = re.compile(
    r"(fig\w*\.?\s*\d|figure\s*\d|diagram|illustration|exploded\s*view)", re.I
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

    # Detect oversized pages (foldout schematics) — cap rendering to avoid OOM/timeout
    page_w_in = page.rect.width / 72.0  # width in inches
    page_h_in = page.rect.height / 72.0  # height in inches
    page_area_sqin = page_w_in * page_h_in
    is_oversized = page_area_sqin > 200  # > ~14x14 inches (anything bigger than tabloid)

    # For oversized pages, reduce DPI to keep pixel count manageable
    # A 24x36" page at 150 DPI = 3600x5400 = 19MP → Tesseract will timeout
    # Cap at ~8MP (roughly 4000x2000) which is enough for readable rendering
    effective_dpi = dpi
    if is_oversized:
        max_pixels = 8_000_000
        pixels_at_dpi = (page_w_in * dpi) * (page_h_in * dpi)
        if pixels_at_dpi > max_pixels:
            import math
            scale = math.sqrt(max_pixels / pixels_at_dpi)
            effective_dpi = max(int(dpi * scale), 72)
            logger.info(
                "Page %d is oversized (%.0fx%.0f in, %.0f sq in) — reducing DPI from %d to %d",
                page_number, page_w_in, page_h_in, page_area_sqin, dpi, effective_dpi,
            )

    # Extract embedded text first
    text = page.get_text("text")
    is_scanned = False

    # Fallback to Tesseract OCR if embedded text is too short (scanned page)
    # Skip Tesseract for oversized pages — it will timeout on huge images
    # and schematics have labels that are too small for reliable OCR anyway
    if len(text.strip()) < 50 and not is_oversized:
        try:
            import pytesseract
            # Render at the requested DPI (reuse for OCR — avoids double render)
            ocr_zoom = effective_dpi / 72.0
            ocr_mat = fitz.Matrix(ocr_zoom, ocr_zoom)
            ocr_pix = page.get_pixmap(matrix=ocr_mat)
            img = Image.open(io.BytesIO(ocr_pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img, lang="eng")
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text
                is_scanned = True
            del ocr_pix, img
        except Exception as ocr_err:
            logger.warning("Page %d: Tesseract OCR failed: %s", page_number, ocr_err)

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
    # For scanned pages, the entire page is one big image — don't count that
    # as a diagram. Only detect diagrams on native-text PDF pages where
    # embedded images represent actual figures/schematics.
    has_diagram = False
    if not is_scanned:
        images = page.get_images(full=True)
        image_count = len(images)
        if image_count >= 3:
            has_diagram = True
        elif image_count >= 1:
            page_area = page.rect.width * page.rect.height
            for img in images:
                xref = img[0]
                try:
                    rects = page.get_image_rects(xref)
                    for r in rects:
                        if r.width * r.height > page_area * 0.15:
                            has_diagram = True
                            break
                except Exception:
                    pass
                if has_diagram:
                    break

    # For oversized pages with embedded text, classify as electrical/schematic
    # based on page dimensions alone — large foldout pages are almost always schematics
    if is_oversized and not is_scanned:
        # Use embedded text for classification (it's already extracted)
        has_diagram = True  # Oversized pages are schematics by definition

    # Classify the page
    classification = _classify_page(text, has_table, has_diagram)

    # If oversized page got classified as 'text', override — large foldouts
    # are schematics, not text pages.
    if is_oversized and classification == "text":
        el_hits = len(_ELECTRICAL_KEYWORDS.findall(text))
        hy_hits = len(_SCHEMATIC_KEYWORDS.findall(text))
        if el_hits > hy_hits:
            classification = "electrical_diagram"
        elif hy_hits > 0:
            classification = "hydraulic_schematic"
        else:
            classification = "electrical_diagram"  # large foldouts default to electrical
        logger.info("Page %d: oversized page reclassified as %s", page_number, classification)

    confidence = 0.95 if text.strip() else 0.0

    # Render page image as PNG (use effective DPI for oversized pages)
    render_dpi = effective_dpi if is_oversized else dpi
    zoom = render_dpi / 72.0
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

    for attempt_dpi, timeout in [(dpi, 180), (72, 120)]:
        result = await _run_page_in_process(loop, pdf_bytes, page_number, attempt_dpi, timeout=timeout)
        if result is not None:
            return result
        logger.warning(
            "Page %d failed at %d DPI (timeout=%ds), %s",
            page_number,
            attempt_dpi,
            timeout,
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


_PARTS_KEYWORDS = re.compile(
    r"(part\s*no|part\s*number|item\s*\d|qty|quantity|ref\.?\s*no)", re.I
)


def _classify_page(text: str, has_table: bool, has_diagram: bool) -> str:
    """Classify a page based on content heuristics.

    For scanned pages, has_diagram will be False (entire page is one image).
    We compensate by using keyword density to detect schematics from OCR text.
    """
    text_stripped = text.strip()
    text_lower = text_stripped.lower()
    text_len = len(text_stripped)

    # Very little or no text — classify based on diagram presence
    if text_len < 20:
        if has_diagram:
            return "general_illustration"
        return "text"

    # Tables with torque/spec patterns
    if has_table and _TABLE_PATTERNS.search(text):
        return "torque_spec_table"

    # Count keyword matches for hydraulic and electrical (mutually exclusive terms)
    hydraulic_hits = len(_SCHEMATIC_KEYWORDS.findall(text))
    electrical_hits = len(_ELECTRICAL_KEYWORDS.findall(text))
    shared_hits = len(_SHARED_SCHEMATIC.findall(text))

    # Shared terms (circuit, schematic, diagram, pressure, sensor, flow)
    # add to BOTH counts for threshold detection, but don't shift the balance
    total_hydraulic = hydraulic_hits + shared_hits
    total_electrical = electrical_hits + shared_hits

    # --- Scanned-page schematic detection ---
    has_designators = bool(re.search(
        r"(?<![a-zA-Z])[A-Z]{1,3}\s*\d{1,3}(?!\d)", text
    ))  # matches V1, P2, M3, SOL1, etc.

    # Keyword density: how many specific keywords per 100 chars
    if text_len > 0:
        hydraulic_density = (hydraulic_hits / text_len) * 100
        electrical_density = (electrical_hits / text_len) * 100
    else:
        hydraulic_density = electrical_density = 0.0

    # --- Determine schematic type by comparing SPECIFIC (non-shared) hits ---
    # If electrical-specific terms > hydraulic-specific terms → electrical
    # This prevents connector/pinout pages from being misclassified as hydraulic
    def _pick_schematic_type() -> str:
        if electrical_hits > hydraulic_hits:
            return "electrical_diagram"
        if hydraulic_hits > electrical_hits:
            return "hydraulic_schematic"
        # Tie — look for stronger electrical signals
        if re.search(r"(connector|pin\s*\d|wire|harness|fuse|relay|terminal)", text, re.I):
            return "electrical_diagram"
        if re.search(r"(hydraulic|pump|cylinder|spool|manifold|reservoir)", text, re.I):
            return "hydraulic_schematic"
        return "electrical_diagram"  # default for ambiguous diagrams

    # Diagram pages with schematic keywords — compare both to pick correct type
    if has_diagram and (total_hydraulic > 0 or total_electrical > 0):
        return _pick_schematic_type()

    # Short text with strong keyword signal (native or scanned)
    if (total_hydraulic >= 3 or total_electrical >= 3) and text_len < 800:
        return _pick_schematic_type()

    # Scanned schematic detection (no has_diagram flag available)
    if not has_diagram and (hydraulic_hits >= 2 or electrical_hits >= 2):
        specific_hits = max(hydraulic_hits, electrical_hits)
        if (
            (specific_hits / max(text_len, 1)) * 100 > 0.3
            or (has_designators and specific_hits >= 2)
            or (text_len < 400 and specific_hits >= 2)
        ):
            return _pick_schematic_type()

    # Diagnostic flowcharts
    if re.search(r"(troubleshoot|diagnostic|fault|error\s*code)", text, re.I):
        if has_diagram:
            return "diagnostic_flowchart"
        # Text-heavy troubleshooting pages
        if re.search(r"(cause|remedy|solution|symptom|check)", text, re.I):
            return "diagnostic_flowchart"

    # Parts exploded views — pages with part numbers, item lists, qty columns
    if _PARTS_KEYWORDS.search(text):
        if has_diagram:
            return "parts_exploded_view"
        # Tables with part numbers are parts lists even without diagrams
        if has_table:
            return "parts_exploded_view"

    # Wiring harness — electrical terms without diagram (pinout tables, etc.)
    if _ELECTRICAL_KEYWORDS.search(text) and not has_diagram:
        return "wiring_harness"

    # Diagrams with figure references — use comparative approach
    if has_diagram and _DIAGRAM_KEYWORDS.search(text):
        if hydraulic_hits > 0 or electrical_hits > 0:
            return _pick_schematic_type()
        return "general_illustration"

    # Short text on diagram pages — likely a schematic with labels
    if has_diagram and text_len < 200:
        if hydraulic_hits > 0 or electrical_hits > 0:
            return _pick_schematic_type()
        return "general_illustration"

    # Last resort for scanned pages: very short text with designators
    if not has_diagram and text_len < 300 and has_designators:
        if hydraulic_hits > 0 or electrical_hits > 0:
            return _pick_schematic_type()
        return "general_illustration"

    return "text"
