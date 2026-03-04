"""Document generation service — creates PDF/DOCX from query responses."""

import io
import json
import time
from datetime import datetime
from uuid import UUID, uuid4

import anthropic
import asyncpg

from ..config import settings
from ..database import set_tenant_context
from ..providers import get_storage_provider


DOC_TEMPLATES = {
    "troubleshooting_guide": {
        "title": "Troubleshooting Guide",
        "prompt": """Create a structured troubleshooting guide from this query and response.

QUERY: {query_text}
RESPONSE: {response_text}
SOURCES: {sources}

Format the guide as:
# Troubleshooting Guide: [Problem Title]

## Problem Description
[Clear description of the reported issue]

## Possible Causes
[Numbered list of causes ranked by likelihood]

## Diagnostic Steps
[Numbered step-by-step diagnostic procedure]

## Repair Procedures
[For each cause, the repair steps with specs]

## Parts & Specifications
[Relevant part numbers, torque specs, pressures]

## Safety Warnings
[Any safety-critical information]

## References
[Page citations from the source manuals]""",
    },
    "service_procedure": {
        "title": "Service Procedure",
        "prompt": """Create a formal service procedure document from this query and response.

QUERY: {query_text}
RESPONSE: {response_text}
SOURCES: {sources}

Format as:
# Service Procedure: [Task Title]

## Prerequisites
[Tools, parts, safety equipment needed]

## Safety Precautions
[All warnings and cautions]

## Procedure Steps
[Detailed numbered steps with specifications]

## Specifications Table
| Parameter | Value | Tolerance |
[Relevant specs in table format]

## Verification
[How to verify the procedure was successful]

## References
[Page citations]""",
    },
    "quick_reference": {
        "title": "Quick Reference Card",
        "prompt": """Create a concise quick reference card from this query and response.

QUERY: {query_text}
RESPONSE: {response_text}
SOURCES: {sources}

Format as a compact reference:
# Quick Reference: [Topic]

## Key Specifications
[Table of critical values]

## Quick Steps
[Abbreviated procedure steps]

## Warnings
[Critical safety notes only]

Keep it to one page equivalent — concise and scannable.""",
    },
    "parts_reference": {
        "title": "Parts Reference",
        "prompt": """Create a parts reference document from this query and response.

QUERY: {query_text}
RESPONSE: {response_text}
SOURCES: {sources}

Format as:
# Parts Reference: [System/Component]

## Component List
| Part Number | Description | Qty | Notes |
[Parts mentioned in the response]

## Assembly Notes
[Key assembly/disassembly information]

## Torque Specifications
[Relevant torque values]

## References
[Page citations]""",
    },
    "system_analysis": {
        "title": "System Analysis Report",
        "prompt": """Create a comprehensive system analysis report from this query and response.

QUERY: {query_text}
RESPONSE: {response_text}
SOURCES: {sources}

Format as:
# System Analysis Report

## System Overview
[Description of the system being analyzed]

## Component Inventory
| Component | Type | Designator | Confidence |
[All components identified in this system]

## Documentation Coverage
[What documentation exists vs. what is missing]

## Specification Summary
[Key specifications found with source pages]

## Cross-References
[Related systems and component interactions]

## Identified Gaps
[Missing information that could impact service quality]

## Recommendations
[Suggested actions to improve documentation coverage]

## Confidence Assessment
[Overall confidence in the analysis with per-area breakdown]

## References
[Page citations from source manuals]""",
    },
    "gap_report": {
        "title": "Documentation Gap Report",
        "prompt": """Create a documentation gap analysis report from this query and response.

QUERY: {query_text}
RESPONSE: {response_text}
SOURCES: {sources}

Format as:
# Documentation Gap Report

## Executive Summary
[Brief overview of documentation completeness]

## Coverage Score
[Overall coverage percentage and rating]

## Critical Gaps
[High-impact missing documentation — safety, spec, and procedure gaps]

## Moderate Gaps
[Medium-impact missing documentation]

## Minor Gaps
[Low-impact missing items or improvements]

## Coverage by System Area
| System Area | Specs | Procedures | Diagrams | Troubleshooting | Score |
[Coverage matrix for each system area]

## Impact Assessment
[How gaps affect mechanic ability to service equipment]

## Remediation Plan
[Prioritized steps to fill documentation gaps]

## References
[Page citations from analyzed manuals]""",
    },
}

# Fallback template for types without a specific template
DEFAULT_TEMPLATE = {
    "title": "Document",
    "prompt": """Create a well-structured document from this query and response.

QUERY: {query_text}
RESPONSE: {response_text}
SOURCES: {sources}

Format it professionally with clear headings, bullet points for lists,
and tables for specifications. Include page citations.""",
}


