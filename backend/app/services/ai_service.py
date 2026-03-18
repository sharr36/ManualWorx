"""AI reasoning service — Anthropic Claude integration."""

import json
import logging
import time
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

import anthropic

from ..config import settings
from manualworx_shared.constants import (
    CONFIDENCE_THRESHOLDS,
    ConfidenceLevel,
    SOURCE_WEIGHTS,
)

SYSTEM_PROMPT = """You are ManualWorx AI, a technical assistant for heavy equipment mechanics.
You answer questions using ONLY the provided service manual pages as context.

RULES:
- Always cite specific page numbers when referencing information: (p.XX)
- If the context doesn't contain enough information, say so honestly
- For torque specs, pressures, and measurements: quote exact values from the manual
- For safety-critical procedures: include any warnings or cautions from the manual
- Adapt your language complexity to the mechanic's skill level if specified
- Never fabricate specifications or procedures not found in the provided pages
- When multiple sources conflict, note the discrepancy

FORMAT:
- Use clear, concise technical language
- Break procedures into numbered steps when applicable
- Highlight safety warnings with ⚠️
- Include units with all measurements"""

QA_PROMPT = """Based on the following service manual pages, answer this question:

QUESTION: {query}

CONTEXT PAGES:
{context}

Provide a clear, accurate answer citing specific page numbers."""

TROUBLESHOOT_PROMPT = """Based on the following service manual pages, help troubleshoot this issue:

PROBLEM: {query}

CONTEXT PAGES:
{context}

Provide a systematic troubleshooting approach:
1. Most likely causes (ranked by probability)
2. Diagnostic steps to isolate the issue
3. Repair procedures for each potential cause
4. Relevant specifications and tolerances

Always cite page numbers for referenced procedures and specs."""

DIAGRAM_PROMPT = """Based on the following service manual pages and diagram annotations, explain the diagram/schematic related to this query:

QUESTION: {query}

CONTEXT PAGES:
{context}

{diagram_context}

Provide a clear explanation that:
1. Identifies the relevant components and their functions
2. Traces flow paths (hydraulic fluid, electrical current, etc.)
3. Explains operating states and how the system behaves
4. Notes any key specifications (pressures, voltages, etc.)
5. References specific components by their designators (V1, M2, etc.)

Always cite page numbers. Use component designators when available."""

PROCEDURE_PROMPT = """Based on the following service manual pages, provide a step-by-step service procedure for:

TASK: {query}

CONTEXT PAGES:
{context}

Format as a complete service procedure:

## Prerequisites
- Required tools and equipment
- Required parts and fluids
- Safety equipment needed

## Safety Precautions
⚠️ List ALL safety warnings and cautions

## Procedure Steps
1. [Detailed numbered steps]
   - Include torque specifications, measurements, and tolerances
   - Note any special techniques or sequence requirements

## Verification
- How to verify the procedure was completed correctly
- Expected readings, clearances, or test results

## Specifications
| Parameter | Value | Tolerance |
List all relevant specs in a table.

Always cite page numbers for each specification and procedure step."""

AUTO_DETECT_PROMPT = """Classify this mechanic's query into the best query mode.

Query: "{query}"

Choose ONE mode:
- "qa" — General question about specs, part numbers, capacities, locations
- "troubleshoot" — Problem description, symptom, fault code, malfunction
- "diagram" — Asks about schematics, wiring, hydraulic circuits, flow paths, component connections
- "procedure" — Asks how to do something: remove, install, adjust, replace, service, inspect

Return ONLY the mode word, nothing else."""


