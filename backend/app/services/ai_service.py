"""AI reasoning service — Anthropic Claude integration (Phase 1)."""


class AIService:
    """Handles prompting Claude with retrieved context and generating responses."""

    async def generate_response(self, query_text, query_mode, context_pages, skill_level=None):
        raise NotImplementedError("Phase 1")

    async def generate_followup(self, query_text, prior_context, context_pages):
        raise NotImplementedError("Phase 1")

    async def analyze_diagram(self, image_bytes, diagram_type=None):
        raise NotImplementedError("Phase 5")

    async def generate_lesson(self, system_area, context_pages, depth="standard"):
        raise NotImplementedError("Phase 8")
