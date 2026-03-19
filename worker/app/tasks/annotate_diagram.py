"""Diagram annotation task using Claude Vision."""

import base64
import json
import logging
import time

import anthropic

logger = logging.getLogger(__name__)


ANNOTATION_PROMPT = """Analyze this technical diagram from a heavy equipment service manual.
{type_hint}{text_hint}

Extract the following as JSON:

{{
  "diagram_type": "hydraulic_schematic" | "electrical" | "wiring",
  "components": [
    {{
      "id": "unique_id",
      "designator": "component label from diagram (e.g. V1, M2, S3)",
      "name": "descriptive name",
      "type": "valve|pump|motor|cylinder|filter|accumulator|gauge|switch|relay|solenoid|sensor|connector|fuse|resistor|other",
      "bbox_pct": [x_pct, y_pct, width_pct, height_pct],
      "specs": {{"key": "value"}}
    }}
  ],
  "connections": [
    {{
      "from_id": "component_id",
      "to_id": "component_id",
      "line_type": "pressure|return|pilot|drain|charge|power_positive|ground_negative|signal_data|can_bus",
      "label": "optional line label"
    }}
  ],
  "operating_states": [
    {{
      "id": "state_id",
      "name": "state name (e.g. Neutral, Extend, Retract)",
      "description": "what happens in this state",
      "active_components": ["component_ids that are active"],
      "flow_paths": [
        {{
          "line_type": "pressure|return|etc",
          "path": ["component_id_1", "component_id_2", "..."]
        }}
      ]
    }}
  ],
  "confidence": 0.0 to 1.0
}}

Important:
- bbox_pct coordinates are percentages (0-100) of image width/height
- Include ALL visible components and connections
- For hydraulic schematics: identify pressure, return, pilot, and drain lines
- For electrical: identify power, ground, signal, and CAN bus lines
- Generate realistic operating states based on the circuit design"""


async def annotate_diagram(ctx: dict, page_id: str) -> dict:
    """Annotate a diagram page using Claude Vision API.

    Extracts component labels, connection flows, operating states,
    and generates structured annotation data.
    """
    pool = ctx["pool"]
    s3 = ctx["s3"]
    bucket = ctx["bucket"]
    config = ctx["config"]

    # 1. Fetch page metadata
    async with pool.acquire() as conn:
        page = await conn.fetchrow(
            """SELECT p.id, p.manual_id, p.page_number, p.classification,
                      p.extracted_text, p.image_storage_key,
                      m.tenant_id
               FROM pages p
               JOIN manuals m ON m.id = p.manual_id
               WHERE p.id = $1""",
            page_id,
        )

    if not page:
        return {"status": "error", "detail": "Page not found"}

    # 2. Fetch page image from storage
    storage_key = page["image_storage_key"]
    if not storage_key:
        storage_key = f"manuals/{page['manual_id']}/pages/{page['page_number']}.png"

    try:
        obj = s3.get_object(Bucket=bucket, Key=storage_key)
        image_bytes = obj["Body"].read()
    except Exception as e:
        return {"status": "error", "detail": f"Failed to fetch image: {e}"}

    image_b64 = base64.standard_b64encode(image_bytes).decode()

    # 3. Build prompt hints
    classification = page["classification"] or ""
    type_hint = ""
    if "hydraulic" in classification:
        type_hint = "\nDiagram type hint: hydraulic_schematic"
    elif "electrical" in classification or "wiring" in classification:
        type_hint = "\nDiagram type hint: electrical"

    text_hint = ""
    if page["extracted_text"]:
        text_hint = f"\nExtracted text from this page:\n{page['extracted_text'][:2000]}"

    prompt = ANNOTATION_PROMPT.format(type_hint=type_hint, text_hint=text_hint)

    # 4. Call Claude Vision
    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

    start = time.monotonic()
    response = await client.messages.create(
        model=config.AI_MODEL,
        max_tokens=4096,
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

    # 5. Parse JSON response
    start_idx = text.find("{")
    end_idx = text.rfind("}") + 1
    if start_idx < 0 or end_idx <= start_idx:
        logger.warning("Failed to parse annotation JSON for page %s", page_id)
        return {"status": "error", "detail": "Failed to parse annotation response"}

    try:
        result = json.loads(text[start_idx:end_idx])
    except json.JSONDecodeError as e:
        logger.warning("Invalid annotation JSON for page %s: %s", page_id, e)
        return {"status": "error", "detail": "Invalid JSON in annotation response"}

    components = result.get("components", [])
    connections = result.get("connections", [])
    operating_states = result.get("operating_states", [])
    diagram_type = result.get("diagram_type", "hydraulic_schematic")
    confidence = float(result.get("confidence", 0.5))

    annotation_data = {
        "components": components,
        "connections": connections,
    }

    # 6. Store in diagram_annotations table
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO diagram_annotations
               (tenant_id, page_id, diagram_type, annotation_data,
                component_count, connection_count, operating_states,
                model_used, confidence_overall)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               ON CONFLICT (page_id)
               DO UPDATE SET
                 annotation_data = EXCLUDED.annotation_data,
                 component_count = EXCLUDED.component_count,
                 connection_count = EXCLUDED.connection_count,
                 operating_states = EXCLUDED.operating_states,
                 model_used = EXCLUDED.model_used,
                 confidence_overall = EXCLUDED.confidence_overall,
                 generated_at = NOW()
               RETURNING id""",
            str(page["tenant_id"]),
            page_id,
            diagram_type,
            json.dumps(annotation_data),
            len(components),
            len(connections),
            json.dumps(operating_states),
            config.AI_MODEL,
            confidence,
        )

    return {
        "status": "completed",
        "annotation_id": str(row["id"]),
        "page_id": page_id,
        "diagram_type": diagram_type,
        "component_count": len(components),
        "connection_count": len(connections),
        "operating_state_count": len(operating_states),
        "confidence": confidence,
        "latency_ms": latency_ms,
    }
