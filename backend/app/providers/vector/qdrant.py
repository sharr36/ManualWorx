"""Qdrant vector store provider."""

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .base import SearchResult, VectorProvider


class QdrantVectorProvider(VectorProvider):
    """Vector storage and search via Qdrant with tenant_id payload filtering."""

    def __init__(self, url: str):
        self.client = AsyncQdrantClient(url=url)

    async def create_collection(self, name: str, dimension: int) -> None:
        collections = await self.client.get_collections()
        existing = {c.name for c in collections.collections}
        if name not in existing:
            await self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )

    async def upsert(self, collection: str, id: str, vector: list[float], payload: dict) -> None:
        await self.client.upsert(
            collection_name=collection,
            points=[PointStruct(id=id, vector=vector, payload=payload)],
        )

    async def search(
        self, collection: str, vector: list[float], filter: dict | None = None, top_k: int = 10
    ) -> list[SearchResult]:
        query_filter = None
        if filter:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            conditions = []
            for key, value in filter.items():
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            query_filter = Filter(must=conditions)

        results = await self.client.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=query_filter,
            limit=top_k,
        )

        return [
            SearchResult(
                id=str(hit.id),
                score=hit.score,
                payload=hit.payload or {},
            )
            for hit in results
        ]

    async def delete(self, collection: str, ids: list[str]) -> None:
        from qdrant_client.models import PointIdsList

        await self.client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=ids),
        )
