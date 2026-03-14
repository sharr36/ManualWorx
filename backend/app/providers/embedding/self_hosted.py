"""Self-hosted embedding provider (internal GPU service)."""

import httpx

from .base import EmbeddingProvider

EMBED_DIMENSION = 1024


class SelfHostedEmbeddingProvider(EmbeddingProvider):
    """Embedding via a self-hosted HTTP service."""

    def __init__(self, service_url: str):
        self.service_url = service_url.rstrip("/")

    async def embed_text(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.service_url}/embed",
                json={"texts": texts},
            )
            resp.raise_for_status()
            data = resp.json()

        return data["embeddings"]

    def dimension(self) -> int:
        return EMBED_DIMENSION
