"""Document generation service (Phase 4)."""


class DocumentService:
    """Generates PDF/DOCX documents from query responses."""

    async def generate_document(self, pool, tenant_id, query_id, doc_type, format="pdf"):
        raise NotImplementedError("Phase 4")

    async def get_document(self, pool, tenant_id, document_id):
        raise NotImplementedError("Phase 4")
