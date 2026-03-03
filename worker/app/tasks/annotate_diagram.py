"""Diagram annotation task using Claude Vision."""


async def annotate_diagram(ctx: dict, page_id: str) -> dict:
    """Annotate a diagram page using Claude Vision API.

    Extracts component labels, connection flows, operating states,
    and generates structured annotation data.

    Args:
        page_id: The page to annotate.
    """
    # TODO: Implement in Phase 5
    # 1. Fetch page image from storage
    # 2. Send to Claude Vision with diagram annotation prompt
    # 3. Parse structured response (components, connections, states)
    # 4. Store annotation in diagram_annotations table
    # 5. Generate SVG overlay data
    return {"status": "not_implemented", "page_id": page_id}
