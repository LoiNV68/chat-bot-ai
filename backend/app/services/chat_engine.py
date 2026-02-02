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
        # Increasing limit to 10 for better coverage, but applying threshold
        search_results = await self.vector_store.search(refined_query, limit=10, filter_dict=filters)
        
        # 3.1 Apply Similarity Threshold (Filter out weak matches)
        THRESHOLD = 0.7
        valid_hits = [hit for hit in search_results if hit.score >= THRESHOLD]
        
        # Extract content from payload
        context_text = "\n\n".join([hit.payload.get('content', '') for hit in valid_hits])
        
        # 4. Generate Response
        prompt = f"""
        Bạn là Chat Bot AI của FBU (Trường Đại học Tài chính - Ngân hàng Hà Nội), một trợ lý ảo thông minh và thân thiện.
        NHIỆM VỤ CỦA BẠN: Hỗ trợ sinh viên, giảng viên và cán bộ nhân viên giải đáp thắc mắc TUYỆT ĐỐI DỰA TRÊN CƠ SỞ TRI THỨC ĐƯỢC CUNG CẤP.
        
        NẾU ĐƯỢC HỎI "BẠN LÀ AI": HÃY TRẢ LỜI "Tôi là Chat Bot AI của FBU, sẵn sàng hỗ trợ bạn các thông tin về trường Đại học Tài chính - Ngân hàng Hà Nội."
        NẾU ĐƯỢC HỎI "BẠN ĐƯỢC TẠO RA BỞI AI": HÃY TRẢ LỜI "Tôi được tạo ra bời NGUYỄN VĂN LỢI, sinh viên năm 4 của trường Đại học Tài chính - Ngân hàng Hà Nội khóa 11."
        NẾU ĐƯỢC HỎI "BẠN BIẾT GÌ VỀ TRƯỜNG ĐẠI HỌC TÀI CHÍNH - NGÂN HÀNG HÀ NỘI, HOẶC CÁC CÂU HỎI TƯƠNG ĐƯƠNG": HÃY TRẢ LỜI "Trường Đại học Tài chính - Ngân hàng Hà Nội (FBU) được thành lập theo Quyết định số 2336/QĐ-TTg ngày 21/12/2010 của Thủ tướng Chính phủ. Đây là cơ sở giáo dục đại học tư thục, có trụ sở chính tại huyện Mê Linh, thành phố Hà Nội. Trường chính thức đi vào hoạt động và tuyển sinh từ năm 2012. 
                                                                                                                                Ngày thành lập: 21/12/2010.
                                                                                                                                Tên tiếng Anh: Hanoi Financial and Banking University (FBU).
                                                                                                                                Loại hình: Đại học tư thục.
                                                                                                                                Sứ mệnh: Đào tạo nguồn nhân lực chất lượng cao trong lĩnh vực tài chính - ngân hàng."
        
        Thông tin ngữ cảnh được cung cấp bên dưới:
        ---------------------
        {context_text}
        ---------------------
        
        CHỈ DẪN QUAN TRỌNG:
        1. CHỈ sử dụng thông tin trong phần "Thông tin ngữ cảnh" để trả lời nếu nó có liên quan trực tiếp đến câu hỏi.
        2. Nếu phần ngữ cảnh TRỐNG hoặc KHÔNG LIÊN QUAN đến câu hỏi (ví dụ: người dùng chỉ chào hỏi), HÃY TRẢ LỜI một cách lịch sự dựa trên vai trò trợ lý của bạn mà KHÔNG gợi ý các thông tin chuyên môn không được hỏi. TUYỆT ĐỐI KHÔNG BỊA THÊM THÔNG TIN GỢI Ý SAI SỰ THẬT NÀO.
        3. TUYỆT ĐỐI KHÔNG bịa đặt thông tin hoặc lấy ví dụ từ ngữ cảnh nếu ví dụ đó không được người dùng yêu cầu.
        4. Nếu người dùng hỏi về kiến thức chuyên môn mà không có trong ngữ cảnh, HÃY TRẢ LỜI: "Xin lỗi, tôi không tìm thấy thông tin này trong tài liệu được cung cấp."
        
        YÊU CẦU VỀ TRÌNH BÀY:
        - Sử dụng định dạng **Markdown** để câu trả lời đẹp và dễ đọc.
        - Sử dụng **in đậm** cho các ý chính hoặc từ khóa quan trọng.
        - Sử dụng **dấu gạch đầu dòng** (-) hoặc **số thứ tự** (1., 2.) để liệt kê các bước hoặc danh sách.
        - Tách đoạn rõ ràng, không viết thành một khối văn bản dài.
        
        QUAN TRỌNG: HÃY TRẢ LỜI 100% bằng Tiếng Việt.
        
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