class DocumentService:
    """Generates PDF/DOCX documents from query responses using Claude."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.storage = get_storage_provider()

    async def generate_document(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        query_id: str,
        doc_type: str,
        doc_format: str = "pdf",
    ) -> dict:
        """Generate a document from a query response.

        Steps:
        1. Fetch the query and response from DB
        2. Use Claude to format into structured document content
        3. Render as PDF or DOCX
        4. Upload to storage
        5. Store document record in DB

        Returns:
            Document dict with id, file_url, etc.
        """
        start = time.monotonic()

        # 1. Fetch the original query
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            query_row = await conn.fetchrow(
                """
                SELECT id, query_text, query_mode, response_text,
                       retrieved_page_ids, manual_ids
                FROM queries
                WHERE id = $1 AND tenant_id = $2
                """,
                UUID(query_id),
                tenant_id,
            )

        if not query_row:
            raise ValueError("Query not found")

        # Fetch source page info for citations
        sources_text = ""
        if query_row["retrieved_page_ids"]:
            async with pool.acquire() as conn:
                pages = await conn.fetch(
                    """
                    SELECT p.page_number, p.classification,
                           LEFT(p.extracted_text, 300) as text_preview,
                           m.title as manual_title
                    FROM pages p
                    JOIN manuals m ON p.manual_id = m.id
                    WHERE p.id = ANY($1::uuid[])
                    ORDER BY p.page_number
                    """,
                    query_row["retrieved_page_ids"][:10],
                )
                sources_text = "\n".join(
                    f"Page {p['page_number']+1} [{p['classification']}] from \"{p['manual_title']}\": {p['text_preview']}"
                    for p in pages
                )

        # 2. Generate formatted document content using Claude
        template = DOC_TEMPLATES.get(doc_type, DEFAULT_TEMPLATE)
        prompt = template["prompt"].format(
            query_text=query_row["query_text"],
            response_text=query_row["response_text"] or "",
            sources=sources_text or "No source pages available.",
        )

        response = await self.client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=4096,
            system="You are a technical document generator for heavy equipment service manuals. Create professional, well-structured documents with accurate specifications and clear formatting. Use markdown formatting.",
            messages=[{"role": "user", "content": prompt}],
        )

        doc_content = response.content[0].text

        # 3. Render to PDF or DOCX
        if doc_format == "pdf":
            file_bytes = self._render_pdf(doc_content, template["title"])
            content_type = "application/pdf"
            extension = "pdf"
        else:
            file_bytes = self._render_docx(doc_content, template["title"])
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            extension = "docx"

        # 4. Upload to storage
        doc_id = uuid4()
        storage_key = f"documents/{tenant_id}/{doc_id}.{extension}"
        await self.storage.upload(storage_key, file_bytes, content_type)

        # 5. Store document record
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            await conn.execute(
                """
                INSERT INTO documents (id, tenant_id, query_id, doc_type, format, file_url)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                doc_id,
                tenant_id,
                UUID(query_id),
                doc_type,
                doc_format,
                storage_key,
            )

        latency_ms = int((time.monotonic() - start) * 1000)

        return {
            "id": str(doc_id),
            "query_id": query_id,
            "doc_type": doc_type,
            "format": doc_format,
            "file_url": storage_key,
            "latency_ms": latency_ms,
            "created_at": datetime.now().isoformat(),
        }

    async def get_document(
        self, pool: asyncpg.Pool, tenant_id: UUID, document_id: UUID
    ) -> dict | None:
        """Retrieve a document record."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            row = await conn.fetchrow(
                """
                SELECT d.id, d.query_id, d.doc_type, d.format, d.file_url, d.created_at,
                       q.query_text
                FROM documents d
                LEFT JOIN queries q ON d.query_id = q.id
                WHERE d.id = $1 AND d.tenant_id = $2
                """,
                document_id,
                tenant_id,
            )

        if not row:
            return None

        return {
            "id": str(row["id"]),
            "query_id": str(row["query_id"]) if row["query_id"] else None,
            "doc_type": row["doc_type"],
            "format": row["format"],
            "file_url": row["file_url"],
            "query_text": row["query_text"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    async def list_documents(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        doc_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """List documents for a tenant, optionally filtered by type."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            if doc_type:
                rows = await conn.fetch(
                    """
                    SELECT d.id, d.query_id, d.doc_type, d.format, d.file_url, d.created_at,
                           q.query_text
                    FROM documents d
                    LEFT JOIN queries q ON d.query_id = q.id
                    WHERE d.tenant_id = $1 AND d.doc_type = $2
                    ORDER BY d.created_at DESC
                    LIMIT $3 OFFSET $4
                    """,
                    tenant_id,
                    doc_type,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT d.id, d.query_id, d.doc_type, d.format, d.file_url, d.created_at,
                           q.query_text
                    FROM documents d
                    LEFT JOIN queries q ON d.query_id = q.id
                    WHERE d.tenant_id = $1
                    ORDER BY d.created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    tenant_id,
                    limit,
                    offset,
                )

        return [
            {
                "id": str(r["id"]),
                "query_id": str(r["query_id"]) if r["query_id"] else None,
                "doc_type": r["doc_type"],
                "format": r["format"],
                "file_url": r["file_url"],
                "query_text": r["query_text"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

    async def get_download_url(
        self, pool: asyncpg.Pool, tenant_id: UUID, document_id: UUID
    ) -> str | None:
        """Get a pre-signed download URL for a document."""
        doc = await self.get_document(pool, tenant_id, document_id)
        if not doc or not doc["file_url"]:
            return None

        return await self.storage.get_url(doc["file_url"])

    async def delete_document(
        self, pool: asyncpg.Pool, tenant_id: UUID, document_id: UUID
    ) -> bool:
        """Delete a document and its storage file."""
        doc = await self.get_document(pool, tenant_id, document_id)
        if not doc:
            return False

        # Delete from storage
        if doc["file_url"]:
            try:
                await self.storage.delete(doc["file_url"])
            except Exception:
                pass

        # Delete from DB
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            await conn.execute(
                "DELETE FROM documents WHERE id = $1 AND tenant_id = $2",
                document_id,
                tenant_id,
            )

        return True

    def _render_pdf(self, markdown_content: str, title: str) -> bytes:
        """Render markdown content to a PDF.

        Uses a simple text-based approach since we don't want heavy
        dependencies like WeasyPrint. Creates a clean, readable PDF
        using fpdf2 (lightweight, pure Python).
        """
        try:
            from fpdf import FPDF
        except ImportError:
            # Fallback: return markdown as plain text PDF
            return self._render_text_pdf(markdown_content, title)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 6, f"Generated by ManualWorx on {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

        # Parse markdown lines
        for line in markdown_content.split("\n"):
            stripped = line.strip()

            if not stripped:
                pdf.ln(3)
                continue

            if stripped.startswith("# "):
                pdf.set_font("Helvetica", "B", 14)
                pdf.multi_cell(0, 7, stripped[2:])
                pdf.ln(2)
            elif stripped.startswith("## "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 6, stripped[3:])
                pdf.ln(1)
            elif stripped.startswith("### "):
                pdf.set_font("Helvetica", "B", 10)
                pdf.multi_cell(0, 6, stripped[4:])
            elif stripped.startswith("| "):
                # Table row
                pdf.set_font("Courier", "", 8)
                pdf.multi_cell(0, 4, stripped)
            elif stripped.startswith("- ") or stripped.startswith("* "):
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(5, 5, "")
                pdf.multi_cell(0, 5, f"\u2022 {stripped[2:]}")
            elif stripped[0].isdigit() and ". " in stripped[:4]:
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, stripped)
            else:
                # Clean bold markers
                clean = stripped.replace("**", "")
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, clean)

        return pdf.output()

    def _render_text_pdf(self, content: str, title: str) -> bytes:
        """Minimal fallback PDF — just encode text as UTF-8 content."""
        # This is a very basic PDF structure
        header = f"{title}\nGenerated by ManualWorx on {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{'='*60}\n\n"
        full = header + content
        return full.encode("utf-8")

    def _render_docx(self, markdown_content: str, title: str) -> bytes:
        """Render markdown content to a DOCX file."""
        try:
            from docx import Document
            from docx.shared import Pt, Inches
        except ImportError:
            # Fallback to plain text
            return (f"{title}\n\n{markdown_content}").encode("utf-8")

        doc = Document()

        # Title
        doc.add_heading(title, level=0)
        doc.add_paragraph(
            f"Generated by ManualWorx on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            style="Subtitle",
        )

        for line in markdown_content.split("\n"):
            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith("# "):
                doc.add_heading(stripped[2:], level=1)
            elif stripped.startswith("## "):
                doc.add_heading(stripped[3:], level=2)
            elif stripped.startswith("### "):
                doc.add_heading(stripped[4:], level=3)
            elif stripped.startswith("- ") or stripped.startswith("* "):
                doc.add_paragraph(stripped[2:], style="List Bullet")
            elif stripped[0].isdigit() and ". " in stripped[:4]:
                doc.add_paragraph(stripped, style="List Number")
            elif stripped.startswith("| "):
                # Simple table rendering
                p = doc.add_paragraph()
                run = p.add_run(stripped)
                run.font.size = Pt(8)
                run.font.name = "Courier New"
            else:
                clean = stripped.replace("**", "")
                doc.add_paragraph(clean)

        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()
