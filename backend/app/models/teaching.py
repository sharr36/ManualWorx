"""Teaching mode and learning models."""

from pydantic import BaseModel

from manualworx_shared.constants import SkillLevel, TeachDepth


class TeachRequest(BaseModel):
    manual_id: str
    system_area: str
    depth: TeachDepth = TeachDepth.STANDARD


class AssistRequest(BaseModel):
    problem_description: str
    machine_model: str | None = None
    manual_ids: list[str] | None = None


class QuizGenerateRequest(BaseModel):
    learning_path_id: str
    module_index: int
    count: int = 5


class QuizSubmitRequest(BaseModel):
    learning_path_id: str
    module_index: int
    answers: dict[str, str]


class LearningPathResponse(BaseModel):
    id: str
    title: str
    system_area: str
    modules: list[dict]
    auto_generated: bool


class ProgressResponse(BaseModel):
    learning_path_id: str
    mechanic_id: str
    completed_modules: int
    total_modules: int
    quiz_scores: list[dict] | None
