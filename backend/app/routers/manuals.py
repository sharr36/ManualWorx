"""Manual management endpoints."""

import asyncio
import json
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse, StreamingResponse

from ..models.manual import ManualDetailResponse, ManualResponse, PageResponse
from ..services.manual_service import ManualService
from manualworx_shared.constants import ManualType, UserRole, MAX_UPLOAD_BYTES
from ..config import settings

router = APIRouter(prefix="/api/manuals", tags=["manuals"])
_service = ManualService()


@router.post("/upload")
async def upload_manual(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    make: str = Form(None),
    model: str = Form(None),
    manual_type: str = Form("service"),
) -> ManualResponse:
    """Upload a new manual PDF for processing."""
    # Validate PDF
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # RBAC: owner or manager can upload
    role = getattr(request.state, "user_role", None)
    if role not in (UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only owners and managers can upload manuals")

    tenant_id = request.state.tenant_id
    pool = request.app.state.db_pool
    redis = getattr(request.app.state, "redis", None)

    pdf_bytes = await file.read()

    # Validate file size
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    # Sanitize filename — strip path components to prevent path traversal
    import os
    safe_filename = os.path.basename(file.filename or "upload.pdf")

    try:
        result = await _service.upload_manual(
            pool=pool,
            redis=redis,
            tenant_id=tenant_id,
            title=title,
            make=make,
            model=model,
            manual_type=manual_type,
            pdf_bytes=pdf_bytes,
            filename=safe_filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ManualResponse(**result)


@router.get("")
async def list_manuals(request: Request) -> list[ManualResponse]:
    """List all manuals for the current tenant."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    results = await _service.list_manuals(pool, tenant_id)
    return [ManualResponse(**r) for r in results]


@router.get("/{manual_id}")
async def get_manual(manual_id: UUID, request: Request) -> ManualDetailResponse:
    """Get manual details and processing status."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    result = await _service.get_manual(pool, tenant_id, manual_id)
    if not result:
        raise HTTPException(status_code=404, detail="Manual not found")

    return ManualDetailResponse(**result)


@router.get("/{manual_id}/pages")
async def get_manual_pages(manual_id: UUID, request: Request) -> list[PageResponse]:
    """Get all pages for a manual."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    pages = await _service.get_manual_pages(pool, tenant_id, manual_id)
    return [
        PageResponse(
            id=str(p["id"]),
            manual_id=str(p["manual_id"]),
            page_number=p["page_number"],
            classification=p["classification"],
            extracted_text=p["extracted_text"],
            image_url=p["image_url"],
            has_table=p["has_table"],
            has_diagram=p["has_diagram"],
        )
        for p in pages
    ]


@router.get("/{manual_id}/progress")
async def manual_progress(manual_id: UUID, request: Request):
    """Stream ingestion progress via SSE.

    Subscribes to Redis pub/sub channel `progress:{manual_id}` and streams
    events until the manual reaches 'ready' or 'failed' status.
    """
    redis = getattr(request.app.state, "redis", None)
    if not redis:
        raise HTTPException(status_code=503, detail="Progress tracking unavailable")

    async def event_generator():
        pubsub = redis.pubsub()
        channel = f"progress:{manual_id}"
        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg and msg["type"] == "message":
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"

                    # Close stream when done
                    try:
                        parsed = json.loads(data)
                        if parsed.get("stage") in ("ready", "failed"):
                            break
                    except Exception:
                        pass
                else:
                    # Send keepalive to prevent connection timeout
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{manual_id}/pages/{page_number}/image")
async def get_page_image(manual_id: UUID, page_number: int, request: Request):
    """Proxy page images via pre-signed URL redirect.

    Generates a pre-signed Tigris URL and redirects the client, avoiding
    exposure of S3 credentials.
    """
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    # Verify the page exists and belongs to the tenant
    async with pool.acquire() as conn:
        page = await conn.fetchrow(
            """
            SELECT p.image_url
            FROM pages p
            JOIN manuals m ON p.manual_id = m.id
            WHERE p.manual_id = $1 AND p.page_number = $2 AND m.tenant_id = $3
            """,
            manual_id,
            page_number,
            tenant_id,
        )

    if not page or not page["image_url"]:
        raise HTTPException(status_code=404, detail="Page image not found")

    # Generate pre-signed URL from storage provider
    from ..providers import get_storage_provider
    storage = get_storage_provider()
    url = await storage.get_url(page["image_url"])

    return RedirectResponse(url=url, status_code=302)


@router.post("/{manual_id}/retry")
async def retry_manual(manual_id: UUID, request: Request) -> ManualResponse:
    """Re-enqueue a failed or stuck manual for processing."""
    role = getattr(request.state, "user_role", None)
    if role not in (UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only owners and managers can retry processing")

    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    # Verify manual exists and belongs to tenant
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, upload_status FROM manuals WHERE id = $1 AND tenant_id = $2",
            manual_id,
            tenant_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Manual not found")

    if row["upload_status"] not in ("failed", "processing", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry manual with status '{row['upload_status']}'"
        )

    # Clean up chunks/vectors from previous attempt (keep pages — they're expensive to reprocess)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chunks WHERE page_id IN (SELECT id FROM pages WHERE manual_id = $1)", manual_id)
        await conn.execute(
            "UPDATE manuals SET upload_status = 'pending', updated_at = NOW() WHERE id = $1",
            manual_id,
        )

    # Re-enqueue the ingestion job
    from arq.connections import create_pool as create_arq_pool
    from manualworx_shared.config import arq_redis_settings
    from ..config import settings

    try:
        arq_pool = await create_arq_pool(arq_redis_settings(settings.REDIS_URL))
        await arq_pool.enqueue_job("ingest_manual", str(manual_id), str(tenant_id))
        await arq_pool.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue retry: {e}")

    # Re-fetch and return
    result = await _service.get_manual(pool, tenant_id, manual_id)
    if not result:
        raise HTTPException(status_code=404, detail="Manual not found after retry")
    # Only pass fields ManualResponse accepts (exclude extra keys like pages_processed)
    return ManualResponse(
        id=result["id"],
        title=result["title"],
        make=result.get("make"),
        model=result.get("model"),
        manual_type=result.get("manual_type"),
        total_pages=result.get("total_pages"),
        upload_status=result["upload_status"],
        visibility=result.get("visibility"),
        created_at=result["created_at"],
        updated_at=result.get("updated_at"),
    )


@router.post("/{manual_id}/reclassify")
async def reclassify_manual(manual_id: UUID, request: Request) -> dict:
    """Re-run AI classification on all pages of a ready manual."""
    role = getattr(request.state, "user_role", None)
    if role not in (UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only owners and managers can reclassify")

    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    # Verify manual exists, belongs to tenant, and is ready
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, upload_status FROM manuals WHERE id = $1 AND tenant_id = $2",
            manual_id,
            tenant_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Manual not found")

    if row["upload_status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Manual must be 'ready' to reclassify (current: '{row['upload_status']}')"
        )

    # Get all page IDs
    async with pool.acquire() as conn:
        page_rows = await conn.fetch(
            "SELECT id FROM pages WHERE manual_id = $1 ORDER BY page_number",
            manual_id,
        )

    if not page_rows:
        raise HTTPException(status_code=400, detail="No pages to classify")

    page_ids = [str(r["id"]) for r in page_rows]

    # Use AI vision classification for accurate results
    from arq.connections import create_pool as create_arq_pool
    from manualworx_shared.config import arq_redis_settings
    from ..config import settings

    try:
        arq_pool = await create_arq_pool(arq_redis_settings(settings.REDIS_URL))
        await arq_pool.enqueue_job("classify_pages", str(manual_id), page_ids)
        await arq_pool.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue classification: {e}")

    return {"status": "queued", "pages": len(page_ids)}


@router.get("/{manual_id}/search")
async def search_manual(
    manual_id: UUID,
    request: Request,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Full-text search within a manual's pages and chunks."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    # Verify manual belongs to tenant
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM manuals WHERE id = $1 AND tenant_id = $2",
            manual_id, tenant_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Manual not found")

    # Full-text search with ts_rank scoring
    async with pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT p.id AS page_id, p.page_number, p.classification, p.has_table, p.has_diagram,
                   ts_rank_cd(to_tsvector('english', COALESCE(p.extracted_text, '')),
                              plainto_tsquery('english', $2)) AS rank,
                   ts_headline('english', COALESCE(p.extracted_text, ''),
                               plainto_tsquery('english', $2),
                               'StartSel=<mark>, StopSel=</mark>, MaxWords=60, MinWords=20') AS snippet
            FROM pages p
            WHERE p.manual_id = $1
              AND to_tsvector('english', COALESCE(p.extracted_text, ''))
                  @@ plainto_tsquery('english', $2)
            ORDER BY rank DESC
            LIMIT $3
            """,
            manual_id, q, limit,
        )

    return {
        "query": q,
        "total": len(results),
        "results": [
            {
                "page_id": str(r["page_id"]),
                "page_number": r["page_number"],
                "classification": r["classification"],
                "has_table": r["has_table"],
                "has_diagram": r["has_diagram"],
                "rank": float(r["rank"]),
                "snippet": r["snippet"],
            }
            for r in results
        ],
    }


@router.get("/{manual_id}/schematics")
async def get_manual_schematics(manual_id: UUID, request: Request) -> dict:
    """Get all schematic pages with their annotation data for the Schematics tab."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM manuals WHERE id = $1 AND tenant_id = $2",
            manual_id, tenant_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Manual not found")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id AS page_id, p.page_number, p.classification, p.extracted_text,
                   da.diagram_type, da.annotation_data, da.component_count,
                   da.connection_count, da.operating_states, da.confidence_overall,
                   da.generated_at AS annotated_at
            FROM pages p
            LEFT JOIN diagram_annotations da ON da.page_id = p.id
            WHERE p.manual_id = $1
              AND (
                  p.classification IN (
                      'hydraulic_schematic', 'electrical_diagram',
                      'wiring_harness', 'diagnostic_flowchart',
                      'parts_exploded_view', 'general_illustration'
                  )
                  OR p.has_diagram = TRUE
                  OR da.page_id IS NOT NULL
              )
            ORDER BY p.page_number
            """,
            manual_id,
        )

    schematics = []
    for r in rows:
        entry = {
            "page_id": str(r["page_id"]),
            "page_number": r["page_number"],
            "classification": r["classification"],
            "annotated": r["annotation_data"] is not None,
        }
        if r["annotation_data"] is not None:
            ad = r["annotation_data"]
            annotation = json.loads(ad) if isinstance(ad, str) else ad
            os_data = r["operating_states"]
            operating_states = (json.loads(os_data) if isinstance(os_data, str) else os_data) or []
            entry.update({
                "diagram_type": r["diagram_type"],
                "component_count": r["component_count"],
                "connection_count": r["connection_count"],
                "confidence": float(r["confidence_overall"]) if r["confidence_overall"] else None,
                "components": annotation.get("components", []),
                "connections": annotation.get("connections", []),
                "operating_states": operating_states,
                "annotated_at": r["annotated_at"].isoformat() if r["annotated_at"] else None,
            })
        schematics.append(entry)

    return {
        "total": len(schematics),
        "annotated": sum(1 for s in schematics if s["annotated"]),
        "schematics": schematics,
    }


