"""Together.ai embedding provider."""

import httpx

from .base import EmbeddingProvider

TOGETHER_EMBED_URL = "https://api.together.xyz/v1/embeddings"
TOGETHER_MODEL = "togethercomputer/m2-bert-80M-8k-retrieval"
EMBED_DIMENSION = 768


class TogetherEmbeddingProvider(EmbeddingProvider):
    """Embedding via Together.ai API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def embed_text(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                TOGETHER_EMBED_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": TOGETHER_MODEL, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()

        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings

    def dimension(self) -> int:
        return EMBED_DIMENSION
