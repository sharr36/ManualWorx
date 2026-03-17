"""Page classification — identifies content type of manual pages using Claude vision."""

import asyncio
import base64
import json
import logging

import anthropic

from manualworx_shared.constants import PageClassification

logger = logging.getLogger(__name__)


CLASSIFICATION_PROMPT = """You are classifying pages from a heavy equipment service manual. Classify this page into exactly ONE category.

Look at the IMAGE carefully — text alone is not sufficient. Pay special attention to schematic symbols, flow lines, and circuit diagrams.

CATEGORIES:
- "hydraulic_schematic" — Page contains a HYDRAULIC SYSTEM DIAGRAM with schematic symbols: flow lines, valve symbols, pump symbols, cylinders, reservoirs, pressure gauges, filters. These are engineering schematics showing fluid flow paths. Even if there is some text labeling components, if the PRIMARY content is a hydraulic circuit diagram, use this.
- "electrical_diagram" — Page contains an ELECTRICAL/WIRING DIAGRAM with circuit symbols: wires, connectors, relays, fuses, ECM pinouts, switches, resistors, ground symbols. Even with component labels/text, if it shows electrical circuits, use this.
- "wiring_harness" — Page shows WIRING HARNESS routing paths, connector pinout tables, or wire color/gauge charts.
- "diagnostic_flowchart" — Page shows a TROUBLESHOOTING FLOWCHART or diagnostic decision tree with yes/no branches, fault codes, or step-by-step diagnostic procedures in a flowchart format.
- "parts_exploded_view" — Page shows an EXPLODED PARTS VIEW: an assembly/disassembly diagram with numbered callouts pointing to individual parts, usually with a parts list.
- "torque_spec_table" — Page is dominated by a TABLE of torque specs, clearances, tolerances, pressures, or measurement values.
- "general_illustration" — Page is a FULL-PAGE photo, cross-section drawing, or cutaway illustration that does NOT fit the above categories. Must have minimal text.
- "text" — Page is PRIMARILY TEXT: procedures, instructions, descriptions, specifications written in paragraphs or numbered steps. Use this ONLY when the page has NO significant diagrams or schematics.

DECISION PRIORITY:
1. If you see schematic symbols (valves, pumps, circuit elements, flow arrows) → hydraulic_schematic or electrical_diagram
2. If you see a flowchart with decision branches → diagnostic_flowchart
3. If you see exploded parts with callout numbers → parts_exploded_view
4. If you see a data table filling most of the page → torque_spec_table
5. If you see wiring routes or connector tables → wiring_harness
6. If mostly a large image/photo with minimal text → general_illustration
7. Only if NONE of the above apply → text

EXTRACTED TEXT FROM THIS PAGE:
{page_text}

Respond with ONLY the classification label, nothing else."""

VALID_CLASSIFICATIONS = {c.value for c in PageClassification}


