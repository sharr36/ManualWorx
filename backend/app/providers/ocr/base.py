"""Abstract base class for OCR providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float


@dataclass
class OCRResult:
    text: str
    confidence: float
    bounding_boxes: list[BoundingBox] = field(default_factory=list)


@dataclass
class TableRow:
    cells: list[str]


@dataclass
class Table:
    headers: list[str]
    rows: list[TableRow]


@dataclass
class LayoutBlock:
    text: str
    block_type: str  # paragraph, heading, list, table, figure
    bbox: BoundingBox | None = None


@dataclass
class LayoutResult:
    blocks: list[LayoutBlock]
    reading_order: list[int]


class OCRProvider(ABC):
    """Abstract OCR provider interface."""

    @abstractmethod
    async def extract_text(self, pdf_bytes: bytes, page_number: int) -> OCRResult:
        """Extract text from a PDF page."""

    @abstractmethod
    async def extract_tables(self, pdf_bytes: bytes, page_number: int) -> list[Table]:
        """Extract tables from a PDF page."""

    @abstractmethod
    async def analyze_layout(self, pdf_bytes: bytes, page_number: int) -> LayoutResult:
        """Analyze page layout and reading order."""
