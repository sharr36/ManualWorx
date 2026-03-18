"""Interactive schematic viewer models."""

from pydantic import BaseModel


class AnnotateRequest(BaseModel):
    page_id: str
    diagram_type: str | None = None
    force: bool = False


class AnnotationResponse(BaseModel):
    id: str
    page_id: str
    diagram_type: str
    annotation_data: dict
    component_count: int
    connection_count: int = 0
    operating_states: list[dict] = []
    confidence_overall: float
    generated_at: str | None = None
    verified: bool = False
    cached: bool = False


class DiagramPageItem(BaseModel):
    page_id: str
    manual_id: str
    page_number: int
    classification: str
    manual_title: str
    annotated: bool
    component_count: int = 0
    confidence: float | None = None


class GenerateSchematicRequest(BaseModel):
    manual_id: str
    system_area: str


class GenerateSchematicResponse(BaseModel):
    id: str
    manual_id: str
    system_area: str
    diagram_dsl: dict
    component_count: int
    confidence_overall: float
    disclaimer: str = "AI-GENERATED — NOT FROM OEM MANUAL"
    created_at: str | None = None


class LocateComponentRequest(BaseModel):
    machine_model: str
    component_designator: str
    manual_ids: list[str] | None = None


class LocateComponentResponse(BaseModel):
    id: str | None = None
    machine_model: str
    component_designator: str
    component_type: str = "unknown"
    location_description: str = ""
    access_notes: str = ""
    source: str = ""
    confidence: float = 0.0
    reference_pages: list[int] = []
    cached: bool = False


class CompareRequest(BaseModel):
    page_ids: list[str]
    comparison_type: str = "side_by_side"


class OperatingState(BaseModel):
    id: str
    name: str
    description: str = ""
    active_components: list[str] = []
    flow_paths: list[dict] = []
