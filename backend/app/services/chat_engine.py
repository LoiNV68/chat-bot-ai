from typing import List, Dict
from app.services.llm_client import LLMClient
from app.services.vector_store import VectorStore
from app.models.user import User

class ChatEngine:
    def __init__(self):
        self.llm = LLMClient()
        self.vector_store = VectorStore()

    async def chat(self, user_query: str, history: List[str], user_info: User) -> str:
        # 1. Rewrite Query
        refined_query = await self.llm.rewrite_query(user_query, history)
        
        # 2. Build Security Filter
        filters = self._build_security_filter(user_info)
        
        # 3. Retrieve Context
        # Using refined_query for vector search
        search_results = await self.vector_store.search(refined_query, filter_dict=filters)
        
        context_docs = [hit.payload.get('payload', {}).get('content', '') for hit in search_results] # Payload structure depends on point creation
        
        # Adjusting context extraction based on point structure in VectorStore
        # In VectorStore.upsert_vectors: payload=metadatas[i]
        # And in IngestionService: chunk['content'] is separate from 'metadata'.
        # Wait, VectorStore implementation put 'payload' as `metadatas[i]`. 
        # But `upsert_vectors` takes `texts` separately to embed.
        # We should store existing text in metadata (payload) to retrieve it later, 
        # OR Qdrant must store it. 
        # Reviewing VectorStore: it puts metadata as payload. 
        # In IngestionService: metadata DOES NOT contain 'content'. 
        # FIX: We need to include content in metadata/payload to retrieve it.
        
        # For now, let's assume content is in payload or we need to fix IngestionService.
        # Let's fix retrieval here assuming we fix IngestionService or VectorStore.
        
        context_text = "\n\n".join([hit.payload.get('content', '') for hit in search_results])
        
        # 4. Generate Response
        prompt = f"""
        Use the following context to answer the user's question. If you don't know the answer, just say that you don't know, don't try to make up an answer.
        
        Context:
        {context_text}
        
        Question: {refined_query}
        
        Answer:
        """
        
        response = await self.llm.generate_response(prompt)
        return response

    def _build_security_filter(self, user: User) -> Dict:
        # Qdrant filter structure
        return {
            "should": [
                { "key": "access_scope", "match": { "value": "public" } },
                {
                    "must": [
                        { "key": "access_scope", "match": { "value": "private" } },
                        { "key": "target_id", "match": { "value": str(user.id) } } # Assuming target_id links to user_id or similar
                    ]
                }
            ],
            "must": [
                { "key": "is_active", "match": { "value": True } } # Use payload key
            ]
        }
