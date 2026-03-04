"""Learning path auto-generation task."""

import json
import logging
from uuid import UUID, uuid4

import anthropic

logger = logging.getLogger(__name__)


async def generate_learning_path(ctx: dict, manual_id: str, tenant_id: str) -> dict:
    """Auto-generate a learning path from a manual's table of contents.

    Analyzes manual structure to create a logical learning sequence
    with modules, lessons, and quiz checkpoints.
    """
    pool = ctx["pool"]
    settings = ctx["settings"]

    logger.info("Generating learning path for manual %s", manual_id)

    # 1. Fetch manual metadata and page classifications
    async with pool.acquire() as conn:
        await conn.execute("SELECT set_config('app.tenant_id', $1, TRUE)", tenant_id)
        manual = await conn.fetchrow(
            "SELECT id, title, make, model FROM manuals WHERE id = $1 AND tenant_id = $2",
            UUID(manual_id),
            UUID(tenant_id),
        )
        if not manual:
            return {"status": "error", "message": "Manual not found"}

        pages = await conn.fetch(
            """
            SELECT page_number, classification, LEFT(extracted_text, 300) as preview
            FROM pages WHERE manual_id = $1 ORDER BY page_number
            """,
            UUID(manual_id),
        )

    if not pages:
        return {"status": "error", "message": "No pages found"}

    # 2. Build content summary
    class_groups: dict[str, list] = {}
    for p in pages:
        cls = p["classification"] or "text"
        class_groups.setdefault(cls, []).append(p["page_number"])

    summary = f"Manual: {manual['title']}\n"
    if manual["make"]:
        summary += f"Make: {manual['make']}, Model: {manual['model'] or 'N/A'}\n"
    summary += f"Total pages: {len(pages)}\n"
    for cls, nums in class_groups.items():
        summary += f"  {cls}: {len(nums)} pages (e.g. {', '.join(str(n) for n in nums[:5])})\n"

    previews = "\n".join(
        f"Page {p['page_number']}: {(p['preview'] or '')[:120]}"
        for p in pages[:8]
    )

    # 3. Generate learning path with Claude
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = f"""Based on this service manual, generate a learning path for a mechanic.

{summary}
Sample pages:
{previews}

Create 3-6 modules progressing from basics to advanced:
1. System overview and safety
2. Component identification
3. Service procedures
4. Troubleshooting and diagnostics

Return JSON only:
```json
{{
  "title": "Learning path title",
  "system_area": "primary system",
  "modules": [
    {{
      "index": 0,
      "title": "Module title",
      "lessons": [
        {{"index": 0, "title": "Lesson title", "page_ids": [], "description": "What this covers"}}
      ],
      "quiz_question_count": 5
    }}
  ]
}}
```"""

    response = await client.messages.create(
        model=settings.DEFAULT_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        path_data = json.loads(text)
    except json.JSONDecodeError:
        path_data = {
            "title": f"{manual['title']} Learning Path",
            "system_area": "general",
            "modules": [],
        }

    # 4. Store in database
    path_id = uuid4()
    async with pool.acquire() as conn:
        await conn.execute("SELECT set_config('app.tenant_id', $1, TRUE)", tenant_id)
        await conn.execute(
            """
            INSERT INTO learning_paths (id, tenant_id, manual_id, title, system_area, modules, auto_generated)
            VALUES ($1, $2, $3, $4, $5, $6, TRUE)
            """,
            path_id,
            UUID(tenant_id),
            UUID(manual_id),
            path_data.get("title", f"{manual['title']} Learning Path"),
            path_data.get("system_area", "general"),
            json.dumps(path_data.get("modules", [])),
        )

    logger.info("Generated learning path %s with %d modules", path_id, len(path_data.get("modules", [])))

    return {
        "status": "completed",
        "learning_path_id": str(path_id),
        "module_count": len(path_data.get("modules", [])),
    }
