"""AI reasoning service — Anthropic Claude integration."""

import time

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

        # Select prompt template
        if query_mode == "troubleshoot":
            user_prompt = TROUBLESHOOT_PROMPT.format(query=query_text, context=context)
        else:
            user_prompt = QA_PROMPT.format(query=query_text, context=context)

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

    async def analyze_diagram(self, image_bytes, diagram_type=None):
        raise NotImplementedError("Phase 5")

    async def generate_lesson(self, system_area, context_pages, depth="standard"):
        raise NotImplementedError("Phase 8")

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
