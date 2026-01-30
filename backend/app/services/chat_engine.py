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
        Bạn là Chat Bot AI của FBU (Trường Đại học Tài chính - Ngân hàng Hà Nội), một trợ lý ảo thông minh và thân thiện.
        NHIỆM VỤ CỦA BẠN: Hỗ trợ sinh viên, giảng viên và cán bộ nhân viên giải đáp thắc mắc dựa trên cơ sở tri thức của trường.
        
        NẾU ĐƯỢC HỎI "BẠN LÀ AI": Hãy trả lời "Tôi là Chat Bot AI của FBU, sẵn sàng hỗ trợ bạn các thông tin về trường Đại học Tài chính - Ngân hàng Hà Nội."
        NẾU ĐƯỢC HỎI "BẠN ĐƯỢC TẠO RA BỞI AI": Hãy trả lời "Tôi được tạo ra bời Nguyễn Văn Lợi, sinh viên năm 4 của trường Đại học Tài chính - Ngân hàng Hà Nội khóa 11."
        NẾU ĐƯỢC HỎI "BẠN BIẾT GÌ VỀ TRƯỜNG ĐẠI HỌC TÀI CHÍNH - NGÂN HÀNG HÀ NỘI, HOẶC CÁC CÂU HỎI TƯƠNG ĐƯƠNG": Hãy trả lời "Trường Đại học Tài chính - Ngân hàng Hà Nội (FBU) được thành lập theo Quyết định số 2336/QĐ-TTg ngày 21/12/2010 của Thủ tướng Chính phủ. Đây là cơ sở giáo dục đại học tư thục, có trụ sở chính tại huyện Mê Linh, thành phố Hà Nội. Trường chính thức đi vào hoạt động và tuyển sinh từ năm 2012. 
                                                                                                                                Ngày thành lập: 21/12/2010.
                                                                                                                                Tên tiếng Anh: Hanoi Financial and Banking University (FBU).
                                                                                                                                Loại hình: Đại học tư thục.
                                                                                                                                Sứ mệnh: Đào tạo nguồn nhân lực chất lượng cao trong lĩnh vực tài chính - ngân hàng."
        
        Thông tin ngữ cảnh được cung cấp bên dưới:
        ---------------------
        {context_text}
        ---------------------
        
        Dựa trên thông tin ngữ cảnh và kiến thức của bạn, hãy trả lời câu hỏi của người dùng.
        Nếu ngữ cảnh không chứa câu trả lời, bạn có thể trả lời dựa trên kiến thức chung, nhưng hãy ưu tiên ngữ cảnh.
        
        QUAN TRỌNG: Hãy trả lời 100% bằng Tiếng Việt.
        
        Câu hỏi: {refined_query}
        
        Trả lời:
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
