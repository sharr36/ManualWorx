"""Interactive schematic viewer models."""

from pydantic import BaseModel


class AnnotateRequest(BaseModel):
    page_id: str
    diagram_type: str | None = None


class AnnotationResponse(BaseModel):
    id: str
    page_id: str
    diagram_type: str
    annotation_data: dict
    component_count: int
    confidence_overall: float


class GenerateSchematicRequest(BaseModel):
    manual_id: str
    system_area: str


class LocateComponentRequest(BaseModel):
    machine_model: str
    component_designator: str
    manual_ids: list[str] | None = None


class CompareRequest(BaseModel):
    page_ids: list[str]
    comparison_type: str = "side_by_side"
