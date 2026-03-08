from __future__ import annotations

from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.core.config import settings
from app.services.llm_client import LLMClient
from app.services.text_normalization import fold_text_for_search


class QdrantClientSingleton:
    _instance = None
    _client: AsyncQdrantClient | None = None

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
                timeout=30,
            )
        return cls._client


class VectorStore:
    _instance = None
    _collection_checked = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.client = QdrantClientSingleton.get_client()
        self.collection_name = "unimind_docs"
        self.llm_client = LLMClient()
        self._initialized = True

    def _is_invalid_query_vector(self, vector: list[float]) -> bool:
        if not isinstance(vector, (list, tuple)) or not vector:
            return True
        try:
            return not any(abs(float(v)) > 1e-9 for v in vector)
        except Exception:
            return True

    async def _ensure_collection(self):
        if VectorStore._collection_checked:
            return

        try:
            await self.client.get_collection(self.collection_name)
        except Exception:
            try:
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
                )
            except Exception:
                pass

        index_configs: list[tuple[str, Any]] = [
            (
                "content",
                models.TextIndexParams(
                    type="text",
                    tokenizer=models.TokenizerType.WORD,
                    min_token_len=2,
                    max_token_len=32,
                    lowercase=True,
                ),
            ),
            (
                "content_folded",
                models.TextIndexParams(
                    type="text",
                    tokenizer=models.TokenizerType.WORD,
                    min_token_len=2,
                    max_token_len=32,
                    lowercase=True,
                ),
            ),
            (
                "title",
                models.TextIndexParams(
                    type="text",
                    tokenizer=models.TokenizerType.WORD,
                    min_token_len=2,
                    max_token_len=40,
                    lowercase=True,
                ),
            ),
            ("doc_id", models.PayloadSchemaType.INTEGER),
            ("version", models.PayloadSchemaType.INTEGER),
            ("is_active", models.PayloadSchemaType.BOOL),
            ("access_scope", models.PayloadSchemaType.KEYWORD),
            ("target_id", models.PayloadSchemaType.KEYWORD),
            ("source", models.PayloadSchemaType.KEYWORD),
            ("content_type", models.PayloadSchemaType.KEYWORD),
            ("chunk_type", models.PayloadSchemaType.KEYWORD),
            ("chunk_id", models.PayloadSchemaType.KEYWORD),
            ("doc_number", models.PayloadSchemaType.KEYWORD),
            ("issuer", models.PayloadSchemaType.KEYWORD),
            ("doc_type", models.PayloadSchemaType.KEYWORD),
            ("topic", models.PayloadSchemaType.KEYWORD),
            ("date", models.PayloadSchemaType.KEYWORD),
        ]

        for field_name, schema in index_configs:
            try:
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception:
                pass

        VectorStore._collection_checked = True
        print("[vector] collection + payload indexes ready")

    async def upsert_vectors(self, texts: list[str], metadatas: list[dict[str, Any]], ids: list[str] | None = None):
        if not texts:
            return

        if len(texts) != len(metadatas):
            raise ValueError("texts/metadatas length mismatch")
        if ids and len(ids) != len(texts):
            raise ValueError("ids/texts length mismatch")

        await self._ensure_collection()

        vectors = await self.llm_client.get_embeddings_async(texts)
        batch_size = 32
        for start in range(0, len(texts), batch_size):
            end = min(start + batch_size, len(texts))
            points = [
                models.PointStruct(
                    id=(ids[idx] if ids else None),
                    vector=vectors[idx],
                    payload=metadatas[idx],
                )
                for idx in range(start, end)
            ]
            await self.client.upsert(collection_name=self.collection_name, points=points)

    async def search(self, query: str, limit: int = 5, filter_dict: dict | None = None):
        query_vector = (await self.llm_client.get_embeddings_async([query]))[0]
        if self._is_invalid_query_vector(query_vector):
            print("[vector] semantic search skipped: empty query vector")
            return []

        await self._ensure_collection()
        q_filter = models.Filter(**filter_dict) if filter_dict else None

        try:
            result = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                query_filter=q_filter,
            )
            return result.points
        except AttributeError:
            return await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=q_filter,
            )

    def _build_match_object(self, match_dict: dict[str, Any]):
        if not isinstance(match_dict, dict):
            return None

        if "value" in match_dict:
            return models.MatchValue(value=match_dict["value"])

        if "text" in match_dict:
            return models.MatchText(text=str(match_dict["text"]))

        if "any" in match_dict:
            any_values = match_dict["any"]
            if isinstance(any_values, (list, tuple, set)):
                values = list(any_values)
                if not values:
                    return None
                try:
                    return models.MatchAny(any=values)
                except Exception:
                    return models.MatchValue(value=values[0])
            if any_values is not None:
                return models.MatchValue(value=any_values)
            return None

        return None

    def _build_field_condition(self, cond: dict[str, Any]):
        if not isinstance(cond, dict):
            return None
        key = cond.get("key")
        match = self._build_match_object(cond.get("match", {}))
        if not key or match is None:
            return None
        return models.FieldCondition(key=key, match=match)

    async def keyword_search(self, keywords: list[str], limit: int = 10, filter_dict: dict | None = None):
        await self._ensure_collection()

        all_results = []
        for keyword in keywords:
            if not keyword:
                continue

            field_queries: list[tuple[str, str]] = [("content", keyword), ("title", keyword)]
            folded = fold_text_for_search(keyword)
            if folded and folded != keyword.lower().strip():
                field_queries.append(("content_folded", folded))

            for field_name, term in field_queries:
                try:
                    must_conditions = [models.FieldCondition(key=field_name, match=models.MatchText(text=term))]

                    if filter_dict and "must" in filter_dict:
                        for cond in filter_dict["must"]:
                            field_condition = self._build_field_condition(cond)
                            if field_condition:
                                must_conditions.append(field_condition)

                    should_conditions = []
                    if filter_dict and "should" in filter_dict:
                        for cond in filter_dict["should"]:
                            field_condition = self._build_field_condition(cond)
                            if field_condition:
                                should_conditions.append(field_condition)

                    must_not_conditions = []
                    if filter_dict and "must_not" in filter_dict:
                        for cond in filter_dict["must_not"]:
                            field_condition = self._build_field_condition(cond)
                            if field_condition:
                                must_not_conditions.append(field_condition)

                    scroll_filter = models.Filter(
                        must=must_conditions,
                        should=should_conditions if should_conditions else None,
                        must_not=must_not_conditions if must_not_conditions else None,
                    )

                    results, _ = await self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=scroll_filter,
                        limit=limit,
                        with_payload=True,
                        with_vectors=False,
                    )
                    all_results.extend(results)
                except Exception as exc:
                    print(f"[vector] keyword search error keyword={term}: {exc}")

        seen_ids = set()
        unique = []
        for hit in all_results:
            if hit.id in seen_ids:
                continue
            seen_ids.add(hit.id)
            unique.append(hit)

        return unique[: limit * 2]

    async def hybrid_search(self, query: str, keywords: list[str], limit: int = 20, filter_dict: dict | None = None):
        import asyncio

        semantic_task = self.search(query, limit=limit, filter_dict=filter_dict)
        keyword_task = self.keyword_search(keywords, limit=limit, filter_dict=filter_dict)
        semantic_results, keyword_results = await asyncio.gather(semantic_task, keyword_task)

        class SearchHit:
            def __init__(self, hit_id, payload, score):
                self.id = hit_id
                self.payload = payload
                self.score = score

        seen_ids = set()
        merged = []

        for hit in keyword_results:
            hid = str(hit.id)
            if hid in seen_ids:
                continue
            seen_ids.add(hid)
            content = str(hit.payload.get("content", "")).lower()
            match_count = sum(1 for kw in keywords if kw and kw.lower() in content)
            kw_score = 0.80 + (0.15 * match_count / max(len(keywords), 1))
            merged.append(SearchHit(hit.id, hit.payload, min(kw_score, 0.99)))

        for hit in semantic_results:
            hid = str(hit.id)
            if hid in seen_ids:
                continue
            seen_ids.add(hid)
            merged.append(SearchHit(hit.id, hit.payload, float(getattr(hit, "score", 0) or 0)))

        merged.sort(key=lambda x: x.score, reverse=True)
        return merged[:limit]

    async def set_document_active(self, doc_id: int, is_active: bool):
        await self._ensure_collection()

        try:
            await self.client.set_payload(
                collection_name=self.collection_name,
                payload={"is_active": is_active},
                points=models.Filter(
                    must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
                ),
            )
            print(f"[vector] set is_active={is_active} doc_id={doc_id}")
            return True
        except Exception as exc:
            print(f"[vector] set_document_active failed doc_id={doc_id}: {exc}")
            return False

    async def delete_document_vectors(self, doc_id: int):
        await self._ensure_collection()

        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
                    )
                ),
            )
            print(f"[vector] deleted vectors doc_id={doc_id}")
            return True
        except Exception as exc:
            print(f"[vector] delete_document_vectors failed doc_id={doc_id}: {exc}")
            return False

    async def scroll_by_doc_id(self, doc_id: int, limit: int = 50) -> list:
        await self._ensure_collection()

        try:
            results, _ = await self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id)),
                        models.FieldCondition(key="is_active", match=models.MatchValue(value=True)),
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            return results
        except Exception as exc:
            print(f"[vector] scroll_by_doc_id failed doc_id={doc_id}: {exc}")
            return []