@router.post("/{manual_id}/extract-specs")
async def extract_specs(manual_id: UUID, request: Request) -> dict:
    """Extract specifications (torque, pressures, clearances) from manual pages using AI."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, make, model FROM manuals WHERE id = $1 AND tenant_id = $2",
            manual_id, tenant_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Manual not found")

    # Get ALL pages likely to contain specs — no limit
    async with pool.acquire() as conn:
        spec_pages = await conn.fetch(
            """
            SELECT id, page_number, classification, extracted_text
            FROM pages
            WHERE manual_id = $1
              AND extracted_text IS NOT NULL
              AND LENGTH(TRIM(extracted_text)) > 30
              AND (
                classification = 'torque_spec_table'
                OR extracted_text ~* '(torque|ft[\.\s-]?lb|[Nn][\.\s]?[Mm]|in[\.\s-]?lb)'
                OR extracted_text ~* '(clearance|tolerance|end\s*play|backlash|wear\s*limit)'
                OR extracted_text ~* '(psi|bar|kpa|pressure|relief)'
                OR extracted_text ~* '(volt|amp|ohm|resistance|battery)'
                OR extracted_text ~* '(capacity|quart|liter|gallon|fluid)'
                OR extracted_text ~* '(specification|rpm|temperature|°[FC])'
                OR extracted_text ~* '(\d+\s*(ft[\.\s-]?lb|[Nn][\.\s]?[Mm]|psi|bar|volt|ohm|rpm|°[FC]|gpm|qt|[Ll]))'
              )
            ORDER BY page_number
            """,
            manual_id,
        )

    if not spec_pages:
        return {"specs": [], "source_pages": [], "total": 0}

    machine_desc = f"{row['make'] or ''} {row['model'] or ''}".strip()

    # Process pages in batches to avoid prompt truncation
    BATCH_SIZE = 15  # ~15 pages * 2000 chars = ~30K chars per batch
    all_specs: list[dict] = []
    source_pages = []

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    for batch_start in range(0, len(spec_pages), BATCH_SIZE):
        batch = spec_pages[batch_start:batch_start + BATCH_SIZE]

        combined_text = ""
        for p in batch:
            text = (p["extracted_text"] or "").strip()
            if text:
                combined_text += f"\n--- Page {p['page_number'] + 1} ({p['classification']}) ---\n{text[:3000]}\n"
                if batch_start == 0 or p["page_number"] not in [sp["page_number"] for sp in source_pages]:
                    source_pages.append({"page_number": p["page_number"], "classification": p["classification"]})

        if not combined_text.strip():
            continue

        prompt = f"""You are a heavy equipment service manual expert. Extract EVERY technical specification from these {machine_desc} service manual pages.

