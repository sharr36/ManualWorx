"""Teaching mode service (Phase 8)."""


class TeachingService:
    """Handles teach-then-troubleshoot flow, lessons, quizzes, and learning paths."""

    async def explain_system(self, pool, tenant_id, manual_id, system_area, depth="standard"):
        raise NotImplementedError("Phase 8")

    async def start_assist(self, pool, tenant_id, problem_description, **kwargs):
        raise NotImplementedError("Phase 8")

    async def generate_quiz(self, pool, tenant_id, learning_path_id, module_index, count=5):
        raise NotImplementedError("Phase 8")

    async def submit_quiz(self, pool, tenant_id, learning_path_id, module_index, answers):
        raise NotImplementedError("Phase 8")

    async def generate_learning_path(self, pool, tenant_id, manual_id):
        raise NotImplementedError("Phase 8")

    async def get_mechanic_dashboard(self, pool, tenant_id, mechanic_id):
        raise NotImplementedError("Phase 8")
