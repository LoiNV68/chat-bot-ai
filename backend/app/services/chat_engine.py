from typing import List, Dict
from app.services.llm_client import LLMClient
from app.services.vector_store import VectorStore
from app.models.user import User

class ChatEngine:
    def __init__(self):
        self.llm = LLMClient()
        self.vector_store = VectorStore()

    async def chat(self, user_query: str, history: List[str], user_info: User) -> dict:
        """
        Returns: dict with 'answer' and 'sources' keys
        """
        # Step 1: Let LLM decide if we need to search documents
        needs_rag = await self._needs_document_search(user_query)
        print(f"[DEBUG] Query: {user_query}, Needs RAG: {needs_rag}")
        
        if not needs_rag:
            # For conversational queries, respond directly without RAG
            response = await self._generate_conversational_response(user_query, history)
            return {'answer': response, 'sources': []}
        
        # Step 2: Rewrite Query for better retrieval
        refined_query = await self.llm.rewrite_query(user_query, history)
        print(f"[DEBUG] Refined query: {refined_query}")
        
        # Step 3: Build Security Filter
        filters = self._build_security_filter(user_info)
        print(f"[DEBUG] Filter: {filters}")
        
        # Step 4: Retrieve Context
        search_results = await self.vector_store.search(refined_query, limit=10, filter_dict=filters)


        
        print(f"[DEBUG] Raw search results count: {len(search_results)}")
        for i, hit in enumerate(search_results):
            score = hit.score
            # Use 'source' field as that's what ingestion_service uses
            filename = hit.payload.get('source', hit.payload.get('filename', 'N/A'))
            print(f"[DEBUG] Result {i+1}: score={score:.4f}, file={filename}")
        
        # 3.1 Apply Similarity Threshold
        THRESHOLD = 0.5
        valid_hits = [hit for hit in search_results if hit.score >= THRESHOLD]
        
        print(f"[DEBUG] After threshold ({THRESHOLD}): {len(valid_hits)} valid hits")
        
        # Extract content and source info
        context_text = "\n\n".join([hit.payload.get('content', '') for hit in valid_hits])
        
        # Extract unique sources with doc_id for linking
        seen_docs = set()
        sources = []
        for hit in valid_hits:
            doc_id = hit.payload.get('doc_id')
            # Use 'source' field as that's what ingestion_service uses
            filename = hit.payload.get('source', hit.payload.get('filename', 'Tài liệu không xác định'))
            if doc_id and doc_id not in seen_docs:
                seen_docs.add(doc_id)
                sources.append({
                    'doc_id': doc_id,

                    'filename': filename,
                    'score': round(hit.score, 2)
                })
        
        # 4. Generate Response
        prompt = f"""Bạn là Chat Bot AI của FBU (Trường Đại học Tài chính - Ngân hàng Hà Nội), một trợ lý ảo thông minh và thân thiện.
NHIỆM VỤ CỦA BẠN: Hỗ trợ sinh viên, giảng viên và cán bộ nhân viên giải đáp thắc mắc TUYỆT ĐỐI DỰA TRÊN CƠ SỞ TRI THỨC ĐƯỢC CUNG CẤP.

NẾU ĐƯỢC HỎI "BẠN LÀ AI": HÃY TRẢ LỜI "Tôi là Chat Bot AI của FBU, sẵn sàng hỗ trợ bạn các thông tin về trường Đại học Tài chính - Ngân hàng Hà Nội."
NẾU ĐƯỢC HỎI "BẠN ĐƯỢC TẠO RA BỞI AI": HÃY TRẢ LỜI "Tôi được tạo ra bởi NGUYỄN VĂN LỢI, sinh viên năm 4 của trường Đại học Tài chính - Ngân hàng Hà Nội khóa 11."
NẾU ĐƯỢC HỎI VỀ TRƯỜNG: HÃY TRẢ LỜI "Trường Đại học Tài chính - Ngân hàng Hà Nội (FBU) được thành lập theo Quyết định số 2336/QĐ-TTg ngày 21/12/2010 của Thủ tướng Chính phủ. Đây là cơ sở giáo dục đại học tư thục, có trụ sở chính tại huyện Mê Linh, thành phố Hà Nội."

Thông tin ngữ cảnh được cung cấp bên dưới:
---------------------
{context_text}
---------------------

CHỈ DẪN QUAN TRỌNG:
1. CHỈ sử dụng thông tin trong phần "Thông tin ngữ cảnh" để trả lời nếu nó có liên quan trực tiếp đến câu hỏi.
2. Nếu phần ngữ cảnh TRỐNG hoặc KHÔNG LIÊN QUAN (ví dụ: chào hỏi), HÃY TRẢ LỜI lịch sự mà KHÔNG bịa thông tin.
3. TUYỆT ĐỐI KHÔNG bịa đặt thông tin hoặc thêm nội dung không có trong ngữ cảnh.
4. Nếu không có thông tin trong ngữ cảnh, HÃY TRẢ LỜI: "Xin lỗi, tôi không tìm thấy thông tin này trong tài liệu."
5. Khi cần hướng dẫn liên hệ hỗ trợ, HÃY NÓI: "Bạn có thể liên hệ với Cố vấn học tập của mình hoặc Phòng Cộng tác sinh viên tại Trường Đại học Tài chính - Ngân hàng Hà Nội."

YÊU CẦU VỀ TRÌNH BÀY:
- Sử dụng **Markdown** để câu trả lời đẹp và dễ đọc.
- Sử dụng **in đậm** cho các ý chính.
- Sử dụng **dấu gạch đầu dòng** (-) hoặc **số thứ tự** (1., 2.) để liệt kê.
- Tách đoạn rõ ràng.

QUAN TRỌNG: TRẢ LỜI 100% bằng Tiếng Việt. KHÔNG sử dụng bất kỳ ký tự tiếng Nga, Trung, Nhật, Hàn nào.

Câu hỏi: {refined_query}

Trả lời:
"""
        
        response = await self.llm.generate_response(prompt)
        
        return {
            'answer': response,
            'sources': sources
        }

    async def _needs_document_search(self, query: str) -> bool:
        """
        Let LLM decide if the query needs document retrieval.
        Returns True if RAG is needed, False for conversational queries.
        """
        prompt = f"""Phân loại câu hỏi sau:

Câu hỏi: "{query}"

Trả lời CHỈ "CẦN" hoặc "KHÔNG" dựa trên:
- CẦN: Câu hỏi về quy định, thông báo, học phí, thủ tục, lịch học, chính sách, hoặc bất cứ thứ gì liên quan đến thông tin của trường
- KHÔNG: Chào hỏi, hỏi về bản thân AI, cảm ơn, tạm biệt, trò chuyện thông thường

Trả lời (CHỈ 1 TỪ):"""

        result = self.llm.generation_model.invoke(prompt).strip().upper()
        return "CẦN" in result or "CAN" in result

    async def _generate_conversational_response(self, query: str, history: List[str]) -> str:
        """
        Generate response for conversational queries without RAG.
        """
        prompt = f"""Bạn là Chat Bot AI của FBU (Trường Đại học Tài chính - Ngân hàng Hà Nội).
Bạn được tạo ra bởi NGUYỄN VĂN LỢI, sinh viên năm 4 khóa 11.

Hãy trả lời câu hỏi/tin nhắn sau một cách thân thiện và tự nhiên.
KHÔNG cần tìm kiếm tài liệu cho câu hỏi này.

Lịch sử hội thoại: {history[-5:] if history else 'Không có'}
Tin nhắn: {query}

Trả lời (bằng tiếng Việt, thân thiện):"""

        return await self.llm.generate_response(prompt)

    def _build_security_filter(self, user: User) -> Dict:
        # Qdrant filter structure
        # Simplified for debugging - only check public scope
        return {
            "should": [
                { "key": "access_scope", "match": { "value": "public" } },
                { "key": "scope", "match": { "value": "public" } },  # Alternative key
            ]
            # Temporarily removed is_active filter for debugging
        }
