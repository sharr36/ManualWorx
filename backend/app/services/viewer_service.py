"""Interactive schematic viewer service (Phase 5)."""


class ViewerService:
    """Handles diagram annotation, schematic generation, and component location."""

    async def annotate_diagram(self, pool, tenant_id, page_id, diagram_type=None):
        raise NotImplementedError("Phase 5")

    async def get_annotations(self, pool, tenant_id, page_id):
        raise NotImplementedError("Phase 5")

    async def get_operating_states(self, pool, tenant_id, page_id):
        raise NotImplementedError("Phase 5")

    async def generate_schematic(self, pool, tenant_id, manual_id, system_area):
        raise NotImplementedError("Phase 5")

    async def locate_component(self, pool, tenant_id, machine_model, component_designator):
        raise NotImplementedError("Phase 5")

    async def compare_diagrams(self, pool, tenant_id, page_ids):
        raise NotImplementedError("Phase 5")