IMPORTANT: Be thorough. A mechanic needs these specs to service the machine. Look for:

TORQUE SPECS: bolt torques, fastener specs, tightening sequences, retorque values
  - Look for: ft-lb, lb-ft, N·m, Nm, in-lb, "tighten to", "torque to"

PRESSURES: hydraulic pressures, relief settings, charge pressures, test pressures
  - Look for: psi, PSI, bar, kPa, MPa, "set at", "adjust to", "relief pressure"

CLEARANCES: bearing clearances, end play, backlash, gear mesh, wear limits
  - Look for: mm, in, thou, "clearance", "end play", "backlash", "wear limit"

ELECTRICAL: battery voltage, alternator output, sensor values, resistance specs
  - Look for: volt, V, amp, A, ohm, Ω, "resistance", "output"

CAPACITIES: oil capacity, coolant, hydraulic reservoir, fuel tank, gear cases
  - Look for: qt, quart, L, liter, gal, gallon, "capacity", "fill to"

TEMPERATURES: operating temps, thermostat ratings, overheat thresholds
  - Look for: °F, °C, "operating temperature"

SPEEDS/FLOW: engine RPM, pump flow, PTO speed
  - Look for: RPM, GPM, LPM, "idle speed", "rated speed"

Return a JSON array. Each spec:
- "category": "torque" | "pressure" | "clearance" | "capacity" | "electrical" | "temperature" | "speed" | "general"
- "component": what it applies to (e.g. "cylinder head bolts", "main relief valve")
- "spec": the exact value with units (e.g. "135 N·m (100 lb-ft)")
- "conditions": any conditions (e.g. "lubricated", "at operating temp", "Stage 1") or null
- "page": the page number

