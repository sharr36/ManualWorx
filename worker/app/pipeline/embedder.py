"""Embedding pipeline — generates vectors for text chunks and stores in Qdrant."""

import uuid

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

TOGETHER_EMBED_URL = "https://api.together.xyz/v1/embeddings"
TOGETHER_MODEL = "intfloat/multilingual-e5-large-instruct"


class Embedder:
    """Batch embed text chunks via Together.ai and upsert to Qdrant."""

    def __init__(
        self,
        qdrant: AsyncQdrantClient,
        together_api_key: str,
        batch_size: int = 32,
    ):
        self.qdrant = qdrant
        self.api_key = together_api_key
        self.batch_size = batch_size

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Call Together.ai embedding API for a batch of texts."""
        import logging

        logger = logging.getLogger(__name__)

        # Truncate any texts that exceed the model's token limit (~512 tokens ≈ ~2k chars)
        max_chars = 2_000
        truncated = [t[:max_chars] if len(t) > max_chars else t for t in texts]

        if not self.api_key:
            raise ValueError(
                "TOGETHER_API_KEY is empty — set it via fly secrets set TOGETHER_API_KEY=<key>"
            )

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                TOGETHER_EMBED_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": TOGETHER_MODEL, "input": truncated},
            )
            if resp.status_code != 200:
                logger.error(
                    "Together.ai embedding API error %d (key starts with %s...): %s",
                    resp.status_code,
                    self.api_key[:8] if self.api_key else "EMPTY",
                    resp.text[:500],
                )
                resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["data"]]

    async def embed_and_store(
        self,
        chunks: list[dict],
        collection: str,
        tenant_id: str,
        manual_id: str,
    ) -> list[dict]:
        """Embed chunks and upsert to Qdrant.

        Args:
            chunks: List of dicts with keys: chunk_id (or id), chunk_text, page_id,
                    page_number, chunk_index, classification.
            collection: Qdrant collection name.
            tenant_id: Tenant ID for payload filtering.
            manual_id: Manual ID for payload filtering.

        Returns:
            List of {chunk_id, vector_id} dicts for DB updates.
        """
        if not chunks:
            return []

        results = []
        # Process in batches
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            texts = [c["chunk_text"] for c in batch]

            # Embed
            vectors = await self._embed_batch(texts)

            # Build points and upsert
            points = []
            for chunk, vector in zip(batch, vectors):
                vector_id = str(uuid.uuid4())
                chunk_id = chunk.get("chunk_id") or chunk.get("id", str(uuid.uuid4()))

                points.append(
                    PointStruct(
                        id=vector_id,
                        vector=vector,
                        payload={
                            "tenant_id": tenant_id,
                            "manual_id": manual_id,
                            "page_id": str(chunk.get("page_id", "")),
                            "chunk_id": str(chunk_id),
                            "page_number": chunk.get("page_number", 0),
                            "chunk_index": chunk.get("chunk_index", 0),
                            "classification": chunk.get("classification", "text"),
                        },
                    )
                )

                results.append({
                    "chunk_id": str(chunk_id),
                    "vector_id": vector_id,
                })

            await self.qdrant.upsert(
                collection_name=collection,
                points=points,
            )

        return results