class AIService:
    """Handles prompting Claude with retrieved context and generating responses."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def generate_response(
        self,
        query_text: str,
        query_mode: str,
        context_chunks: list[dict],
        skill_level: str | None = None,
    ) -> dict:
        """Generate a response using Claude with retrieved context.

        Args:
            query_text: The user's question.
            query_mode: 'qa', 'troubleshoot', etc.
            context_chunks: Retrieved chunks with page metadata.
            skill_level: 'green', 'apprentice', 'journeyman'.

        Returns:
            {response_text, confidence_score, confidence_level, sources,
             input_tokens, output_tokens, model_used, latency_ms}
        """
        # Build context string from chunks
        context = self._build_context(context_chunks)

        # Select prompt template based on mode
        user_prompt = self._select_prompt(query_text, query_mode, context, context_chunks)

        # Add skill level instruction
        system = SYSTEM_PROMPT
        if skill_level == "green":
            system += "\n\nThe mechanic is a beginner. Use simple language, explain technical terms, and provide extra detail on safety."
        elif skill_level == "apprentice":
            system += "\n\nThe mechanic is an apprentice. Use standard technical language but explain complex concepts."

        # Call Claude
        start = time.monotonic()
        response = await self.client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        response_text = response.content[0].text

        # Calculate confidence
        confidence_score = self._calculate_confidence(context_chunks)
        confidence_level = self._get_confidence_level(confidence_score)

        # Build source citations
        sources = self._build_sources(context_chunks)

        return {
            "response_text": response_text,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "sources": sources,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model_used": settings.DEFAULT_MODEL,
            "latency_ms": latency_ms,
        }

    async def generate_followup(
        self,
        query_text: str,
        prior_context: str,
        context_chunks: list[dict],
    ) -> dict:
        """Generate a follow-up response with conversation history."""
        context = self._build_context(context_chunks)

        messages = [
            {
                "role": "user",
                "content": f"Previous context:\n{prior_context}\n\nFollow-up question: {query_text}\n\nAdditional context pages:\n{context}",
            }
        ]

        start = time.monotonic()
        response = await self.client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        confidence_score = self._calculate_confidence(context_chunks)

        return {
            "response_text": response.content[0].text,
            "confidence_score": confidence_score,
            "confidence_level": self._get_confidence_level(confidence_score),
            "sources": self._build_sources(context_chunks),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model_used": settings.DEFAULT_MODEL,
            "latency_ms": latency_ms,
        }

    async def generate_response_stream(
        self,
        query_text: str,
        query_mode: str,
        context_chunks: list[dict],
        skill_level: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token as SSE events.

        Yields SSE-formatted strings:
          data: {"type": "token", "text": "..."}\n\n
          data: {"type": "done", "confidence_score": ..., "sources": [...]}\n\n
        """
        context = self._build_context(context_chunks)

        # Select prompt template based on mode
        user_prompt = self._select_prompt(query_text, query_mode, context, context_chunks)

        system = SYSTEM_PROMPT
        if skill_level == "green":
            system += "\n\nThe mechanic is a beginner. Use simple language, explain technical terms, and provide extra detail on safety."
        elif skill_level == "apprentice":
            system += "\n\nThe mechanic is an apprentice. Use standard technical language but explain complex concepts."

        start = time.monotonic()
        full_text = ""
        input_tokens = 0
        output_tokens = 0

        async with self.client.messages.stream(
            model=settings.DEFAULT_MODEL,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    text = event.delta.text
                    full_text += text
                    yield f"data: {json.dumps({'type': 'token', 'text': text})}\n\n"

            # Get final message for usage stats
            message = await stream.get_final_message()
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens

        latency_ms = int((time.monotonic() - start) * 1000)
        confidence_score = self._calculate_confidence(context_chunks)
        confidence_level = self._get_confidence_level(confidence_score)
        sources = self._build_sources(context_chunks)

        # Yield final event with metadata
        yield f"data: {json.dumps({'type': 'done', 'response_text': full_text, 'confidence_score': confidence_score, 'confidence_level': confidence_level, 'sources': sources, 'input_tokens': input_tokens, 'output_tokens': output_tokens, 'model_used': settings.DEFAULT_MODEL, 'latency_ms': latency_ms})}\n\n"

    async def rerank_passages(
        self,
        query: str,
        passages: list[dict],
    ) -> list[dict]:
        """Re-rank passages using Claude for relevance scoring.

        Returns passages with updated 'score' field.
        """
        if not passages:
            return []

        rerank_model = getattr(settings, "RERANK_MODEL", "claude-haiku-4-5-20251001")

        passage_text = ""
        for i, p in enumerate(passages):
            text = p.get("chunk_text", "")[:500]
            passage_text += f"\n[{i}] Page {p.get('page_number', '?')}: {text}\n"

        prompt = f"""Rate the relevance of each passage to the query on a scale of 0.0 to 1.0.
Return ONLY a JSON array of numbers, one per passage, in order.

Query: {query}

Passages:{passage_text}

Return format: [0.8, 0.3, 0.95, ...]"""

        try:
            response = await self.client.messages.create(
                model=rerank_model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            # Extract JSON array from response
            start_idx = text.find("[")
            end_idx = text.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                scores = json.loads(text[start_idx:end_idx])
                for i, score in enumerate(scores):
                    if i < len(passages):
                        passages[i]["score"] = float(score)
        except Exception as e:
            logger.warning("Reranking failed, keeping original scores: %s", e)

        passages.sort(key=lambda x: x.get("score", 0), reverse=True)
        return passages

    async def suggest_refinements(
        self,
        query_text: str,
        response_text: str,
        confidence_score: float,
        claims: list[dict],
    ) -> list[dict]:
        """Suggest query refinements when confidence is low.

        Returns a list of refinement suggestions with rationale.
        """
        if confidence_score >= 0.8 and not any(
            c.get("contradictions") for c in claims
        ):
            return []

        low_claims = [
            c for c in claims
            if c.get("confidence", 1.0) < 0.6 or c.get("contradictions")
        ]

        prompt = f"""A mechanic asked: "{query_text}"

The AI response had {len(claims)} claims. Overall confidence: {confidence_score:.0%}.
{len(low_claims)} claims had low confidence or contradictions.

Low-confidence claims:
{json.dumps([{"text": c["claim_text"], "confidence": c["confidence"], "type": c["claim_type"]} for c in low_claims[:5]], indent=2)}

Suggest 2-3 refined queries that would get more specific, higher-confidence answers.
Focus on: narrowing scope, specifying exact components, asking for specific spec types.

Return ONLY a JSON array:
[{{"query": "refined question text", "reason": "why this would help"}}]"""

        try:
            response = await self.client.messages.create(
                model=getattr(settings, "RERANK_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                suggestions = json.loads(text[start:end])
                return [
                    {"query": s.get("query", ""), "reason": s.get("reason", "")}
                    for s in suggestions[:3]
                ]
        except Exception as e:
            logger.warning("Refinement suggestion generation failed: %s", e)

        return []

    async def analyze_diagram(
        self,
        image_bytes: bytes,
        page_text: str = "",
        diagram_type: str | None = None,
    ) -> dict:
        """Analyze a diagram image using Claude Vision.

        Extracts components, connections, operating states, and generates
        structured annotation data for the interactive viewer.

        Returns:
            {diagram_type, components, connections, operating_states,
             component_count, connection_count, confidence_overall}
        """
        import base64

        image_b64 = base64.standard_b64encode(image_bytes).decode()

        type_hint = f"\nDiagram type hint: {diagram_type}" if diagram_type else ""
        text_hint = f"\nExtracted text from this page:\n{page_text[:2000]}" if page_text else ""

        prompt = f"""Analyze this technical diagram from a heavy equipment service manual.{type_hint}{text_hint}

You MUST identify every individual discrete component and trace every circuit/wire path.
Take your time — thoroughness is more important than speed.

Extract the following as JSON:

{{
  "diagram_type": "hydraulic_schematic" | "electrical" | "wiring",
  "components": [
    {{
      "id": "unique_id",
      "designator": "exact label from diagram (e.g. RY1, SW1, M3, K5, 24-19)",
      "name": "descriptive name",
      "type": "valve|pump|motor|cylinder|filter|accumulator|gauge|switch|relay|solenoid|sensor|connector|fuse|resistor|battery|alternator|starter|light|other",
      "bbox_pct": [x_pct, y_pct, width_pct, height_pct],
      "specs": {{"key": "value"}}
    }}
  ],
  "connections": [
    {{
      "from_id": "component_id",
      "to_id": "component_id",
      "line_type": "pressure|return|pilot|drain|charge|power_positive|ground_negative|signal_data|can_bus",
      "label": "wire number or line label if visible",
      "waypoints": [[x_pct, y_pct], [x_pct, y_pct]]
    }}
  ],
  "operating_states": [
    {{
      "id": "state_id",
      "name": "state name (e.g. Neutral, Extend, Retract, Key ON, Cranking)",
      "description": "what happens in this state",
      "active_components": ["component_ids that are active"],
      "flow_paths": [
        {{
          "line_type": "pressure|return|power_positive|ground_negative|etc",
          "path": ["component_id_1", "component_id_2", "..."]
        }}
      ]
    }}
  ],
  "confidence": 0.0 to 1.0
}}

CRITICAL RULES:
1. INDIVIDUAL COMPONENTS ONLY: Each component must be a single discrete device
   (one relay, one switch, one connector, one fuse, etc.).
   NEVER group multiple components into a single "section" or "area" entry.
   A "Power Distribution Section" is NOT a component — the individual relays,
   fuses, and switches within it ARE components.

2. TIGHT BOUNDING BOXES: bbox_pct must tightly wrap the component symbol only.
   Typical component bbox should be 2-8% of image width and 2-8% height.
   If a bbox exceeds 15% in either dimension, you are probably grouping — split it.

3. CIRCUIT TRACING with waypoints: For each connection, provide waypoints
   that trace the actual wire/line path as drawn on the diagram.
   Waypoints are [x_pct, y_pct] coordinates (0-100) along the path.
   Include bends, junctions, and routing points. Minimum 2 waypoints per connection
   (start and end). For lines with bends, include intermediate points.

4. EVERY wire and line visible on the diagram must be a connection entry.
   Include wire numbers/labels when visible (e.g. "000", "772", "864").

5. For electrical diagrams: trace power from battery through switches, relays,
   and loads to ground. Identify every wire by its number if labeled.

6. bbox_pct coordinates are percentages (0-100) of image width/height.
   [x, y] is top-left corner. [width, height] is size."""

        start = time.monotonic()
        response = await self.client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=16384,
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
        latency_ms = int((time.monotonic() - start) * 1000)

        text = response.content[0].text.strip()

        # Extract JSON from response
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1
        if start_idx < 0 or end_idx <= start_idx:
            return {
                "diagram_type": diagram_type or "hydraulic_schematic",
                "components": [],
                "connections": [],
                "operating_states": [],
                "component_count": 0,
                "connection_count": 0,
                "confidence_overall": 0.0,
                "model_used": settings.DEFAULT_MODEL,
                "latency_ms": latency_ms,
            }

        result = json.loads(text[start_idx:end_idx])

        components = result.get("components", [])
        connections = result.get("connections", [])
        states = result.get("operating_states", [])

        return {
            "diagram_type": result.get("diagram_type", diagram_type or "hydraulic_schematic"),
            "components": components,
            "connections": connections,
            "operating_states": states,
            "component_count": len(components),
            "connection_count": len(connections),
            "confidence_overall": float(result.get("confidence", 0.5)),
            "model_used": settings.DEFAULT_MODEL,
            "latency_ms": latency_ms,
        }

    async def auto_detect_mode(self, query_text: str) -> str:
        """Use Claude to classify query intent into the best mode."""
        try:
            response = await self.client.messages.create(
                model=getattr(settings, "RERANK_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=16,
                messages=[
                    {
                        "role": "user",
                        "content": AUTO_DETECT_PROMPT.format(query=query_text),
                    }
                ],
            )
            mode = response.content[0].text.strip().lower().strip('"')
            if mode in ("qa", "troubleshoot", "diagram", "procedure"):
                return mode
        except Exception as e:
            logger.warning("Auto-detect mode failed, defaulting to QA: %s", e)
        return "qa"

    def _select_prompt(
        self,
        query_text: str,
        query_mode: str,
        context: str,
        context_chunks: list[dict],
    ) -> str:
        """Select the appropriate prompt template based on query mode."""
        if query_mode == "troubleshoot":
            return TROUBLESHOOT_PROMPT.format(query=query_text, context=context)
        elif query_mode == "diagram":
            diagram_context = self._build_diagram_context(context_chunks)
            return DIAGRAM_PROMPT.format(
                query=query_text,
                context=context,
                diagram_context=diagram_context,
            )
        elif query_mode == "procedure":
            return PROCEDURE_PROMPT.format(query=query_text, context=context)
        else:
            return QA_PROMPT.format(query=query_text, context=context)

    def _build_diagram_context(self, chunks: list[dict]) -> str:
        """Build additional diagram context from annotation data in chunks."""
        diagram_sections = []
        for chunk in chunks:
            annotation = chunk.get("annotation_data")
            if not annotation:
                continue

            components = annotation.get("components", [])
            connections = annotation.get("connections", [])

            if components:
                comp_text = "Components on this diagram:\n"
                for c in components[:20]:
                    comp_text += f"  - {c.get('designator', '?')}: {c.get('name', 'unknown')} ({c.get('type', '')})"
                    specs = c.get("specs", {})
                    if specs:
                        spec_str = ", ".join(f"{k}={v}" for k, v in specs.items())
                        comp_text += f" [{spec_str}]"
                    comp_text += "\n"
                diagram_sections.append(comp_text)

            if connections:
                conn_text = "Connections:\n"
                for c in connections[:30]:
                    conn_text += f"  - {c.get('from_id', '?')} --[{c.get('line_type', '')}]--> {c.get('to_id', '?')}\n"
                diagram_sections.append(conn_text)

            states = chunk.get("operating_states") or annotation.get("operating_states", [])
            if states:
                state_text = "Operating states:\n"
                for s in states[:5]:
                    state_text += f"  - {s.get('name', '?')}: {s.get('description', '')}\n"
                diagram_sections.append(state_text)

        if diagram_sections:
            return "DIAGRAM ANNOTATIONS:\n" + "\n".join(diagram_sections)
        return "No diagram annotations available for these pages."

    async def generate_lesson(self, system_area: str, context_pages: list[dict], depth: str = "standard") -> dict:
        """Generate an interactive lesson about a system area.

        Args:
            system_area: The system to teach about (e.g., "auxiliary hydraulics").
            context_pages: Retrieved manual pages as context chunks.
            depth: "full" (5-min deep dive), "quick" (60-sec overview), or "standard" (2-3 min).

        Returns:
            dict with lesson_text, key_concepts, diagrams_referenced, quiz_hooks.
        """
        context = self._build_context(context_pages)

        depth_instructions = {
            "full": "Create a thorough 5-minute lesson. Cover theory, component functions, fluid/signal flow paths, common failure modes, and maintenance tips. Use numbered sections.",
            "quick": "Create a concise 60-second overview. Hit only the critical points: what the system does, main components, and one key maintenance fact.",
            "standard": "Create a 2-3 minute lesson. Cover how the system works, key components and their roles, and important specifications.",
        }

        prompt = f"""You are ManualWorx AI teaching a mechanic about the {system_area} system.

CONTEXT PAGES:
{context}

TEACHING DEPTH: {depth}
{depth_instructions.get(depth, depth_instructions["standard"])}

Generate an engaging lesson that:
1. Starts with a practical hook ("Here's why this matters...")
2. Explains how the system works using the manual content
3. References specific pages and specs from the context
4. Highlights safety warnings with ⚠️
5. Ends with 2-3 key takeaways

Also provide:
- A JSON block at the end with this structure:
```json
{{
  "key_concepts": ["concept1", "concept2", ...],
  "diagrams_referenced": [page_numbers_that_have_diagrams],
  "quiz_hooks": ["potential quiz question 1", "potential quiz question 2", ...]
}}
```"""

        start = time.monotonic()
        response = await self.client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=2000 if depth == "full" else 1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        lesson_text = response.content[0].text
        latency = int((time.monotonic() - start) * 1000)

        # Try to extract the JSON metadata
        metadata = {"key_concepts": [], "diagrams_referenced": [], "quiz_hooks": []}
        try:
            json_start = lesson_text.rfind("```json")
            if json_start != -1:
                json_end = lesson_text.find("```", json_start + 7)
                json_str = lesson_text[json_start + 7:json_end].strip()
                metadata = json.loads(json_str)
                lesson_text = lesson_text[:json_start].strip()
        except (json.JSONDecodeError, ValueError):
            pass

        return {
            "lesson_text": lesson_text,
            "key_concepts": metadata.get("key_concepts", []),
            "diagrams_referenced": metadata.get("diagrams_referenced", []),
            "quiz_hooks": metadata.get("quiz_hooks", []),
            "depth": depth,
            "system_area": system_area,
            "model_used": settings.DEFAULT_MODEL,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "latency_ms": latency,
        }

    async def generate_quiz_questions(
        self, system_area: str, context_pages: list[dict], count: int = 5, difficulty: str = "green"
    ) -> list[dict]:
        """Generate quiz questions from manual content.

        Returns:
            List of question dicts with question_text, question_type, options, correct_answer, explanation.
        """
        context = self._build_context(context_pages)

        prompt = f"""Generate exactly {count} quiz questions about the {system_area} system for a mechanic at the "{difficulty}" skill level.

CONTEXT PAGES:
{context}

DIFFICULTY LEVELS:
- green: Basic identification, safety awareness, simple procedures
- apprentice: System theory, component interactions, spec interpretation
- journeyman: Advanced diagnostics, edge cases, cross-system effects

QUESTION TYPES to use (mix them):
- concept: Understanding how something works
- diagram_id: Identifying components in diagrams/schematics
- scenario: "What would happen if..." practical situations
- sequence: Correct order of procedure steps
- safety: Safety-critical knowledge

Return a JSON array:
```json
[
  {{
    "question_type": "concept|diagram_id|scenario|sequence|safety",
    "question_text": "The question",
    "options": {{"A": "option A", "B": "option B", "C": "option C", "D": "option D"}},
    "correct_answer": "A",
    "explanation": "Why this is correct, citing the manual page"
  }}
]
```

Return ONLY the JSON array, no other text."""

        response = await self.client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=2000,
            system="You generate technical quiz questions from service manual content. Return only valid JSON.",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            questions = json.loads(text)
            return questions if isinstance(questions, list) else []
        except json.JSONDecodeError:
            return []

    async def identify_system_area(self, problem_description: str) -> dict:
        """Use AI to identify which system area a problem relates to.

        Returns:
            dict with system_area, confidence, related_systems.
        """
        prompt = f"""A mechanic describes this problem:
"{problem_description}"

Identify the primary system area this relates to. Common areas:
engine, hydraulic, electrical, transmission, drivetrain, steering, brakes, cooling, fuel, exhaust, HVAC, attachment, frame, cab

Return JSON only:
```json
{{
  "system_area": "the primary system",
  "confidence": 0.0-1.0,
  "related_systems": ["other", "related", "systems"]
}}
```"""

        response = await self.client.messages.create(
            model=settings.RERANK_MODEL,  # Use Haiku for fast classification
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"system_area": "unknown", "confidence": 0.0, "related_systems": []}

    def _build_context(self, chunks: list[dict]) -> str:
        """Build a formatted context string from retrieved chunks."""
        if not chunks:
            return "No relevant pages found."

        sections = []
        seen_pages = set()

        for chunk in chunks:
            page_num = chunk.get("page_number", "?")
            classification = chunk.get("classification", "text")
            manual_title = chunk.get("manual_title", "Manual")

            # Use full page text for page-level chunks, chunk text otherwise
            text = chunk.get("chunk_text", "")

            header = f"--- Page {page_num} [{classification}] from \"{manual_title}\" ---"
            if page_num not in seen_pages:
                sections.append(f"{header}\n{text}")
                seen_pages.add(page_num)
            else:
                # Additional chunk from same page
                sections.append(f"[Additional context from page {page_num}]\n{text}")

        return "\n\n".join(sections)

    def _calculate_confidence(self, chunks: list[dict]) -> float:
        """Calculate confidence score based on source quality and relevance."""
        if not chunks:
            return 0.0

        scores = []
        for chunk in chunks:
            classification = chunk.get("classification", "text")
            vector_score = chunk.get("score", 0.5)

            # Map classification to source weight
            if classification in ("text",):
                source_weight = SOURCE_WEIGHTS["oem_manual_text"]
            elif classification in ("torque_spec_table",):
                source_weight = SOURCE_WEIGHTS["oem_manual_table"]
            elif classification in (
                "hydraulic_schematic",
                "electrical_diagram",
                "diagnostic_flowchart",
            ):
                source_weight = SOURCE_WEIGHTS["oem_diagram_clear"]
            else:
                source_weight = SOURCE_WEIGHTS.get("oem_manual_text", 0.85)

            # Combined score: source quality × vector relevance
            combined = source_weight * vector_score
            scores.append(combined)

        # Weighted average (top results count more)
        if not scores:
            return 0.0
        weighted = sum(s * (1.0 / (i + 1)) for i, s in enumerate(scores))
        total_weight = sum(1.0 / (i + 1) for i in range(len(scores)))
        return round(weighted / total_weight, 3)

    def _get_confidence_level(self, score: float) -> str:
        """Map score to confidence level."""
        for level, (low, high) in CONFIDENCE_THRESHOLDS.items():
            if low <= score <= high:
                return level
        return ConfidenceLevel.INFERENCE

    def _build_sources(self, chunks: list[dict]) -> list[dict]:
        """Build source citation list from chunks."""
        seen = set()
        sources = []

        for chunk in chunks:
            page_id = chunk.get("page_id")
            if page_id in seen:
                continue
            seen.add(page_id)

            text = chunk.get("chunk_text", "")
            preview = text[:200] + "..." if len(text) > 200 else text

            sources.append({
                "page_id": page_id,
                "page_number": chunk.get("page_number", 0),
                "classification": chunk.get("classification", "text"),
                "text_preview": preview,
                "relevance_score": chunk.get("score", 0.0),
                "manual_title": chunk.get("manual_title", ""),
            })

        return sources
