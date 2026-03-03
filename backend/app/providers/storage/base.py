"""Abstract base class for object storage providers."""

from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Abstract object storage interface."""

    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload a file and return its URL."""

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download a file by key."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a file by key."""

    @abstractmethod
    async def get_url(self, key: str) -> str:
        """Get a pre-signed or public URL for a file."""
