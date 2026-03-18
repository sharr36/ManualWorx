"""Interactive schematic viewer service (Phase 5)."""

import json
import logging
from uuid import UUID

from .ai_service import AIService

logger = logging.getLogger(__name__)
_ai = AIService()


class ViewerService:
    """Handles diagram annotation, schematic generation, and component location."""

    async def annotate_diagram(self, pool, tenant_id, page_id, diagram_type=None, force=False):
        """Trigger AI annotation for a diagram page.

        If a cached annotation exists and is fresh, returns it (unless force=True).
        Otherwise calls Claude Vision for a new annotation.
        """
        page_uuid = UUID(page_id) if isinstance(page_id, str) else page_id

        async with pool.acquire() as conn:
            # Check for cached annotation (skip if force re-annotate)
            existing = None
            if not force:
                existing = await conn.fetchrow(
                    """SELECT id, diagram_type, annotation_data, component_count,
                              connection_count, operating_states, confidence_overall,
                              generated_at
                       FROM diagram_annotations
                       WHERE page_id = $1 AND tenant_id = $2""",
                    page_uuid,
                    tenant_id,
                )

            if existing:
                annotation_data = (
                    json.loads(existing["annotation_data"])
                    if isinstance(existing["annotation_data"], str)
                    else existing["annotation_data"]
                )
                operating_states = (
                    json.loads(existing["operating_states"])
                    if isinstance(existing["operating_states"], str)
                    else existing["operating_states"]
                ) or []
                return {
                    "id": str(existing["id"]),
                    "page_id": str(page_uuid),
                    "diagram_type": existing["diagram_type"],
                    "annotation_data": annotation_data,
                    "component_count": existing["component_count"] or 0,
                    "connection_count": existing["connection_count"] or 0,
                    "operating_states": operating_states,
                    "confidence_overall": float(existing["confidence_overall"] or 0),
                    "cached": True,
                }

            # Fetch page for image + text
            page = await conn.fetchrow(
                """SELECT p.id, p.page_number, p.classification, p.extracted_text,
                          p.image_url, p.manual_id
                   FROM pages p
                   JOIN manuals m ON m.id = p.manual_id
                   WHERE p.id = $1 AND m.tenant_id = $2""",
                page_uuid,
                tenant_id,
            )

        if not page:
            raise ValueError("Page not found")

        # Get image from storage
        from ..config import settings
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=settings.AWS_ENDPOINT_URL_S3,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

        storage_key = page["image_url"]
        if not storage_key:
            storage_key = f"manuals/{tenant_id}/{page['manual_id']}/pages/{page['page_number']}.png"

        try:
            obj = s3.get_object(Bucket=settings.BUCKET_NAME, Key=storage_key)
            image_bytes = obj["Body"].read()
        except Exception as e:
            logger.error("Failed to fetch page image from S3 key=%s: %s", storage_key, e)
            raise ValueError(f"Could not load page image: {e}")

        # Determine diagram type
        dt = diagram_type
        if not dt:
            cls = page["classification"] or ""
            if "hydraulic" in cls:
                dt = "hydraulic_schematic"
            elif "electrical" in cls:
                dt = "electrical"
            elif "wiring" in cls:
                dt = "wiring"

        # Call AI
        result = await _ai.analyze_diagram(
            image_bytes=image_bytes,
            page_text=page["extracted_text"] or "",
            diagram_type=dt,
        )

        annotation_data = {
            "components": result["components"],
            "connections": result["connections"],
        }
        operating_states = result["operating_states"]

        # Store
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
                tenant_id,
                page_uuid,
                result["diagram_type"],
                json.dumps(annotation_data),
                result["component_count"],
                result["connection_count"],
                json.dumps(operating_states),
                result.get("model_used", ""),
                result["confidence_overall"],
            )

        return {
            "id": str(row["id"]),
            "page_id": str(page_uuid),
            "diagram_type": result["diagram_type"],
            "annotation_data": annotation_data,
            "component_count": result["component_count"],
            "connection_count": result["connection_count"],
            "operating_states": operating_states,
            "confidence_overall": result["confidence_overall"],
            "cached": False,
        }

    async def get_annotations(self, pool, tenant_id, page_id):
        """Retrieve cached annotations for a diagram page."""
        page_uuid = UUID(page_id) if isinstance(page_id, str) else page_id

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT da.id, da.page_id, da.diagram_type, da.annotation_data,
                          da.component_count, da.connection_count, da.operating_states,
                          da.confidence_overall, da.generated_at, da.last_verified_at
                   FROM diagram_annotations da
                   WHERE da.page_id = $1 AND da.tenant_id = $2""",
                page_uuid,
                tenant_id,
            )

        if not row:
            return None

        annotation_data = (
            json.loads(row["annotation_data"])
            if isinstance(row["annotation_data"], str)
            else row["annotation_data"]
        )
        operating_states = (
            json.loads(row["operating_states"])
            if isinstance(row["operating_states"], str)
            else row["operating_states"]
        ) or []

        return {
            "id": str(row["id"]),
            "page_id": str(row["page_id"]),
            "diagram_type": row["diagram_type"],
            "annotation_data": annotation_data,
            "component_count": row["component_count"] or 0,
            "connection_count": row["connection_count"] or 0,
            "operating_states": operating_states,
            "confidence_overall": float(row["confidence_overall"] or 0),
            "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None,
            "verified": row["last_verified_at"] is not None,
        }

    async def get_operating_states(self, pool, tenant_id, page_id):
        """Get all operating states for a diagram."""
        annotation = await self.get_annotations(pool, tenant_id, page_id)
        if not annotation:
            return []
        return annotation.get("operating_states", [])

    async def list_diagram_pages(self, pool, tenant_id, manual_id=None):
        """List all diagram pages available for the viewer."""
        async with pool.acquire() as conn:
            if manual_id:
                rows = await conn.fetch(
                    """SELECT p.id, p.manual_id, p.page_number, p.classification,
                              m.title as manual_title,
                              da.id as annotation_id,
                              da.component_count, da.confidence_overall
                       FROM pages p
                       JOIN manuals m ON m.id = p.manual_id
                       LEFT JOIN diagram_annotations da ON da.page_id = p.id
                       WHERE m.tenant_id = $1 AND m.id = $2
                         AND (
                           p.classification IN (
                             'hydraulic_schematic', 'electrical_diagram',
                             'wiring_harness', 'diagnostic_flowchart',
                             'parts_exploded_view', 'general_illustration'
                           )
                           OR p.has_diagram = TRUE
                           OR da.page_id IS NOT NULL
                         )
                       ORDER BY m.title, p.page_number""",
                    tenant_id,
                    UUID(manual_id) if isinstance(manual_id, str) else manual_id,
                )
            else:
                rows = await conn.fetch(
                    """SELECT p.id, p.manual_id, p.page_number, p.classification,
                              m.title as manual_title,
                              da.id as annotation_id,
                              da.component_count, da.confidence_overall
                       FROM pages p
                       JOIN manuals m ON m.id = p.manual_id
                       LEFT JOIN diagram_annotations da ON da.page_id = p.id
                       WHERE m.tenant_id = $1
                         AND (
                           p.classification IN (
                             'hydraulic_schematic', 'electrical_diagram',
                             'wiring_harness', 'diagnostic_flowchart',
                             'parts_exploded_view', 'general_illustration'
                           )
                           OR p.has_diagram = TRUE
                           OR da.page_id IS NOT NULL
                         )
                       ORDER BY m.title, p.page_number""",
                    tenant_id,
                )

        return [
            {
                "page_id": str(r["id"]),
                "manual_id": str(r["manual_id"]),
                "page_number": r["page_number"],
                "classification": r["classification"],
                "manual_title": r["manual_title"],
                "annotated": r["annotation_id"] is not None,
                "component_count": r["component_count"] or 0,
                "confidence": float(r["confidence_overall"]) if r["confidence_overall"] else None,
            }
            for r in rows
        ]

    async def generate_schematic(self, pool, tenant_id, manual_id, system_area):
        """Generate an AI schematic from text descriptions in the manual."""
        manual_uuid = UUID(manual_id) if isinstance(manual_id, str) else manual_id

        # Fetch relevant pages
        async with pool.acquire() as conn:
            pages = await conn.fetch(
                """SELECT p.page_number, p.extracted_text, p.classification
                   FROM pages p
                   JOIN manuals m ON m.id = p.manual_id
                   WHERE m.id = $1 AND m.tenant_id = $2
                     AND p.extracted_text IS NOT NULL
                     AND (p.extracted_text ILIKE $3
                          OR p.classification IN (
                            'hydraulic_schematic', 'electrical_diagram',
                            'wiring_harness'
                          ))
                   ORDER BY p.page_number
                   LIMIT 20""",
                manual_uuid,
                tenant_id,
                f"%{system_area}%",
            )

        if not pages:
            raise ValueError(f"No relevant pages found for system area: {system_area}")

        # Build context from pages
        context = "\n\n".join(
            f"[Page {p['page_number']+1}, {p['classification']}]: {(p['extracted_text'] or '')[:1000]}"
            for p in pages
        )

        from .ai_service import AIService
        import anthropic
        from ..config import settings

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        prompt = f"""Based on the following service manual pages about the "{system_area}" system,
generate a structured schematic representation as JSON.