Only include values explicitly stated in the text. Do not guess.
If no specs are found in this text, return an empty array: []

TEXT:
{combined_text}

Return ONLY a JSON array. No markdown, no explanation."""

        try:
            response = await client.messages.create(
                model=settings.DEFAULT_MODEL,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            text_result = response.content[0].text.strip()

            start = text_result.find("[")
            end = text_result.rfind("]") + 1
            if start >= 0 and end > start:
                batch_specs = json.loads(text_result[start:end])
                all_specs.extend(batch_specs)
        except Exception as e:
            logger.warning("Spec extraction failed for batch starting at page %s: %s",
                         batch[0]["page_number"] if batch else "?", e)
            continue

    # Deduplicate specs by component+spec value
    seen = set()
    unique_specs = []
    for s in all_specs:
        key = (s.get("component", "").lower().strip(), s.get("spec", "").lower().strip())
        if key not in seen:
            seen.add(key)
            unique_specs.append(s)

    return {
        "specs": unique_specs,
        "source_pages": source_pages,
        "total": len(unique_specs),
        "pages_analyzed": len(spec_pages),
    }


@router.delete("/{manual_id}")
async def delete_manual(manual_id: UUID, request: Request) -> dict:
    """Delete a manual."""
    # RBAC: owner or manager can delete
    role = getattr(request.state, "user_role", None)
    if role not in (UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only owners and managers can delete manuals")

    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    deleted = await _service.delete_manual(pool, tenant_id, manual_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Manual not found")

    return {"status": "deleted", "id": str(manual_id)}
