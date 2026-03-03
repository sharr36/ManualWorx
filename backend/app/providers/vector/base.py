"""Abstract base class for vector store providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    id: str
    score: float
    payload: dict


class VectorProvider(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    async def create_collection(self, name: str, dimension: int) -> None:
        """Create a vector collection."""

    @abstractmethod
    async def upsert(self, collection: str, id: str, vector: list[float], payload: dict) -> None:
        """Insert or update a vector."""

    @abstractmethod
    async def search(
        self, collection: str, vector: list[float], filter: dict | None = None, top_k: int = 10
    ) -> list[SearchResult]:
        """Search for similar vectors."""

    @abstractmethod
    async def delete(self, collection: str, ids: list[str]) -> None:
        """Delete vectors by ID."""
