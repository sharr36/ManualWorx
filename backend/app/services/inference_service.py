"""Inference engine service — fills documentation gaps (Phase 6)."""

import json
import logging
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

import anthropic

from ..config import settings
from ..database import set_tenant_context


COVERAGE_ANALYSIS_PROMPT = """Analyze the documentation available for the "{system_area}" system on a {machine_model} machine.

Total pages: {total_pages}

Classification breakdown:
{classification_breakdown}

Sample pages with text content:
{page_samples}

Determine what documentation exists and what is missing. Return JSON:
{{
  "has_service_manual": true/false,
  "has_operator_manual": true/false,
  "has_parts_manual": true/false,
  "has_hydraulic_schematic": true/false,
  "has_electrical_schematic": true/false,
  "has_wiring_diagram": true/false,
  "has_diagnostic_flowchart": true/false,
  "coverage_score": 0.0 to 1.0 (how complete the documentation is),
  "gaps": [
    {{"type": "missing_doc_type", "description": "what's missing", "impact": "high|medium|low"}}
  ],
  "strengths": ["what documentation coverage is good"],
  "recommendations": ["what to add or improve"]
}}"""

COMPONENT_INFERENCE_PROMPT = """Analyze the following service manual pages about the "{system_area}" system.
Extract ALL components mentioned — both explicitly named and implied by context.

Pages:
{page_texts}

For each component, return JSON array:
[
  {{
    "component_name": "descriptive name",
    "component_type": "valve|pump|motor|cylinder|filter|sensor|switch|relay|solenoid|connector|gauge|accumulator|cooler|reservoir|harness|fuse|other",
    "designator": "label from manual (e.g. V1, M2) or null",
    "inferred_from": "manual_text" | "diagram" | "cross_reference" | "ai_knowledge",
    "confidence": 0.0 to 1.0,
    "specs": {{"key": "value"}},
    "source_pages": [page_numbers],
    "notes": "any relevant context"
  }}
]

Include components that are:
- Explicitly named with part numbers/designators
- Referenced in procedures (e.g. "remove the filter" implies a filter exists)
- Visible in diagrams or schematics
- Implied by system descriptions (e.g. "closed-center hydraulic system" implies certain valve types)"""

GAP_DETECTION_PROMPT = """Analyze this manual's content to identify documentation gaps that could impact a mechanic's ability to service the equipment.

Manual info:
- Title: {title}
- Make: {make}, Model: {model}
- Total pages: {total_pages}
- Page types: {page_breakdown}

Sample content from pages:
{sample_content}

Identify gaps and return JSON:
{{
  "overall_quality": 0.0 to 1.0,
  "gaps": [
    {{
      "category": "specs|procedures|diagrams|safety|parts|troubleshooting",
      "description": "what is missing",
      "impact": "critical|high|medium|low",
      "affected_systems": ["system areas affected"],
      "recommendation": "how to address this gap"
    }}
  ],
  "coverage_by_area": [
    {{
      "system_area": "area name",
      "coverage": 0.0 to 1.0,
      "has_specs": true/false,
      "has_procedures": true/false,
      "has_diagrams": true/false,
      "has_troubleshooting": true/false
    }}
  ]
}}"""

TEXT_ANALYSIS_PROMPT = """Analyze this service manual page text and extract structured information.

Page {page_number} [{classification}] from "{manual_title}":
{page_text}

Extract and return JSON:
{{
  "specs": [
    {{"name": "spec name", "value": "value with units", "context": "where this applies"}}
  ],
  "safety_warnings": [
    {{"text": "warning text", "severity": "danger|warning|caution|notice"}}
  ],
  "procedures": [
    {{"title": "procedure name", "steps": ["step 1", "step 2"], "tools_required": ["tool list"]}}
  ],
  "components_mentioned": [
    {{"name": "component", "type": "type", "part_number": "if available"}}
  ],
  "cross_references": [
    {{"text": "reference text", "target_page": page_number_or_null}}
  ]
}}"""


