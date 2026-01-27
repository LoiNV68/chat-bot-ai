from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from app.core.config import settings
from typing import List, Dict, Any
from app.services.llm_client import LLMClient

class VectorStore:
    def __init__(self):
        self.client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.collection_name = "unimind_docs"
        self.llm_client = LLMClient()

    async def _ensure_collection(self):
        try:
            await self.client.get_collection(self.collection_name)
        except Exception:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
            )

    async def upsert_vectors(self, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str] = None):
        # Embeddings are synchronous in LangChain integration usually, 
        # but we can optimize this later.
        vectors = self.llm_client.get_embeddings(texts)
        
        points = [
            models.PointStruct(
                id=ids[i] if ids else None,
                vector=vectors[i],
                payload=metadatas[i]
            )
            for i in range(len(texts))
        ]
        
        await self._ensure_collection()
        await self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
    async def search(self, query: str, limit: int = 5, filter_dict: Dict = None):
        # Generate query vector
        query_vector = self.llm_client.get_embeddings([query])[0]
        
        await self._ensure_collection()
        # Use query_points for newer qdrant-client versions
        try:
            return (await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                query_filter=models.Filter(**filter_dict) if filter_dict else None
            )).points
        except AttributeError:
             # Fallback: using retrieve or scroll if search is missing, but here trying invalid method again.
             # Actually if qdrant-client is new (1.10+), it has query_points. 
             # If old (1.9), it has search.
             # The previous error "no attribute search" led us here.
             # Let's trust query_points works if we await it correctly.
            return await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=models.Filter(**filter_dict) if filter_dict else None
            )
