"""Abstract base class for embedding providers."""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract embedding provider interface."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings."""

    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