class InferenceService:
    """Handles cross-reference analysis, component inference, and gap detection."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def analyze_coverage(self, pool, tenant_id, manual_id, system_area):
        """Analyze documentation coverage for a system area within a manual.

        Checks what documentation types exist and identifies gaps.
        """
        manual_uuid = UUID(manual_id) if isinstance(manual_id, str) else manual_id

        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)

            # Get manual info
            manual = await conn.fetchrow(
                "SELECT title, make, model FROM manuals WHERE id = $1 AND tenant_id = $2",
                manual_uuid, tenant_id,
            )
            if not manual:
                raise ValueError("Manual not found")

            # Get page classification breakdown for this system area
            pages = await conn.fetch(
                """SELECT p.page_number, p.classification, p.has_table, p.has_diagram,
                          LEFT(p.extracted_text, 300) as text_preview
                   FROM pages p
                   WHERE p.manual_id = $1
                     AND (p.extracted_text ILIKE $2 OR $2 = '%')
                   ORDER BY p.page_number""",
                manual_uuid,
                f"%{system_area}%" if system_area else "%",
            )

        if not pages:
            return {
                "manual_id": manual_id,
                "system_area": system_area,
                "coverage_score": 0.0,
                "gaps": [{"type": "no_content", "description": "No pages found for this system area", "impact": "high"}],
                "page_count": 0,
            }

        # Build classification breakdown
        from collections import Counter
        class_counts = Counter(p["classification"] for p in pages)
        classification_breakdown = "\n".join(
            f"- {cls}: {count} pages" for cls, count in class_counts.most_common()
        )

        # Sample a few pages from each classification type for context
        samples_by_class: dict[str, list[str]] = {}
        for p in pages:
            cls = p["classification"]
            if cls not in samples_by_class:
                samples_by_class[cls] = []
            if len(samples_by_class[cls]) < 3 and p["text_preview"]:
                samples_by_class[cls].append(
                    f"  Page {p['page_number']+1}: {p['text_preview']}"
                )
        page_samples = "\n".join(
            f"[{cls}]\n" + "\n".join(samples)
            for cls, samples in samples_by_class.items()
            if samples
        )

        machine_model = f"{manual['make'] or ''} {manual['model'] or ''}".strip() or "unknown"

        prompt = COVERAGE_ANALYSIS_PROMPT.format(
            system_area=system_area or "general",
            machine_model=machine_model,
            total_pages=len(pages),
            classification_breakdown=classification_breakdown,
            page_samples=page_samples[:4000],
        )

        response = await self.client.messages.create(
            model=settings.RERANK_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1

        if start_idx >= 0 and end_idx > start_idx:
            result = json.loads(text[start_idx:end_idx])
        else:
            result = {"coverage_score": 0.5, "gaps": []}

        coverage_score = float(result.get("coverage_score", 0.5))

        # Store coverage analysis
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            await conn.execute(
                """INSERT INTO documentation_coverage
                   (tenant_id, manual_id, machine_model, system_area,
                    has_service_manual, has_operator_manual, has_parts_manual,
                    has_hydraulic_schematic, has_electrical_schematic,
                    has_wiring_diagram, has_diagnostic_flowchart,
                    coverage_score, gaps)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                   ON CONFLICT DO NOTHING""",
                tenant_id, manual_uuid, machine_model,
                system_area or "general",
                result.get("has_service_manual", False),
                result.get("has_operator_manual", False),
                result.get("has_parts_manual", False),
                result.get("has_hydraulic_schematic", False),
                result.get("has_electrical_schematic", False),
                result.get("has_wiring_diagram", False),
                result.get("has_diagnostic_flowchart", False),
                coverage_score,
                json.dumps(result.get("gaps", [])),
            )

        return {
            "manual_id": manual_id,
            "system_area": system_area,
            "machine_model": machine_model,
            "coverage_score": coverage_score,
            "has_service_manual": result.get("has_service_manual", False),
            "has_operator_manual": result.get("has_operator_manual", False),
            "has_parts_manual": result.get("has_parts_manual", False),
            "has_hydraulic_schematic": result.get("has_hydraulic_schematic", False),
            "has_electrical_schematic": result.get("has_electrical_schematic", False),
            "has_wiring_diagram": result.get("has_wiring_diagram", False),
            "has_diagnostic_flowchart": result.get("has_diagnostic_flowchart", False),
            "gaps": result.get("gaps", []),
            "strengths": result.get("strengths", []),
            "recommendations": result.get("recommendations", []),
            "page_count": len(pages),
        }

    async def infer_components(self, pool, tenant_id, manual_id, system_area):
        """Extract and infer components from manual pages for a system area.

        Uses AI to find explicitly named components and infer implied ones.
        """
        manual_uuid = UUID(manual_id) if isinstance(manual_id, str) else manual_id

        # Check for cached components
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            existing = await conn.fetch(
                """SELECT id, component_name, component_type, designator,
                          inferred_from, confidence_score, specs
                   FROM inferred_components
                   WHERE manual_id = $1 AND tenant_id = $2
                     AND ($3 IS NULL OR system_area = $3)
                   ORDER BY confidence_score DESC""",
                manual_uuid, tenant_id, system_area,
            )

        if existing:
            return {
                "manual_id": manual_id,
                "system_area": system_area,
                "components": [
                    {
                        "id": str(r["id"]),
                        "component_name": r["component_name"],
                        "component_type": r["component_type"],
                        "designator": r["designator"],
                        "inferred_from": r["inferred_from"],
                        "confidence": float(r["confidence_score"] or 0),
                        "specs": json.loads(r["specs"]) if isinstance(r["specs"], str) else (r["specs"] or {}),
                    }
                    for r in existing
                ],
                "cached": True,
            }

        # Fetch relevant pages
        async with pool.acquire() as conn:
            pages = await conn.fetch(
                """SELECT p.page_number, p.classification, p.extracted_text
                   FROM pages p
                   WHERE p.manual_id = $1
                     AND p.extracted_text IS NOT NULL
                     AND (p.extracted_text ILIKE $2 OR $2 = '%')
                   ORDER BY p.page_number
                   LIMIT 25""",
                manual_uuid,
                f"%{system_area}%" if system_area else "%",
            )

        if not pages:
            return {"manual_id": manual_id, "system_area": system_area, "components": [], "cached": False}

        page_texts = "\n\n".join(
            f"[Page {p['page_number']+1}, {p['classification']}]: {(p['extracted_text'] or '')[:800]}"
            for p in pages
        )

        prompt = COMPONENT_INFERENCE_PROMPT.format(
            system_area=system_area or "all systems",
            page_texts=page_texts[:8000],
        )

        response = await self.client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        start_idx = text.find("[")
        end_idx = text.rfind("]") + 1

        if start_idx < 0 or end_idx <= start_idx:
            return {"manual_id": manual_id, "system_area": system_area, "components": [], "cached": False}

        components = json.loads(text[start_idx:end_idx])

        # Store inferred components
        stored = []
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            for comp in components:
                comp_id = uuid4()
                await conn.execute(
                    """INSERT INTO inferred_components
                       (id, tenant_id, manual_id, system_area,
                        component_name, component_type, designator,
                        inferred_from, confidence_score, specs, spec_sources)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                    comp_id, tenant_id, manual_uuid,
                    system_area or "general",
                    comp.get("component_name", "Unknown"),
                    comp.get("component_type", "other"),
                    comp.get("designator"),
                    comp.get("inferred_from", "manual_text"),
                    float(comp.get("confidence", 0.5)),
                    json.dumps(comp.get("specs", {})),
                    json.dumps(comp.get("source_pages", [])),
                )
                stored.append({
                    "id": str(comp_id),
                    "component_name": comp.get("component_name", "Unknown"),
                    "component_type": comp.get("component_type", "other"),
                    "designator": comp.get("designator"),
                    "inferred_from": comp.get("inferred_from", "manual_text"),
                    "confidence": float(comp.get("confidence", 0.5)),
                    "specs": comp.get("specs", {}),
                    "notes": comp.get("notes", ""),
                })

        return {
            "manual_id": manual_id,
            "system_area": system_area,
            "components": stored,
            "cached": False,
        }

    async def detect_gaps(self, pool, tenant_id, manual_id):
        """Detect documentation gaps across an entire manual.

        Analyzes the manual's content to find missing specs, procedures,
        diagrams, and safety information.
        """
        manual_uuid = UUID(manual_id) if isinstance(manual_id, str) else manual_id

        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)

            manual = await conn.fetchrow(
                "SELECT title, make, model, total_pages FROM manuals WHERE id = $1 AND tenant_id = $2",
                manual_uuid, tenant_id,
            )
            if not manual:
                raise ValueError("Manual not found")

            # Page classification breakdown
            breakdown = await conn.fetch(
                """SELECT classification, COUNT(*) as cnt
                   FROM pages WHERE manual_id = $1
                   GROUP BY classification ORDER BY cnt DESC""",
                manual_uuid,
            )

            # Sample pages for content analysis
            sample_pages = await conn.fetch(
                """SELECT page_number, classification, LEFT(extracted_text, 500) as text_preview
                   FROM pages WHERE manual_id = $1 AND extracted_text IS NOT NULL
                   ORDER BY page_number
                   LIMIT 30""",
                manual_uuid,
            )

        page_breakdown = ", ".join(f"{r['classification']}: {r['cnt']}" for r in breakdown)
        sample_content = "\n\n".join(
            f"[Page {p['page_number']+1}, {p['classification']}]: {p['text_preview'] or ''}"
            for p in sample_pages
        )

        prompt = GAP_DETECTION_PROMPT.format(
            title=manual["title"],
            make=manual["make"] or "Unknown",
            model=manual["model"] or "Unknown",
            total_pages=manual["total_pages"] or len(sample_pages),
            page_breakdown=page_breakdown or "no pages classified",
            sample_content=sample_content[:8000],
        )

        response = await self.client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1

        if start_idx >= 0 and end_idx > start_idx:
            result = json.loads(text[start_idx:end_idx])
        else:
            result = {"overall_quality": 0.5, "gaps": [], "coverage_by_area": []}

        return {
            "manual_id": manual_id,
            "title": manual["title"],
            "make": manual["make"],
            "model": manual["model"],
            "total_pages": manual["total_pages"],
            "page_breakdown": {r["classification"]: r["cnt"] for r in breakdown},
            "overall_quality": float(result.get("overall_quality", 0.5)),
            "gaps": result.get("gaps", []),
            "coverage_by_area": result.get("coverage_by_area", []),
        }

    async def analyze_text(self, pool, tenant_id, page_id):
        """Analyze a single page's text for structured information extraction.

        Extracts specs, safety warnings, procedures, component references,
        and cross-references.
        """
        page_uuid = UUID(page_id) if isinstance(page_id, str) else page_id

        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            page = await conn.fetchrow(
                """SELECT p.page_number, p.classification, p.extracted_text,
                          m.title as manual_title
                   FROM pages p
                   JOIN manuals m ON m.id = p.manual_id
                   WHERE p.id = $1 AND m.tenant_id = $2""",
                page_uuid, tenant_id,
            )

        if not page or not page["extracted_text"]:
            raise ValueError("Page not found or has no text")

        prompt = TEXT_ANALYSIS_PROMPT.format(
            page_number=page["page_number"] + 1,
            classification=page["classification"],
            manual_title=page["manual_title"],
            page_text=page["extracted_text"][:6000],
        )

        response = await self.client.messages.create(
            model=settings.RERANK_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1

        if start_idx >= 0 and end_idx > start_idx:
            result = json.loads(text[start_idx:end_idx])
        else:
            result = {"specs": [], "safety_warnings": [], "procedures": [], "components_mentioned": [], "cross_references": []}

        return {
            "page_id": page_id,
            "page_number": page["page_number"],
            "classification": page["classification"],
            "manual_title": page["manual_title"],
            **result,
        }

    async def aggregate_analysis(self, pool, tenant_id, manual_id, system_area=None):
        """Aggregate analysis across multiple pages for a system area.

        Combines coverage analysis, component inference, and gap detection
        into a comprehensive system report.
        """
        coverage = await self.analyze_coverage(pool, tenant_id, manual_id, system_area)
        components = await self.infer_components(pool, tenant_id, manual_id, system_area)
        gaps = await self.detect_gaps(pool, tenant_id, manual_id)

        return {
            "manual_id": manual_id,
            "system_area": system_area,
            "coverage": coverage,
            "components": components,
            "gap_analysis": gaps,
            "summary": {
                "coverage_score": coverage.get("coverage_score", 0),
                "component_count": len(components.get("components", [])),
                "gap_count": len(gaps.get("gaps", [])),
                "overall_quality": gaps.get("overall_quality", 0),
                "critical_gaps": len([
                    g for g in gaps.get("gaps", [])
                    if g.get("impact") == "critical"
                ]),
            },
        }
