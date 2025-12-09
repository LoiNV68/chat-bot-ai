from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.core.config import settings
from typing import List, Dict, Any

class VectorStore:
    def __init__(self):
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.collection_name = "unimind_docs"
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
            )

    def upsert_vectors(self, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str] = None):
        from langchain_community.embeddings import OllamaEmbeddings
        
        embeddings_model = OllamaEmbeddings(
            base_url=settings.OLLAMA_BASE_URL,
            model="nomic-embed-text"
        )
        
        vectors = embeddings_model.embed_documents(texts)
        
        points = [
            models.PointStruct(
                id=ids[i] if ids else None,
                vector=vectors[i],
                payload=metadatas[i]
            )
            for i in range(len(texts))
        ]
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
    def search(self, query_vector: List[float], limit: int = 5, filter_dict: Dict = None):
        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=models.Filter(**filter_dict) if filter_dict else None
        )
