"""Manual management service (Phase 1)."""


class ManualService:
    """Handles manual upload, processing status, and metadata."""

    async def upload_manual(self, pool, tenant_id, **kwargs):
        raise NotImplementedError("Phase 1")

    async def get_manual(self, pool, tenant_id, manual_id):
        raise NotImplementedError("Phase 1")

    async def list_manuals(self, pool, tenant_id):
        raise NotImplementedError("Phase 1")

    async def delete_manual(self, pool, tenant_id, manual_id):
        raise NotImplementedError("Phase 1")

    async def update_processing_status(self, pool, manual_id, status, **kwargs):
        raise NotImplementedError("Phase 1")