Context pages:
{context}

Return JSON:
{{
  "title": "schematic title",
  "system_area": "{system_area}",
  "components": [
    {{
      "id": "comp_N",
      "name": "component name",
      "type": "valve|pump|motor|cylinder|filter|etc",
      "designator": "label from manual",
      "x_pct": 0-100,
      "y_pct": 0-100,
      "specs": {{}}
    }}
  ],
  "connections": [
    {{
      "from_id": "comp_N",
      "to_id": "comp_M",
      "line_type": "pressure|return|pilot|drain|signal",
      "label": ""
    }}
  ],
  "notes": "any important notes about this system",
  "confidence": 0.0 to 1.0
}}"""

        response = await client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1

        if start_idx < 0 or end_idx <= start_idx:
            raise ValueError("Failed to generate schematic")

        result = json.loads(text[start_idx:end_idx])

        source_page_ids = [str(p["page_number"]) for p in pages]

        # Store generated schematic
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO generated_schematics
                   (tenant_id, manual_id, system_area, source_type,
                    diagram_dsl, component_count, confidence_overall)
                   VALUES ($1, $2, $3, 'text_inference', $4, $5, $6)
                   RETURNING id, created_at""",
                tenant_id,
                manual_uuid,
                system_area,
                json.dumps(result),
                len(result.get("components", [])),
                float(result.get("confidence", 0.5)),
            )

        return {
            "id": str(row["id"]),
            "manual_id": manual_id,
            "system_area": system_area,
            "diagram_dsl": result,
            "component_count": len(result.get("components", [])),
            "confidence_overall": float(result.get("confidence", 0.5)),
            "disclaimer": "AI-GENERATED — NOT FROM OEM MANUAL",
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    async def locate_component(
        self, pool, tenant_id, machine_model, component_designator, manual_ids=None
    ):
        """Locate a component in manuals using text search + AI."""
        # Check cached locations first
        async with pool.acquire() as conn:
            cached = await conn.fetchrow(
                """SELECT * FROM component_locations
                   WHERE tenant_id = $1
                     AND machine_model ILIKE $2
                     AND component_designator ILIKE $3""",
                tenant_id,
                machine_model,
                component_designator,
            )

        if cached:
            return {
                "id": str(cached["id"]),
                "machine_model": cached["machine_model"],
                "component_designator": cached["component_designator"],
                "component_type": cached["component_type"],
                "location_description": cached["location_description"],
                "access_notes": cached["access_notes"],
                "location_coords": (
                    json.loads(cached["location_coords"])
                    if isinstance(cached["location_coords"], str)
                    else cached["location_coords"]
                ),
                "source": cached["source"],
                "confidence": float(cached["confidence"] or 0),
                "cached": True,
            }

        # Search manuals for component references
        async with pool.acquire() as conn:
            query = """
                SELECT p.id, p.page_number, p.extracted_text, p.classification,
                       m.title, m.make, m.model
                FROM pages p
                JOIN manuals m ON m.id = p.manual_id
                WHERE m.tenant_id = $1
                  AND p.extracted_text ILIKE $2
            """
            params = [tenant_id, f"%{component_designator}%"]

            if manual_ids:
                placeholders = ", ".join(
                    f"${i+3}" for i in range(len(manual_ids))
                )
                query += f" AND m.id IN ({placeholders})"
                params.extend(UUID(mid) if isinstance(mid, str) else mid for mid in manual_ids)

            query += " ORDER BY p.page_number LIMIT 10"
            pages = await conn.fetch(query, *params)

        if not pages:
            return {
                "machine_model": machine_model,
                "component_designator": component_designator,
                "location_description": "Component not found in available manuals.",
                "confidence": 0.0,
                "source": "not_found",
            }

        # Use AI to synthesize location info
        context = "\n\n".join(
            f"[{p['title']}, Page {p['page_number']+1}]: {(p['extracted_text'] or '')[:500]}"
            for p in pages
        )

        from ..config import settings
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        prompt = f"""Based on the following manual pages, describe the location of component "{component_designator}" on a {machine_model}.

Context:
{context}

Return JSON:
{{
  "component_type": "valve|pump|motor|sensor|etc",
  "location_description": "physical location description",
  "access_notes": "how to access the component for service",
  "reference_pages": [page_numbers],
  "confidence": 0.0 to 1.0
}}"""

        response = await client.messages.create(
            model=settings.RERANK_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1

        if start_idx >= 0 and end_idx > start_idx:
            result = json.loads(text[start_idx:end_idx])
        else:
            result = {
                "component_type": "unknown",
                "location_description": "Could not determine location.",
                "access_notes": "",
                "confidence": 0.2,
            }

        # Cache the result
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO component_locations
                   (tenant_id, machine_model, component_designator,
                    component_type, location_description, access_notes,
                    source, confidence)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   RETURNING id""",
                tenant_id,
                machine_model,
                component_designator,
                result.get("component_type", "unknown"),
                result.get("location_description", ""),
                result.get("access_notes", ""),
                "ai_inference",
                float(result.get("confidence", 0.5)),
            )

        return {
            "id": str(row["id"]),
            "machine_model": machine_model,
            "component_designator": component_designator,
            "component_type": result.get("component_type", "unknown"),
            "location_description": result.get("location_description", ""),
            "access_notes": result.get("access_notes", ""),
            "source": "ai_inference",
            "confidence": float(result.get("confidence", 0.5)),
            "reference_pages": result.get("reference_pages", []),
            "cached": False,
        }

    async def compare_diagrams(self, pool, tenant_id, page_ids):
        """Compare two or more diagram pages side by side."""
        results = []
        for pid in page_ids:
            annotation = await self.get_annotations(pool, tenant_id, pid)
            if annotation:
                results.append(annotation)
            else:
                results.append({
                    "page_id": pid,
                    "annotation_data": None,
                    "note": "Not annotated yet. Trigger annotation first.",
                })

        # Build comparison summary if both are annotated
        annotated = [r for r in results if r.get("annotation_data")]
        comparison = {
            "pages": results,
            "both_annotated": len(annotated) == len(page_ids),
        }

        if len(annotated) >= 2:
            # Find shared and unique components
            sets = []
            for a in annotated:
                comps = a.get("annotation_data", {}).get("components", [])
                sets.append({c.get("designator", c.get("id", "")) for c in comps})

            if len(sets) >= 2:
                shared = sets[0] & sets[1]
                only_first = sets[0] - sets[1]
                only_second = sets[1] - sets[0]
                comparison["shared_components"] = list(shared)
                comparison["unique_to_first"] = list(only_first)
                comparison["unique_to_second"] = list(only_second)

        return comparison

    async def verify_annotation(self, pool, tenant_id, annotation_id, verified_by):
        """Mark an annotation as human-verified."""
        annotation_uuid = (
            UUID(annotation_id) if isinstance(annotation_id, str) else annotation_id
        )
        user_uuid = UUID(verified_by) if isinstance(verified_by, str) else verified_by

        async with pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE diagram_annotations
                   SET last_verified_at = NOW(), verified_by = $3
                   WHERE id = $1 AND tenant_id = $2""",
                annotation_uuid,
                tenant_id,
                user_uuid,
            )

        return "UPDATE 1" in result
