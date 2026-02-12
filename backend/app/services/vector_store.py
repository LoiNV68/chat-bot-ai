from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from app.core.config import settings
from typing import List, Dict, Any
from app.services.llm_client import LLMClient


class QdrantClientSingleton:
    """Singleton Qdrant Client - tái sử dụng kết nối cho mọi request."""
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_client(cls) -> AsyncQdrantClient:
        if cls._client is None:
            cls._client = AsyncQdrantClient(
                host=settings.QDRANT_HOST, 
                port=settings.QDRANT_PORT,
                timeout=30  # Thời gian chờ kết nối
            )
        return cls._client


class VectorStore:
    """VectorStore tối ưu với singleton Qdrant client."""
    _instance = None
    _collection_checked = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.client = QdrantClientSingleton.get_client()
        self.collection_name = "unimind_docs"
        self.llm_client = LLMClient()
        
        self._initialized = True

    async def _ensure_collection(self):
        # Chỉ kiểm tra một lần trong vòng đời ứng dụng
        if VectorStore._collection_checked:
            return
        try:
            await self.client.get_collection(self.collection_name)
            VectorStore._collection_checked = True
        except Exception:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
            )
            VectorStore._collection_checked = True
        
        # Tạo full-text index cho keyword search (idempotent)
        try:
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="content",
                field_schema=models.TextIndexParams(
                    type="text",
                    tokenizer=models.TokenizerType.WORD,
                    min_token_len=2,
                    max_token_len=20,
                    lowercase=True,
                )
            )
            print("[DEBUG] Full-text index created on 'content' field")
        except Exception:
            pass  # Index đã tồn tại

    async def upsert_vectors(self, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str] = None):
        if not texts:
            return
            
        # Sử dụng async embeddings để không block event loop
        vectors = await self.llm_client.get_embeddings_async(texts)
        
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
        # Sử dụng async embeddings
        query_vector = (await self.llm_client.get_embeddings_async([query]))[0]
        
        await self._ensure_collection()
        # Sử dụng query_points cho các phiên bản qdrant-client mới hơn
        try:
            return (await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                query_filter=models.Filter(**filter_dict) if filter_dict else None
            )).points
        except AttributeError:
            # Fallback cho các phiên bản qdrant-client cũ hơn
            return await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=models.Filter(**filter_dict) if filter_dict else None
            )

    async def keyword_search(self, keywords: List[str], limit: int = 10, filter_dict: Dict = None):
        """
        Tìm kiếm theo từ khóa chính xác trong content payload.
        Dùng Qdrant scroll với payload filtering.
        """
        await self._ensure_collection()
        
        all_results = []
        
        for keyword in keywords:
            try:
                # Xây dựng filter: keyword match + base filters
                must_conditions = [
                    models.FieldCondition(
                        key="content",
                        match=models.MatchText(text=keyword)
                    )
                ]
                
                # Thêm base filter conditions (is_active, scope, etc.)
                if filter_dict:
                    if "must" in filter_dict:
                        for cond in filter_dict["must"]:
                            must_conditions.append(
                                models.FieldCondition(
                                    key=cond["key"],
                                    match=models.MatchValue(value=cond["match"]["value"])
                                )
                            )
                
                should_conditions = []
                if filter_dict and "should" in filter_dict:
                    for cond in filter_dict["should"]:
                        should_conditions.append(
                            models.FieldCondition(
                                key=cond["key"],
                                match=models.MatchValue(value=cond["match"]["value"])
                            )
                        )
                
                scroll_filter = models.Filter(
                    must=must_conditions,
                    should=should_conditions if should_conditions else None
                )
                
                results, _ = await self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=scroll_filter,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False
                )
                
                all_results.extend(results)
                print(f"[DEBUG] Keyword '{keyword}': found {len(results)} matches")
                
            except Exception as e:
                print(f"[DEBUG] Keyword search error for '{keyword}': {e}")
        
        # Deduplicate by point id
        seen_ids = set()
        unique_results = []
        for r in all_results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                unique_results.append(r)
        
        return unique_results

    async def hybrid_search(self, query: str, keywords: List[str], limit: int = 20, filter_dict: Dict = None):
        """
        Hybrid Search: kết hợp semantic search + keyword search.
        Ưu tiên keyword matches, sau đó bổ sung bằng semantic results.
        """
        import asyncio
        
        semantic_task = self.search(query, limit=limit, filter_dict=filter_dict)
        keyword_task = self.keyword_search(keywords, limit=limit, filter_dict=filter_dict)
        
        semantic_results, keyword_results = await asyncio.gather(semantic_task, keyword_task)
        
        print(f"[DEBUG] Hybrid: {len(semantic_results)} semantic + {len(keyword_results)} keyword results")
        
        # Wrapper class cho kết quả thống nhất
        class SearchHit:
            def __init__(self, id, payload, score):
                self.id = id
                self.payload = payload
                self.score = score
        
        seen_ids = set()
        merged = []
        
        # Keyword matches đầu tiên (chính xác hơn, score cao)
        for r in keyword_results:
            rid = str(r.id)
            if rid not in seen_ids:
                seen_ids.add(rid)
                merged.append(SearchHit(id=r.id, payload=r.payload, score=0.95))
        
        # Semantic results bổ sung
        for r in semantic_results:
            rid = str(r.id)
            if rid not in seen_ids:
                seen_ids.add(rid)
                merged.append(SearchHit(id=r.id, payload=r.payload, score=r.score if hasattr(r, 'score') else 0))
        
        # Sort by score descending
        merged.sort(key=lambda x: x.score, reverse=True)
        
        return merged[:limit]



    async def set_document_active(self, doc_id: int, is_active: bool):
        """
        Cập nhật trạng thái is_active của tất cả vectors thuộc về document.
        Dùng khi delete (is_active=False) hoặc restore (is_active=True).
        """
        await self._ensure_collection()
        
        try:
            # Cập nhật payload cho tất cả points có doc_id tương ứng
            await self.client.set_payload(
                collection_name=self.collection_name,
                payload={"is_active": is_active},
                points=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(value=doc_id)
                        )
                    ]
                )
            )
            print(f"[DEBUG] Qdrant: Updated is_active={is_active} for doc_id={doc_id}")
            return True
        except Exception as e:
            print(f"[DEBUG] Qdrant update failed for doc_id={doc_id}: {e}")
            return False

    async def delete_document_vectors(self, doc_id: int):
        """
        Xóa hoàn toàn tất cả vectors thuộc về document (hard delete).
        """
        await self._ensure_collection()
        
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="doc_id",
                                match=models.MatchValue(value=doc_id)
                            )
                        ]
                    )
                )
            )
            print(f"[DEBUG] Qdrant: Deleted all vectors for doc_id={doc_id}")
            return True
        except Exception as e:
            print(f"[DEBUG] Qdrant delete failed for doc_id={doc_id}: {e}")
            return False