class PageClassifier:
    """Classifies pages using Claude vision for accurate content type detection.

    Falls back to heuristic classification if vision fails.
    """

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for AI page classification. "
                "Set it via environment variable or fly secrets."
            )
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._consecutive_failures = 0

    async def classify(self, page_image_bytes: bytes, page_text: str = "") -> str:
        """Classify a single page using Claude vision.

        Args:
            page_image_bytes: PNG image bytes of the page.
            page_text: Extracted text from OCR (provides additional context).

        Returns:
            Classification string from PageClassification enum.
        """
        if not page_image_bytes or len(page_image_bytes) < 100:
            logger.warning("Empty or invalid image bytes (%d bytes), using heuristic",
                           len(page_image_bytes) if page_image_bytes else 0)
            return self._heuristic_classify(page_text)

        try:
            image_b64 = base64.b64encode(page_image_bytes).decode("utf-8")
            prompt = CLASSIFICATION_PROMPT.format(
                page_text=page_text[:1000] if page_text else "(no text extracted)"
            )

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=50,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

            result = response.content[0].text.strip().lower()
            self._consecutive_failures = 0

            # Validate against known classifications
            if result in VALID_CLASSIFICATIONS:
                return result

            # Try fuzzy matching
            for valid in VALID_CLASSIFICATIONS:
                if valid in result:
                    return valid

            logger.warning("Claude returned unrecognized classification: %s", result)
            return self._heuristic_classify(page_text)

        except anthropic.AuthenticationError:
            logger.error("Anthropic API key is invalid — cannot classify pages")
            raise  # Don't silently fall back on auth errors
        except Exception as exc:
            self._consecutive_failures += 1
            logger.warning("Vision classification failed (%s: %s), using heuristic (failure #%d)",
                           type(exc).__name__, exc, self._consecutive_failures)
            if self._consecutive_failures >= 5:
                logger.error("5+ consecutive classification failures — likely a systemic issue")
            return self._heuristic_classify(page_text)

    async def classify_batch(
        self,
        pages: list[dict],
        max_concurrent: int = 4,
    ) -> list[str]:
        """Classify multiple pages concurrently with a semaphore.

        Args:
            pages: List of dicts with 'image_bytes' and 'text' keys.
            max_concurrent: Max parallel Claude calls.

        Returns:
            List of classification strings in the same order.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _classify_one(page: dict) -> str:
            async with semaphore:
                return await self.classify(
                    page_image_bytes=page["image_bytes"],
                    page_text=page.get("text", ""),
                )

        results = await asyncio.gather(
            *[_classify_one(p) for p in pages],
            return_exceptions=True,
        )

        return [
            r if isinstance(r, str) else PageClassification.TEXT
            for r in results
        ]

    def _heuristic_classify(self, text: str) -> str:
        """Fallback heuristic classification based on text content."""
        if not text or len(text.strip()) < 20:
            return PageClassification.GENERAL_ILLUSTRATION

        text_lower = text.lower()
        text_len = len(text.strip())
        lines = text.strip().split("\n")

        # Check for table patterns (multiple columns of numbers)
        table_lines = sum(
            1 for line in lines
            if line.count("\t") >= 2 or line.count("  ") >= 3
        )
        if table_lines > len(lines) * 0.4:
            if any(w in text_lower for w in ("torque", "n·m", "ft-lb", "nm", "lb-ft")):
                return PageClassification.TORQUE_SPEC_TABLE

        # Check for flowchart / troubleshooting indicators
        if any(w in text_lower for w in ("troubleshoot", "diagnostic", "fault", "error code")):
            return PageClassification.DIAGNOSTIC_FLOWCHART
        if any(w in text_lower for w in ("yes", "no", "check", "verify", "does")) and \
                text_lower.count("?") >= 2:
            return PageClassification.DIAGNOSTIC_FLOWCHART

        # Count keyword matches
        hydraulic_terms = ("hydraulic", "valve", "pump", "cylinder", "psi", "bar", "flow",
                          "schematic", "circuit")
        hydraulic_hits = sum(1 for t in hydraulic_terms if t in text_lower)

        electrical_terms = ("wire", "connector", "pin", "circuit", "voltage", "amp", "fuse",
                          "relay", "solenoid", "ECM")
        electrical_hits = sum(1 for t in electrical_terms if t in text_lower)

        # Hydraulic schematics — even 1-2 hits on short pages suggest a schematic
        if hydraulic_hits >= 2 or (hydraulic_hits >= 1 and text_len < 500):
            return PageClassification.HYDRAULIC_SCHEMATIC

        # Electrical diagrams
        if electrical_hits >= 2 or (electrical_hits >= 1 and text_len < 500):
            return PageClassification.ELECTRICAL_DIAGRAM

        # Check for parts list
        if any(w in text_lower for w in ("part number", "part no", "qty", "exploded",
                                          "item no", "ref no", "quantity")):
            return PageClassification.PARTS_EXPLODED_VIEW

        # Check for wiring harness
        if any(w in text_lower for w in ("harness", "pinout", "routing")):
            return PageClassification.WIRING_HARNESS

        return PageClassification.TEXT
