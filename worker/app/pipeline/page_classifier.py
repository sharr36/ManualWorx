"""Page classification — identifies content type of manual pages using Claude vision."""

import asyncio
import base64
import json
import logging

import anthropic

from manualworx_shared.constants import PageClassification

logger = logging.getLogger(__name__)


CLASSIFICATION_PROMPT = """You are classifying pages from a heavy equipment service manual. Classify this page into exactly ONE category.

Look at the IMAGE carefully — text alone is not sufficient. Pay special attention to schematic symbols, flow lines, circuit diagrams, and page layout.

CATEGORIES:
- "hydraulic_schematic" — HYDRAULIC SYSTEM DIAGRAM with ISO hydraulic symbols: directional control valves (rectangles with arrows/ports), pumps (circles with triangles), cylinders (rectangles with pistons), check valves, relief valves, flow control valves, reservoirs, filters, accumulators. Connected by lines representing pressure/return/pilot/drain lines. These show fluid flow paths through a hydraulic system.
- "electrical_diagram" — ELECTRICAL CIRCUIT/WIRING DIAGRAM showing electrical circuits with standard symbols: switches, relays, fuses, resistors, solenoids, motors, batteries, grounds, ECM/ECU connections. Lines represent wires, often labeled with wire numbers or colors. Shows how electrical components are connected in circuits.
- "wiring_harness" — WIRING HARNESS layout showing physical wire routing paths on the machine, connector pinout tables/charts, wire color codes, or splice locations. Distinguished from electrical_diagram by showing physical routing rather than circuit logic.
- "diagnostic_flowchart" — TROUBLESHOOTING FLOWCHART with decision diamonds (yes/no branches), fault code tables, or step-by-step diagnostic procedures arranged as a visual flow. Must have branching logic or decision trees.
- "parts_exploded_view" — EXPLODED PARTS DIAGRAM showing components pulled apart with numbered callout lines pointing to individual parts. Usually accompanied by a parts list with item numbers, part numbers, and descriptions.
- "torque_spec_table" — Page DOMINATED by a specifications TABLE: torque values, clearances, tolerances, pressures, capacities, or measurement data arranged in rows and columns. The table must be the primary content.
- "general_illustration" — FULL-PAGE photo, cross-section cutaway, location diagram, or machine overview illustration that does NOT contain schematic circuit symbols. Photos of actual components, location callouts on machine photos, or cross-section drawings go here.
- "text" — PRIMARILY TEXT content: written procedures, descriptions, maintenance instructions, or general information in paragraphs, numbered steps, or bullet points. Use ONLY when the page has NO significant diagrams, schematics, or illustrations.

KEY DISTINCTIONS:
- Hydraulic vs Electrical: Hydraulic schematics use ISO fluid power symbols (valve blocks, pump circles, cylinder rectangles). Electrical diagrams use circuit symbols (relay coils, switch contacts, fuse symbols, ground triangles).
- Electrical diagram vs Wiring harness: Electrical diagrams show circuit LOGIC (how components are electrically connected). Wiring harness shows PHYSICAL routing (where wires run on the machine) or connector pin assignments.
- If a page has BOTH text AND a diagram, classify by the diagram type — the diagram takes priority.
- Large foldout pages with dense circuit drawings are almost always hydraulic_schematic or electrical_diagram.

EXTRACTED TEXT FROM THIS PAGE (for context only — rely primarily on the IMAGE):
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
