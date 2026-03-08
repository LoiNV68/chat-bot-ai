from typing import List, Dict, Any, Tuple
import re
import datetime
import unicodedata
from collections import defaultdict
from app.services.llm_client import LLMClient
from app.services.vector_store import VectorStore
from app.models.user import User
# from pyvi import ViTokenizer  # Removed: bge-m3 handles Vietnamese natively
# =================================================================
# GLOBAL PROMPTS
# =================================================================
FORMATTING_SYSTEM_PROMPT = """Bạn là chatbot AI của Trường Đại học Tài chính – Ngân hàng Hà Nội (FBU). 
Nhiệm vụ của bạn là tra cứu và trả lời chính xác thông tin từ hệ thống dữ liệu của nhà trường 
(văn bản, quyết định, thông báo, quy định, thông tin học tập, học phí, lịch học, điểm số…).

Mục tiêu:
- Trả lời rõ ràng, đúng thông tin.
- Format dễ đọc, giống văn bản hành chính của trường.
- Không suy đoán nếu dữ liệu không có.

==================================================
QUY TẮC TRẢ LỜI
==================================================

1. Chỉ trả lời dựa trên thông tin tìm được từ hệ thống.
2. Nếu không tìm thấy dữ liệu phù hợp, trả lời:
   "Hiện chưa tìm thấy thông tin trong hệ thống. Vui lòng liên hệ phòng ban liên quan của trường."
3. Không suy diễn, không tự tạo nội dung. KHÔNG than phiền hoặc giải thích về chất lượng dữ liệu (tuyệt đối không nhắc đến từ "OCR", "dữ liệu bị nhiễu", "không đọc được").
4. Không viết các câu như:
   - "Dựa trên ngữ cảnh được cung cấp"
   - "Theo tài liệu đã cho"

Hãy trả lời như đang tra cứu trực tiếp trong hệ thống của trường.

==================================================
QUY TẮC FORMAT
==================================================

1. Văn bản / Quyết định / Thông báo

Dòng đầu hiển thị:

**Tên văn bản** — Số hiệu — Ngày ban hành

Ví dụ:

**Quyết định số 93/QĐ-ĐHTNH** — Ngày ban hành: **22/02/2026**

Sau đó trình bày nội dung theo điều/khoản:

**Điều 1:** Nội dung điều thứ nhất...

**Điều 2:** Nội dung điều thứ hai...

**Điều 3:** Quyết định có hiệu lực từ ngày...

Mỗi điều phải xuống dòng riêng.

==================================================

2. Danh sách thông tin

Khi có từ 2 mục trở lên phải dùng danh sách:

- Mục thông tin thứ nhất
- Mục thông tin thứ hai
- Mục thông tin thứ ba

Hoặc:

1. Mục thứ nhất
2. Mục thứ hai
3. Mục thứ ba

==================================================

3. Số liệu quan trọng

Luôn in đậm các thông tin quan trọng:

- **Số tiền**
- **Ngày tháng**
- **Điểm số**
- **Số lượng sinh viên**
- **Thời hạn nộp**

Ví dụ:

- Hạn nộp học phí: **30/09/2026**
- Mức học phí: **12.500.000 VNĐ/học kỳ**
- Điểm trung bình tích lũy: **3.25**

==================================================

4. Câu hỏi thông tin ngắn

Nếu câu hỏi chỉ là hỏi thông tin đơn giản:

Ví dụ:
- Học phí bao nhiêu
- Bao giờ thi
- Điều kiện tốt nghiệp

Thì trả lời tự nhiên, ngắn gọn, không dùng cấu trúc Điều/Khoản.

Ví dụ:

Học phí hệ đại học chính quy tại FBU hiện khoảng **12.000.000 – 14.000.000 VNĐ/học kỳ** hoặc **600.000 – 1.200.000 VNĐ/tín chỉ** tùy ngành đào tạo.

==================================================
QUY TẮC TRÌNH BÀY
==================================================

Luôn đảm bảo:

- Nội dung xuống dòng rõ ràng
- Không viết toàn bộ thành một đoạn dài
- Không gộp nhiều điều trong cùng một dòng
- KHÔNG dùng code block markdown cho văn bản bình thường.
- TUY NHIÊN, NẾU dữ liệu gốc là Bảng biểu (Table/Danh sách dạng bảng), bạn BẮT BUỘC PHẢI giữ nguyên định dạng Bảng Markdown để hiển thị đẹp nhất.
- Không thêm ký hiệu hoặc format không cần thiết
"""

# =================================================================
# THÊM CLASS NÀY ĐỂ LƯU TRÍ NHỚ NGẮN HẠN CỦA USER
# =================================================================
class UserSession:
    def __init__(self):
        self.last_student_id = None
        self.last_student_name = None
        self.last_topic = None
        # Conversation Summary Memory
        self.summary = ""           # Tóm tắt hội thoại cũ
        self.recent_turns = []      # Chỉ giữ 4 tin nhắn gần nhất (raw)
        self.turn_count = 0

class ExcelQueryProcessor:
    """
    Basic implementation of ExcelQueryProcessor to replace the missing module.
    Analyzes queries to optimize search strategy.
    """
    def analyze_query(self, query: str) -> Dict[str, Any]:
        # Default fallback analysis
        return {
            'query_type': 'general',
            'search_strategy': 'hybrid', # Default to hybrid search
            'preferred_chunk_types': [],
            'keywords': [],
            'time_filter': None,
            'column_mentions': []
        }


class ChatEngine:
    """Singleton ChatEngine - tái sử dụng LLMClient và VectorStore."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.llm = LLMClient()
        self.vector_store = VectorStore()
        self.query_processor = ExcelQueryProcessor()
        # Cache sources từ truy vấn trước cho khi người dùng yêu cầu tài liệu
        self._cached_sources: Dict[str, List] = {}
        
        # BỔ SUNG: Dictionary lưu trữ session của tất cả người dùng
        self.sessions: Dict[str, UserSession] = {}
        
        # TASK 5: Khởi tạo Reranker 
        self._init_reranker()

    def _init_reranker(self):
        # Đã gỡ bỏ mô hình BAAI/bge-reranker-large trên CPU để tối ưu hiệu suất và dọn dẹp log.
        self.reranker = None

    def _normalize_text(self, text: str) -> str:
        """Normalize unicode input so keyword/intent matching is stable (NFC)."""
        if not text:
            return ""
        normalized = unicodedata.normalize("NFC", text)
        return re.sub(r'\s+', ' ', normalized).strip()

    def _is_student_followup(self, query: str, session: UserSession) -> bool:
        """Detect very short follow-ups that still refer to the previously selected student."""
        if not session.last_student_id:
            return False
        q = self._normalize_text(query).lower()
        personal_keywords = [
            'điểm', 'học kỳ', 'kỳ', 'hk1', 'hk2', 'hk3',
            'xếp loại', 'bao nhiêu', 'thì sao', 'còn'
        ]
        return len(q.split()) <= 8 and any(kw in q for kw in personal_keywords)

    # =================================================================
    # FIX 4: Query Intent Classifier — Phân loại câu hỏi thông minh
    # =================================================================
    def _classify_query_intent(self, query: str) -> str:
        """Phân loại intent của câu hỏi để chọn chiến lược search phù hợp."""
        query = self._normalize_text(query)
        q = query.lower()
        
        # ƯU TIÊN -1: Tra cứu văn bản cụ thể (vượt qua mọi keyword của sinh viên nếu người dùng dùng từ khóa quá rõ ràng)
        if any(kw in q for kw in [
            'nội dung của', 'nội dung quyết định', 'nội dung thông báo', 
            'chi tiết quyết định', 'chi tiết thông báo', 'cho tôi xin văn bản',
            'cho tôi xem văn bản', 'đọc quyết định'
        ]):
            return 'document_info'

        # ƯU TIÊN 0: Tra cứu sinh viên cụ thể (MSV hoặc keyword đặc trưng)
        # PHẢI CHECK TRƯỚC document_info vì "cho tôi biết về điểm của Lợi" = student_lookup
        if re.search(r'\b\d{10}\b', query) or any(kw in q for kw in [
            'điểm của', 'msv', 'mã sinh viên',
            'xếp loại của', 'kết quả học tập của'
        ]):
            return 'student_lookup'
        
        # ƯU TIÊN 0.5: Hỏi điểm + có tên người → student_lookup (kể cả khi có "cho tôi biết về")
        if any(kw in q for kw in ['điểm rèn luyện', 'điểm thi', 'điểm của']):
            name = self._extract_person_name(query)
            if name:
                return 'student_lookup'
        
        # ƯU TIÊN 1: Hỏi VỀ thông báo/quyết định/văn bản
        # VD: "thông báo về điểm rèn luyện" → document_info (không có tên người)
        if any(kw in q for kw in [
            'thông báo', 'quyết định', 'công văn', 'văn bản', 'kế hoạch',
            'nội dung', 'cho biết về', 'cho tôi biết về'
        ]):
            return 'document_info'
        
        # FIX C: Hỏi điểm + có tên người → student_lookup (không phải score_general)
        # VD: "điểm rèn luyện của Lợi" → student_lookup
        if any(kw in q for kw in ['điểm rèn luyện', 'điểm thi', 'điểm của']):
            # Kiểm tra có tên riêng không (từ viết hoa không phải stopword)
            name = self._extract_person_name(query)
            if name:
                return 'student_lookup'
            return 'score_general'
        
        # Hỏi về lịch, thời gian, deadline
        if any(kw in q for kw in [
            'khi nào', 'bao giờ', 'lịch', 'deadline', 'hạn',
            'thời gian', 'ngày', 'tháng'
        ]):
            return 'schedule'
        
        # Hỏi quy định, quy trình, thủ tục
        if any(kw in q for kw in [
            'quy định', 'quy trình', 'thủ tục', 'cách', 'làm sao',
            'hướng dẫn', 'điều kiện', 'yêu cầu'
        ]):
            return 'regulation'
        
        # Hỏi về phòng thi, thi cử
        if any(kw in q for kw in [
            'phòng thi', 'lịch thi', 'toeic', 'thi',
            'ca thi', 'địa điểm thi'
        ]):
            return 'exam'
        
        return 'general'

    async def chat(self, user_query: str, history: List[str], user_info: User, session_id: str = None, **kwargs) -> dict:
        """
        Trả về: dict với các key 'answer', 'sources', và 'has_related_docs'
        """
        # --- Khởi tạo hoặc Lấy Session của User/Conversation ---
        user_id = str(user_info.id) if user_info else "anonymous"
        session_key = f"{user_id}:{session_id}" if session_id else user_id
        if session_key not in self.sessions:
            self.sessions[session_key] = UserSession()
        session = self.sessions[session_key]

        # Normalize để tránh mismatch do Unicode tổ hợp (NFD/NFC)
        user_query = self._normalize_text(user_query)

        # === Build effective_history từ session memory (thay vì dùng history thô) ===
        effective_history = self._build_context_history(session)
        
        # === Detect user chỉ gửi chuỗi số (VD: MSV sau khi bot hỏi) ===
        pure_number_match = re.match(r'^\s*(\d+)\s*$', user_query.strip())
        if pure_number_match and effective_history:
            context_prompt = f"""Dựa vào lịch sử hội thoại sau, hãy xác định chuỗi số "{user_query.strip()}" là gì và người dùng muốn hỏi gì.

Lịch sử hội thoại gần nhất:
{chr(10).join(effective_history[-4:])}

Tin nhắn mới nhất của người dùng: "{user_query.strip()}"

Hãy viết lại thành câu hỏi hoàn chỉnh bằng tiếng Việt. Ví dụ:
- Nếu đây là mã sinh viên được chọn từ danh sách → "Cho tôi biết điểm rèn luyện của sinh viên MSV 2254800092"
- Nếu đây là số khác → giữ nguyên ngữ cảnh phù hợp

CHỈ trả về câu hỏi hoàn chỉnh, không giải thích."""

            try:
                expanded = await self.llm.generate_response(context_prompt)
                expanded = expanded.strip()
                if expanded and len(expanded) > 5:
                    print(f"[DEBUG] Pure number '{user_query}' → AI expanded: {expanded}")
                    user_query = expanded
            except Exception:
                pass  # Fallback: giữ nguyên, để flow xử lý bình thường
        
        # Bước 0: Kiểm tra người dùng có yêu cầu tài liệu rõ ràng không (DÙNG AI PHÁN ĐOÁN)
        wants_documents = await self._check_wants_documents_ai(user_query, effective_history)
        print(f"[DEBUG] Query: {user_query}, Wants documents AI: {wants_documents}")
        
        # Nếu người dùng yêu cầu tài liệu, trả về sources đã cache
        if wants_documents:
            cached = self._cached_sources.get(session_key, [])
            if cached:
                return {
                    'answer': "Đây là các tài liệu tham khảo liên quan:",
                    'sources': cached,
                    'has_related_docs': False
                }
            else:
                return {
                    'answer': "Mình chưa có tài liệu tham khảo nào từ câu hỏi trước đó. Bạn thử hỏi một nội dung cụ thể để mình tìm kiếm nhé! 😊",
                    'sources': [],
                    'has_related_docs': False
                }
        
        # Bước 1: Pattern matching nhanh để quyết định có cần RAG không
        needs_rag = self._needs_document_search(user_query, effective_history)
        print(f"[DEBUG] Query: {user_query}, Needs RAG: {needs_rag}")
        
        if not needs_rag:
            # Với các câu hỏi hội thoại, trả lời trực tiếp không cần RAG
            response = await self._generate_conversational_response(user_query, effective_history)
            # Cập nhật session memory
            await self._update_session_memory(session, user_query, response)
            return {'answer': response, 'sources': [], 'has_related_docs': False}
        
        # Bước 2: Follow-up pronoun resolution — thay thế "nó/đó/này" bằng topic cũ
        followup_pronouns = ['nó', 'cái đó', 'vấn đề đó', 'cái này', 'về nó', 'về điều đó', 'trích', 'trích ra', 'trích xuất', 'chi tiết', 'rõ hơn', 'đọc cho tôi']
        if session.last_topic and any(p in user_query.lower() for p in followup_pronouns):
            # Tiêm topic cũ vào query để LLM hiểu ngữ cảnh
            user_query_with_topic = user_query
            for p in followup_pronouns:
                if p in user_query.lower():
                    user_query_with_topic = user_query.lower().replace(p, f'"{session.last_topic}"', 1)
                    break
            print(f"🔗 [Follow-up] Thay đại từ: '{user_query}' → '{user_query_with_topic}'")
            user_query = user_query_with_topic
        
        # Bước 3: Viết lại Query để truy xuất tốt hơn
        refined_query = await self.llm.rewrite_query(user_query, effective_history)
        print(f"[DEBUG] Refined query: {refined_query}")
        
        # Bước 3: Xây dựng Security Filter
        filters = self._build_security_filter(user_info)
        print(f"[DEBUG] Filter: {filters}")
        
        # Bước 4: Phân tích query (Excel optimization)
        query_analysis = self.query_processor.analyze_query(user_query)
        query_analysis['original_query'] = user_query  # Truyền query gốc cho reranker
        print(f"[DEBUG] Query Analysis: Type={query_analysis['query_type']}, Strategy={query_analysis['search_strategy']}, Preferred={query_analysis['preferred_chunk_types']}")
        
        # Bước 5: Trích xuất keywords và MÃ SINH VIÊN
        keywords = self._extract_keywords(user_query)
        refined_keywords = self._extract_keywords(refined_query)
        all_kw = list(dict.fromkeys(keywords + refined_keywords))
        for kw in query_analysis.get('keywords', []):
            if kw not in all_kw:
                all_kw.append(kw)
        
        # Bước 6: Enhance filter với chunk_type, time_info và ĐẶC NHIỆM MÃ SINH VIÊN
        enhanced_filters = filters.copy()
        
        # 6.1. Thêm chunk_type và time filter (giữ nguyên code của bạn)
        if len(query_analysis['preferred_chunk_types']) <= 2 and query_analysis['preferred_chunk_types']:
            if 'should' not in enhanced_filters:
                enhanced_filters['should'] = []
            for chunk_type in query_analysis['preferred_chunk_types']:
                enhanced_filters['should'].append({
                    'key': 'chunk_type',
                    'match': {'value': chunk_type}
                })
                
        if query_analysis.get('time_filter'):
            if 'must' not in enhanced_filters:
                enhanced_filters['must'] = []
            enhanced_filters['must'].append({
                'key': 'time_info',
                'match': {'value': query_analysis['time_filter']}
            })

        # Xác định intent sớm bằng refined_query để hiểu đúng context
        query_intent = self._classify_query_intent(refined_query)
        print(f"[DEBUG] Query intent: {query_intent}")

        should_apply_student_router = query_intent == 'student_lookup' or self._is_student_followup(user_query, session)

        # 6.2. THE MAGIC ROUTER: TÌM KIẾM SIÊU TỐC NẾU CÓ MÃ SINH VIÊN
        student_ids = re.findall(r'\b(\d{10})\b', user_query)
        target_id = None
        ambiguous_name_to_ask = None
        lookup_results = []

        if should_apply_student_router and student_ids:
            # Có MSV rõ ràng → luôn dùng MSV mới
            target_id = student_ids[0]
            session.last_student_id = target_id
            session.last_student_name = None
            print(f"🎯 [Memory] Lưu Mã SV MỚI: {target_id}")
        elif should_apply_student_router:
            # Không có MSV → kiểm tra xem có tên người mới không (Dùng refined_query để bắt đúng tên thật đã viết hoa & full intent từ AI)
            new_name_in_query = self._extract_person_name(refined_query)
            
            if new_name_in_query and session.last_student_name:
                # So sánh tên trong query với tên đang nhớ
                name_changed = False
                for w in new_name_in_query.lower().split():
                    if w not in session.last_student_name.lower():
                        name_changed = True
                        break
                        
                if name_changed:
                    # User đang hỏi về người KHÁC → reset session
                    print(f"🔄 [Memory] Tên mới '{new_name_in_query}' ≠ cũ '{session.last_student_name}' → reset")
                    session.last_student_id = None
                    target_id = None
                    
                    # [NEW] Pre-lookup MSV cho người MỚI
                    lookup_results = await self._lookup_student_msv_by_name(new_name_in_query)
                    if len(lookup_results) == 1:
                        target_id = lookup_results[0][0]
                        session.last_student_id = target_id
                        session.last_student_name = lookup_results[0][1]
                        print(f"✨ [Pre-Lookup] Tự động gán MSV {target_id} cho '{new_name_in_query}'")
                    elif len(lookup_results) > 1:
                        ambiguous_name_to_ask = new_name_in_query
                        
                else:
                    # Cùng người → dùng MSV cũ
                    target_id = session.last_student_id
                    print(f"🧠 [Memory] Tên khớp → dùng MSV cũ: {target_id}")
            
            elif new_name_in_query and not session.last_student_id:
                # Không có memory, không có MSV → tra cứu MSV MỚI
                target_id = None
                
                # [NEW] Pre-lookup MSV
                lookup_results = await self._lookup_student_msv_by_name(new_name_in_query)
                if len(lookup_results) == 1:
                    target_id = lookup_results[0][0]
                    session.last_student_id = target_id
                    session.last_student_name = lookup_results[0][1]
                    print(f"✨ [Pre-Lookup] Tự động gán MSV {target_id} cho '{new_name_in_query}'")
                elif len(lookup_results) > 1:
                    ambiguous_name_to_ask = new_name_in_query
            
            elif not new_name_in_query and session.last_student_id:
                # Không có tên mới → câu follow-up thực sự?
                personal_keywords = ['điểm', 'kỳ', 'xếp loại', 'bao nhiêu', 'thì sao', 'còn']
                is_followup = any(kw in user_query.lower() for kw in personal_keywords)
                
                if is_followup and len(user_query.split()) <= 8:
                    target_id = session.last_student_id
                    print(f"🧠 [Memory] Follow-up thực sự → MSV cũ: {target_id}")

        # [NEW] Trả lời luôn nếu tìm ra NHIỀU người (mơ hồ) TỪ TRƯỚC KHI SEARCH
        if ambiguous_name_to_ask:
            session.last_student_name = ambiguous_name_to_ask
            
            lines = [f"Mình tìm thấy **{len(lookup_results)} sinh viên** có tên chứa \"{ambiguous_name_to_ask}\", bạn muốn hỏi về ai?\n"]
            for msv, f_name in lookup_results:
                lines.append(f"- **{f_name}** — MSV: `{msv}`")
            lines.append("\nBạn hãy nhập **mã sinh viên** để mình tìm chính xác nhé!")
            
            clarification = "\n".join(lines)
            return {
                'answer': clarification,
                'sources': [],
                'has_related_docs': False
            }

        # NẾU XÁC ĐỊNH ĐƯỢC ĐỐI TƯỢNG (Mới hoặc Cũ), ÁP DỤNG FILTER CỨNG
        if target_id:
            if 'must' not in enhanced_filters:
                enhanced_filters['must'] = []
                
            enhanced_filters['must'].append({
                "key": "student_ids_in_chunk",
                "match": {"any": [target_id]}
            })
            
            # Xóa mã SV khỏi text search để tránh làm nhiễu thuật toán BM25
            all_kw = [kw for kw in all_kw if kw != target_id]
            query_analysis['search_strategy'] = 'hybrid'
            
            # MẸO HACK PROMPT: Tiêm ngầm mã SV vào câu hỏi để LLM không bị ngáo
            if target_id not in refined_query:
                refined_query += f" (cho sinh viên mã {target_id})"

        print(f"[DEBUG] Enhanced Filters: {enhanced_filters}")
        
        # Bước 7: Không cần ViTokenizer nữa — bge-m3 xử lý tiếng Việt trực tiếp
        tokenized_query = refined_query
        tokenized_kw = all_kw  # Giữ nguyên keywords gốc
        print(f"[DEBUG] Query (raw): {tokenized_query[:100]}")
        
        # Bước 8: Search dựa trên strategy từ query analysis
        # --- TASK 9: CHUYỂN SANG HYBRID (BM25 + Semantic) MẶC ĐỊNH ---
        # Qdrant hỗ trợ Sparse Vector, bật Hybrid lấy cả 2 kết hợp
        search_strategy = 'hybrid'
        
        # FIX 4: Điều chỉnh strategy dựa trên intent
        
        if query_intent == 'student_lookup' and not target_id:
            # Tra cứu SV theo tên → ưu tiên keyword search
            search_strategy = 'keyword' if tokenized_kw else 'hybrid'
            
            # QUAN TRỌNG: Nếu đang tra bằng tên (không có target_id - mã sinh viên được xác nhận)
            # Không được cho phép tải danh sách lớp ngẫu nhiên vào context vì BM25 sẽ "ghép" các
            # thành phần tên rời rạc từ các sinh viên khác nhau trong cùng 1 lớp (vd: Nguyễn A, Lê B Nam -> Nguyễn Nam)
            # Việc này dẫn đến LLM bị ảo giác báo sinh viên ở lớp đó
            if 'must_not' not in enhanced_filters:
                enhanced_filters['must_not'] = []
            enhanced_filters['must_not'].append({
                'key': 'content_type',
                'match': {'any': ['student_list', 'excel_table']}
            })
            print("🎯 [Intent] student_lookup (no MSV) → loại bỏ student_list + excel_table để tránh trộn tên")
            
        elif query_intent == 'document_info' and not target_id:
            # Hỏi VỀ thông báo/quyết định → ưu tiên hybrid + lọc bỏ bảng điểm
            # CHỈ lọc khi KHÔNG có target_id (nếu có target_id = đang tra cứu SV cụ thể)
            search_strategy = 'hybrid' if tokenized_kw else 'semantic'
            # QUAN TRỌNG: Filter bỏ chunks bảng điểm (student_list) — chỉ lấy text
            if 'must_not' not in enhanced_filters:
                enhanced_filters['must_not'] = []
            enhanced_filters['must_not'].append({
                'key': 'content_type',
                'match': {'value': 'student_list'}
            })
            print(f"🎯 [Intent] document_info → loại bỏ student_list khỏi kết quả")
        elif query_intent in ('regulation', 'schedule', 'exam'):
            # Hỏi thông tin chung → ưu tiên semantic search
            if not tokenized_kw:
                search_strategy = 'semantic'
        
        SEARCH_LIMIT = 20  # Tăng lên 20 để tạo tập ứng viên đủ rộng cho Reranker đánh giá lai
        
        if search_strategy == 'keyword' and tokenized_kw:
            search_results = await self.vector_store.keyword_search(
                keywords=tokenized_kw,
                limit=SEARCH_LIMIT,
                filter_dict=enhanced_filters
            )
        elif search_strategy == 'semantic' or not tokenized_kw:
            search_results = await self.vector_store.search(
                tokenized_query, limit=SEARCH_LIMIT, filter_dict=enhanced_filters
            )
        else:  # hybrid (default)
            search_results = await self.vector_store.hybrid_search(
                query=tokenized_query, 
                keywords=tokenized_kw, 
                limit=SEARCH_LIMIT, 
                filter_dict=enhanced_filters
            )

        # Fallback: if semantic has no hits, retry keyword search
        if not search_results and search_strategy == 'semantic' and tokenized_kw:
            print('[Fallback] Semantic empty, retry keyword search.')
            search_results = await self.vector_store.keyword_search(
                keywords=tokenized_kw,
                limit=SEARCH_LIMIT,
                filter_dict=enhanced_filters
            )
            search_strategy = 'keyword'

        print(f"[DEBUG] Raw search results count: {len(search_results)} (strategy: {search_strategy})")
        valid_hits = self._filter_results(search_results, query_analysis, search_strategy=search_strategy)
        
        # Bước 8: Re-rank results dựa trên query type (heuristics cũ)
        valid_hits = self._rerank_by_query_type(valid_hits, query_analysis)

        # TASK 5: CROSS-ENCODER RERANKER CHÍNH THỨC
        if getattr(self, 'reranker', None) and valid_hits:
            print(f"[DEBUG] Khởi chạy BGE-Reranker trên {len(valid_hits)} kết quả...")
            try:
                pairs = [[refined_query, hit.payload.get('content', '')] for hit in valid_hits]
                
                # Sửa lỗi WinError 1450/10055: Chạy predict() trong ThreadPool để không block Event Loop
                import asyncio
                scores = await asyncio.to_thread(self.reranker.predict, pairs)
                
                for i, hit in enumerate(valid_hits):
                    hit.score = float(scores[i]) # CrossEncoder logit score
                
                # Sắp xếp giảm dần theo điểm Reranker thực tế (BGE Reranker)
                valid_hits.sort(key=lambda x: x.score, reverse=True)
            except Exception as e:
                print(f"[ERROR] Lỗi hạ tầng khi gọi Reranker: {e}")

        # Nếu người dùng chỉ định năm/năm học rõ ràng, ưu tiên cứng các hit khớp năm.
        if query_intent != 'student_lookup':
            valid_hits = self._apply_explicit_year_filter(valid_hits, user_query)
            valid_hits = self._apply_topic_guard(valid_hits, user_query)
        
        # TOP-K ĐỘNG: Văn bản dài (quy định, thông báo) cần nhiều chunks hơn
        if query_intent in ('document_info', 'regulation'):
            top_k = 8  # Lấy nhiều hơn cho văn bản dài
        else:
            top_k = 6
        valid_hits = valid_hits[:top_k] 
        
        print(f"[DEBUG] After dynamic threshold + limit top {top_k}: {len(valid_hits)} valid hits")
        
        # Bước 9: DOCUMENT-LEVEL EXPANSION — lấy TẤT CẢ chunks từ cùng document
        # Đảm bảo LLM có context đầy đủ (không thiếu bảng phí, phương thức nộp, v.v.)
        if valid_hits and query_intent != 'student_lookup':  # Student lookup đã filter chuẩn rồi
            excluded_types = []
            if query_intent == 'document_info':
                excluded_types = ['student_list']
            valid_hits = await self._expand_with_same_doc_chunks(valid_hits, excluded_types)

        # Với truy vấn "nội dung văn bản", chỉ giữ 1 document chính để tránh trộn ngữ cảnh.
        if valid_hits and query_intent == 'document_info':
            valid_hits = self._focus_on_primary_document(valid_hits)
        
        # === FIX 1: Phát hiện tên người mơ hồ (không có MSV) ===
        if query_intent == 'student_lookup' and not target_id:  # Chỉ check khi KHÔNG có MSV
            ambiguous_name = self._detect_ambiguous_name(user_query, valid_hits)
            if ambiguous_name:
                session.last_student_name = ambiguous_name  # Lưu tên đang hỏi
                clarification = self._build_clarification_response(ambiguous_name, valid_hits)
                return {
                    'answer': clarification,
                    'sources': [],
                    'has_related_docs': False
                }
        # Fallback mềm: nếu có raw hits nhưng bị filter quá gắt, giữ lại vài chunk đầu
        # cho truy vấn văn bản/lịch để tránh false-negative.
        if not valid_hits and search_results and query_intent in ('document_info', 'regulation', 'schedule', 'exam'):
            relaxed_hits = []
            for hit in search_results:
                content = str(hit.payload.get('content', '')).strip()
                if len(content) < 30:
                    continue
                relaxed_hits.append(hit)
                if len(relaxed_hits) >= 3:
                    break
            if relaxed_hits:
                print(f"[Fallback] Relaxed retrieval keeps {len(relaxed_hits)} hits from raw results.")
                valid_hits = relaxed_hits

        # Nếu vẫn không có dữ liệu phù hợp, trả câu trả lời deterministic có format rõ ràng.
        if not valid_hits:
            response = self._build_no_data_response(refined_query, query_intent)
            await self._update_session_memory(session, user_query, response)
            return {
                'answer': response,
                'sources': [],
                'has_related_docs': False
            }
        
        # Trích xuất nội dung với context building tối ưu (grouped by source + priority)
        context_text = self._build_optimized_context(valid_hits)
        print(f"[DEBUG] Context length: {len(context_text)} chars")
        
        # Trích xuất các sources duy nhất với doc_id để liên kết
        seen_docs = set()
        sources = []
        for hit in valid_hits:
            doc_id = hit.payload.get('doc_id')
            # Sử dụng field 'source' vì đó là field ingestion_service dùng
            filename = hit.payload.get('source', hit.payload.get('filename', 'Tài liệu không xác định'))
            if doc_id and doc_id not in seen_docs:
                seen_docs.add(doc_id)
                sources.append({
                    'doc_id': doc_id,
                    'filename': filename,
                    'score': round(getattr(hit, 'score', 0) or 0, 2)
                })
        # Cache sources theo session để tránh lẫn tài liệu giữa các hội thoại khác nhau.
        self._cached_sources[session_key] = sources
        
        # Kiểm tra xem có tài liệu liên quan để gợi ý không
        has_related_docs = len(sources) > 0
        
        # === FIX 5: Parse trực tiếp dữ liệu SV từ bảng — bypass LLM cho tra cứu điểm ===
        if target_id:
            student_records = self._extract_student_data_from_hits(valid_hits, target_id)
            if student_records:
                name = student_records[0]['ho_ten']
                lines = [f"**Điểm rèn luyện** của **{name}** (MSV: `{target_id}`):\n"]
                for r in student_records:
                    lines.append(f"- **{r['hoc_ky']}**: **{r['diem']} điểm** — Xếp loại: {r['xep_loai']}")
                
                # Lưu tên đầy đủ vào session cho follow-up
                session.last_student_name = student_records[0]['ho_ten']
                session.last_student_id = target_id
                print(f"[DEBUG] Direct parse bypass: {len(student_records)} records for {target_id}")
                answer = "\n".join(lines)
                await self._update_session_memory(session, user_query, answer)
                return {
                    'answer': answer,
                    'sources': [],
                    'has_related_docs': has_related_docs
                }
            # Parse thất bại → fallback LLM bình thường
        
        # Với tài liệu scan/OCR nhiễu, trả lời theo chế độ an toàn để tránh bịa.
        safe_ocr_answer = self._build_safe_ocr_answer(user_query, query_intent, valid_hits)
        if safe_ocr_answer:
            await self._update_session_memory(session, user_query, safe_ocr_answer)
            return {
                'answer': safe_ocr_answer,
                'sources': [],
                'has_related_docs': has_related_docs
            }
        
        
        deterministic_mien_giam_answer = self._build_mien_giam_subject_answer(refined_query, context_text)
        if deterministic_mien_giam_answer:
            await self._update_session_memory(session, user_query, deterministic_mien_giam_answer)
            return {
                'answer': deterministic_mien_giam_answer,
                'sources': [],
                'has_related_docs': has_related_docs
            }

        deterministic_fee_answer = self._build_fee_notice_answer(refined_query, context_text)
        if deterministic_fee_answer:
            await self._update_session_memory(session, user_query, deterministic_fee_answer)
            return {
                'answer': deterministic_fee_answer,
                'sources': [],
                'has_related_docs': has_related_docs
            }
        deterministic_tet_answer = self._build_tet_notice_answer(refined_query, context_text)
        if deterministic_tet_answer:
            await self._update_session_memory(session, user_query, deterministic_tet_answer)
            return {
                'answer': deterministic_tet_answer,
                'sources': [],
                'has_related_docs': has_related_docs
            }

        # 4. Tạo phản hồi - FIX 2: Prompt đa năng cho mọi loại câu hỏi
        document_answer_rule = ""
        if query_intent == 'document_info':
            document_answer_rule = "6. CHI TIẾT VĂN BẢN: Nếu tài liệu là Quyết định/Thông báo, hãy liệt kê đầy đủ các Điều/Khoản.\n7. ĐỊNH DẠNG BẢNG: Chỉ hiển thị Markdown Table khi bảng có dữ liệu thực tế.\n8. BẢNG MẪU/TRỐNG: Nếu các dòng chủ yếu là placeholder (ví dụ '...', ô rỗng, gạch), KHÔNG dựng lại từng dòng; chỉ nêu tên bảng và hướng dẫn ngắn gọn."
        elif query_intent == 'student_lookup':
            document_answer_rule = "6. KILL-SWITCH TÌM KIẾM SINH VIÊN (RẤT QUAN TRỌNG): NẾU bạn không tìm thấy tên sinh viên người dùng hỏi, BẠN PHẢI DỪNG LẠI NGAY LẬP TỨC. Tuyệt đối KHÔNG ĐƯỢC tóm tắt hay phân tích tài liệu (không được in ra Điều 1, Điều 2...). CHỈ trả lời ngắn gọn: 'Rất tiếc, mình không tìm thấy thông tin của [Tên sinh viên] trên hệ thống nhà trường.' và DỪNG."

        prompt = f"""{FORMATTING_SYSTEM_PROMPT}

---
DỮ LIỆU ĐƯỢC TRÍCH XUẤT TỪ HỆ THỐNG (Giữ nguyên cấu trúc Bảng nếu có):
{context_text}

YÊU CẦU TỪ NGƯỜI DÙNG: {refined_query}

QUY TẮC RÀNG BUỘC (KIỂM TRA TRƯỚC KHI TRẢ LỜI):
1. Mọi thông tin bạn nói ra đều phải có trong dữ liệu hệ thống bên trên.
2. Tuyệt đối cấm báo cáo sai lệch hoặc chắp vá dữ liệu của người này cho người khác.
3. Không sử dụng các từ khóa lộ liễu của bot như: "Trong ngữ cảnh được cung cấp", "Dựa theo tài liệu ban đầu", "Trong văn bản trên bề mặt". Đóng vai nhân viên tra cứu tự nhiên.
4. Trả lời bằng giọng điệu lịch sự, chuyên nghiệp, gọn gàng bằng tiếng Việt.
5. Nếu câu trả lời quá dài, hãy tách đoạn bằng khoảng trắng.
{document_answer_rule}

TRẢ LỜI (Nếu có bảng, hãy dùng cú pháp Markdown Table như | Cột 1 | Cột 2 |):"""
        
        print(f"\n[DEBUG] Context length sent to LLM: {len(context_text)} chars")
        if "<table>" in context_text:
            print("[DEBUG] <table> tag DETECTED in context! The LLM should render a Markdown table.")

        response = await self.llm.generate_response(prompt)
        
        print(f"\n[DEBUG] LLM Raw Response snippet: {response[:200]}...\n")

        if query_intent != 'student_lookup' and self._looks_like_no_data_response(response):
            print('[NoData Detector] Fallback forced by detector for response opening:', response[:120])
            response = self._build_no_data_response(refined_query, query_intent)
            sources = []
            self._cached_sources[session_key] = []
            has_related_docs = False

        if query_intent == 'document_info':
            response = self._suppress_placeholder_tables(response)
            response = self._enrich_document_info_response(response, context_text, refined_query)

        # FIX 5: Validate response — phát hiện hallucination (MSV bịa)
        response = self._validate_response(response, context_text)
        
        # Lưu topic vào session cho follow-up (lấy từ hit đầu tiên, TRỪ KHI đang tra cứu sinh viên)
        # Vì nếu tra cứu sinh viên, chủ đề chính là sinh viên chứ không phải văn bản chứa tên họ.
        if valid_hits and query_intent != 'student_lookup':
            top_title = valid_hits[0].payload.get('title', '')
            top_doc_number = valid_hits[0].payload.get('doc_number', '')
            if top_title and top_title != 'Không xác định':
                topic_str = top_title
                if top_doc_number and top_doc_number != 'Không xác định':
                    topic_str = f"{top_doc_number} - {top_title}"
                session.last_topic = topic_str
                print(f"📌 [Session] Saved topic: {session.last_topic}")
        
        # Cập nhật session memory sau mỗi response
        await self._update_session_memory(session, user_query, response)
        
        # Trả về câu trả lời KHÔNG kèm sources, nhưng báo hiệu có tài liệu liên quan
        print(f"""
=== CHAT DEBUG ===
Query gốc: {user_query}
Query refined: {refined_query}
Intent: {query_intent}
Filter: {enhanced_filters}
Hits ban đầu: {len(search_results)}
Hits sau filter: {len(valid_hits)}
Context length: {len(context_text)} chars
Scores: {[round(h.score, 3) for h in valid_hits if hasattr(h, 'score')]}
Content types: {[h.payload.get('content_type', '?') for h in valid_hits]}
==================
""")
        return {
            'answer': response,
            'sources': [],  # Không tự động đính kèm sources
            'has_related_docs': has_related_docs  # Flag cho frontend hiển thị gợi ý
        }

    async def _check_wants_documents_ai(self, query: str, history: List[str]) -> bool:
        """
        Sử dụng AI để phán đoán xem người dùng có đang yêu cầu xem tài liệu/nguồn tham khảo không.
        """
        prompt = f"""Bạn là một hệ thống phân tích ý định người dùng.
Nhiệm vụ: Xác định xem câu hỏi của người dùng có đúng là đang YÊU CẦU XEM, LẤY, HOẶC TẢI XUỐNG CÁC FILE TÀI LIỆU GỐC/NGUỒN THAM KHẢO mà AI vừa dùng để trả lời hay không.

Ví dụ NGƯỜI DÙNG CHỈ HỎI THÔNG TIN BÌNH THƯỜNG (KHÔNG yêu cầu file):
- "Bạn có biết điểm rèn luyện của Nam không?" -> FALSE
- "Cho tôi xem thông báo học phí" -> FALSE (Họ muốn AI đọc thông báo và trả lời, không phải bắt AI đưa file)
- "Có" hoặc "Ừ" (Nếu lịch sử không hề hỏi "bạn có muốn xem file không") -> FALSE
- "Quy định học bổng xem ở đâu?" -> FALSE (hỏi thông tin)

Ví dụ NGƯỜI DÙNG THỰC SỰ MUỐN CUNG CẤP FILE GỐC:
- "Cho tôi xem file tài liệu đó" -> TRUE
- "Bạn lấy nguồn từ đâu, cho tôi xem văn bản" -> TRUE
- "Tải file gốc ở đâu" -> TRUE
- "Có" / "Xem đi" / "Gửi luôn đi" (NẾU ngay trước đó AI vừa hỏi "Bạn có muốn xem tài liệu tham khảo không?") -> TRUE

Lịch sử hội thoại gần nhất (để biết họ đang trả lời câu nào):
{history[-2:] if history else 'Không có'}

Câu hỏi của người dùng: "{query}"

Hãy trả lời CHỈ bằng đúng 1 từ: "TRUE" hoặc "FALSE"."""

        try:
            response = await self.llm.generate_response(prompt)
            print(f"[DEBUG] AI Intent Response for documents: {response.strip()}")
            return "TRUE" in response.upper()
        except Exception as e:
            print(f"[ERROR] AI Intent check failed: {e}")
            return False
    def _build_no_data_response(self, query: str, query_intent: str) -> str:
        """Deterministic fallback response with readable markdown layout."""
        contact_by_intent = {
            'document_info': 'Phòng Hành chính - Tổng hợp',
            'schedule': 'Phòng Đào tạo',
            'exam': 'Phòng Khảo thí',
            'regulation': 'Phòng Đào tạo',
            'student_lookup': 'Phòng Công tác sinh viên',
        }
        contact_hint = contact_by_intent.get(query_intent, 'phòng ban liên quan')
        normalized_query = self._normalize_text(query)

        lines = [
            "Hiện chưa tìm thấy thông tin phù hợp trong hệ thống cho nội dung bạn hỏi.",
            "",
            f"- Nội dung tra cứu: **{normalized_query}**",
            "- Gợi ý: thử thêm từ khóa như **thông báo**, **quyết định**, **số hiệu văn bản** hoặc **đơn vị ban hành**.",
            f"- Nếu cần xác nhận chính thức, vui lòng liên hệ **{contact_hint}** của trường.",
        ]
        return "\n".join(lines)

    def _looks_like_no_data_response(self, response: str) -> bool:
        if not response:
            return False

        folded = self._fold_for_match(response)
        if not folded:
            return False

        # Chỉ coi là "no data" khi phần mở đầu đúng mẫu thiếu dữ liệu.
        folded_head = folded[:220]
        openers = [
            'hien chua tim thay thong tin',
            'khong tim thay thong tin',
            'chua tim thay thong tin',
        ]
        if not any(op in folded_head for op in openers):
            return False

        # Nếu đã có dấu hiệu câu trả lời nội dung thực tế thì không ép fallback.
        substantive_markers = [            'ngay ban hanh',
            'theo van ban',
            'dieu 1',
            'dieu 2',
            'noi dung chinh',
        ]
        if any(marker in folded for marker in substantive_markers):
            return False

        checks = [
            'hien chua tim thay thong tin',
            'khong tim thay thong tin',
            'vui long lien he',
            'phong ban lien quan',
        ]
        hit_count = sum(1 for c in checks if c in folded)
        return hit_count >= 2
    def _build_mien_giam_subject_answer(self, query: str, context_text: str) -> str | None:
        """Deterministic answer for "??i t??ng mi?n, gi?m h?c ph? l? ai/l? g?"."""
        if not query or not context_text:
            return None

        q_fold = self._fold_for_match(query)
        has_subject = 'doi tuong' in q_fold and ('mien' in q_fold or 'giam hoc phi' in q_fold)
        ask_who = any(token in q_fold for token in ['la ai', 'la gi', 'doi tuong nao'])
        if not (has_subject and ask_who):
            return None

        compact_fold = self._fold_for_match(context_text)

        has_item1 = bool(re.search(r'mien giam hoc phi.{0,400}phu luc 1', compact_fold))
        has_item2 = (
            bool(re.search(r'81 2021.{0,300}phu luc 2', compact_fold))
            or bool(re.search(r'phu luc 2.{0,300}81 2021', compact_fold))
        )
        if not (has_item1 or has_item2):
            return None

        item1_text = (
            'Đối tượng sinh viên được miễn, giảm học phí trực tiếp tại trường theo chính sách '            'ưu đãi, hỗ trợ của Trường Đại học Tài chính - Ngân hàng Hà Nội (theo phụ lục 1).'
        )
        item2_text = (
            'Đối tượng được Nhà nước hỗ trợ đóng học phí theo Nghị định 81/2021/NĐ-CP (theo phụ lục 2).'
        )

        lines = [
            '**Đối tượng sinh viên được miễn, giảm học phí gồm:**',
            '',
        ]
        if has_item1:
            lines.append(f'- {item1_text}')
        if has_item2:
            lines.append(f'- {item2_text}')

        lines.append('')
        lines.append('Nếu bạn cần, mình có thể liệt kê thêm **hồ sơ cụ thể** của từng nhóm theo Phụ lục 1 và Phụ lục 2.')
        return '\n'.join(lines).strip()


    def _build_fee_notice_answer(self, query: str, context_text: str) -> str | None:
        """Deterministic answer for tuition/fee notice to avoid missing tuition rates."""
        if not query or not context_text:
            return None

        q_fold = self._fold_for_match(query)
        is_fee_query = (
            ('hoc phi' in q_fold or 'le phi' in q_fold)
            and any(k in q_fold for k in ['ky 1', 'ky i', '2025 2026', 'thu le phi', 'thu hoc phi'])
        )
        if not is_fee_query:
            return None

        target_semester = ''
        if re.search(r'\bky\s*(1|i)\b', q_fold):
            target_semester = 'i'
        elif re.search(r'\bky\s*(2|ii)\b', q_fold):
            target_semester = 'ii'

        target_years = re.findall(r'20\d{2}', q_fold)
        target_years = target_years[:2] if len(target_years) >= 2 else []

        normalized_ctx = self._normalize_text(context_text)
        header_matches = list(re.finditer(r'\[(.*?)\]', normalized_ctx, flags=re.S))

        selected_header = ''
        selected_index = -1
        for idx, match in enumerate(header_matches):
            candidate = self._normalize_text(match.group(1))
            candidate_fold = self._fold_for_match(candidate)
            if target_semester == 'i' and not any(marker in candidate_fold for marker in ['ky i', 'ky 1']):
                continue
            if target_semester == 'ii' and not any(marker in candidate_fold for marker in ['ky ii', 'ky 2']):
                continue
            if target_years and not all(y in candidate_fold for y in target_years):
                continue
            selected_header = candidate
            selected_index = idx
            break

        if selected_index < 0 and header_matches:
            selected_index = 0
            selected_header = self._normalize_text(header_matches[0].group(1))

        if selected_index >= 0:
            start = header_matches[selected_index].end()
            end = header_matches[selected_index + 1].start() if selected_index + 1 < len(header_matches) else len(normalized_ctx)
            working_ctx = normalized_ctx[start:end]
        else:
            working_ctx = normalized_ctx

        compact = re.sub(r'\s+', ' ', working_ctx)
        compact_fold = self._fold_for_match(working_ctx)
        header_fold = self._fold_for_match(selected_header)

        if target_semester == 'i':
            has_semester = any(marker in compact_fold for marker in ['ky i', 'ky 1']) or any(marker in header_fold for marker in ['ky i', 'ky 1'])
        elif target_semester == 'ii':
            has_semester = any(marker in compact_fold for marker in ['ky ii', 'ky 2']) or any(marker in header_fold for marker in ['ky ii', 'ky 2'])
        else:
            has_semester = any(marker in compact_fold for marker in ['thu hoc phi ky', 'le phi hoc ky', 'hoc phi ky', 'thu le phi ky'])
        if not has_semester:
            return None

        title = 'TH\u00d4NG B\u00c1O V\u1ec1 vi\u1ec7c thu h\u1ecdc ph\u00ed K\u1ef3 I, n\u0103m h\u1ecdc 2025-2026'
        so = ''
        ngay = ''
        if selected_header:
            for part in selected_header.split('|'):
                part_norm = self._normalize_text(part).strip()
                if ':' not in part_norm:
                    continue
                value = part_norm.split(':', 1)[1].strip()
                part_fold = self._fold_for_match(part_norm)
                if part_fold.startswith('van ban') and value:
                    title = value
                elif part_fold.startswith('so') and value:
                    so = value
                elif part_fold.startswith('ngay') and value:
                    ngay = value

        def _normalize_amount_token(token: str) -> str:
            cleaned = re.sub(r'[^0-9\.,]', '', token or '').strip('.,')
            return cleaned

        def _amount_value(token: str) -> int:
            digits = re.sub(r'[^0-9]', '', token or '')
            return int(digits) if digits else 0

        def _looks_like_money(token: str) -> bool:
            return bool(re.fullmatch(r'\d{1,3}(?:[\.,]\d{3})+', token or ''))

        def _format_fold_amount(token: str) -> str:
            digits = re.sub(r'[^0-9]', '', token or '')
            if len(digits) > 3:
                return f"{digits[:-3]}.{digits[-3:]}"
            return digits

        tuition_vals = None
        for raw_line in working_ctx.splitlines():
            if '|' not in raw_line:
                continue
            line_fold = self._fold_for_match(raw_line)
            if 'chuong trinh' not in line_fold:
                continue
            nums = [_normalize_amount_token(x) for x in re.findall(r'[0-9][0-9\.,]*', raw_line)]
            valid_nums = [x for x in nums if _looks_like_money(x)]
            if len(valid_nums) >= 3:
                tuition_vals = tuple(valid_nums[-3:])
                break

        if not tuition_vals:
            triple_amount_pattern = re.compile(r'([0-9][0-9\.,]{3,})\s*\|\s*([0-9][0-9\.,]{3,})\s*\|\s*([0-9][0-9\.,]{3,})')
            for match in triple_amount_pattern.finditer(working_ctx):
                prefix = working_ctx[max(0, match.start() - 120):match.start()]
                prefix_fold = self._fold_for_match(prefix)
                if any(marker in prefix_fold for marker in ['chuong trinh', 'hoc phi', 'dai hoc']):
                    candidate = tuple(_normalize_amount_token(x) for x in match.groups())
                    if all(_looks_like_money(x) for x in candidate):
                        tuition_vals = candidate
                        break

        fee_rows: List[Tuple[str, str]] = []
        for m in re.finditer(r'\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([0-9][0-9\.,]*\s*[d\u0111]?)\s*\|', working_ctx, flags=re.IGNORECASE):
            item = re.sub(r'\s+', ' ', m.group(1)).strip(' .;-')
            amount = re.sub(r'\s+', '', m.group(2)).strip()
            if len(item) < 3:
                continue
            if all(item.lower() != existed[0].lower() for existed in fee_rows):
                fee_rows.append((item, amount))

        if not fee_rows:
            m_item = re.search(r'tien dien[^0-9]{0,80}([0-9][0-9\.,]*)\s*d?', compact_fold)
            if m_item:
                fee_rows.append(('Ti\u1ec1n \u0111i\u1ec7n \u0110HN\u0110, ti\u1ec1n n\u01b0\u1edbc u\u1ed1ng (c\u1ea3 n\u0103m)', f"{m_item.group(1)}\u0111"))

        total_fee = ''
        m_total_fold = re.search(r'tong cong\s*([0-9 ]{3,})\s*d', compact_fold)
        if m_total_fold:
            formatted = _format_fold_amount(m_total_fold.group(1))
            if _looks_like_money(formatted):
                total_fee = formatted + '\u0111'

        if not total_fee:
            for raw_line in working_ctx.splitlines():
                if 'tong cong' not in self._fold_for_match(raw_line):
                    continue
                nums = [_normalize_amount_token(x) for x in re.findall(r'[0-9][0-9\.,]*', raw_line)]
                nums = [x for x in nums if _looks_like_money(x)]
                if nums:
                    total_fee = nums[-1] + '\u0111'
                    break

        m_time = re.search(
            r'tu ngay\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})\s*den(?:\s*het)?\s*ngay\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})',
            compact_fold,
        )
        time_range = f"{m_time.group(1)} - {m_time.group(2)}" if m_time else ''

        pay_methods = []
        if 'nop tien mat' in compact_fold:
            pay_methods.append('N\u1ed9p ti\u1ec1n m\u1eb7t t\u1ea1i Ph\u00f2ng K\u1ebf ho\u1ea1ch - T\u00e0i ch\u00ednh (T\u1ea7ng 1, t\u00f2a nh\u00e0 31 D\u1ecbch V\u1ecdng H\u1eadu).')
        if 'qr code' in compact_fold:
            pay_methods.append('N\u1ed9p qua QR-Code \u0111\u1ed9ng tr\u00ean c\u1ed5ng sinh vi\u00ean.')
        if 'the atm noi dia' in compact_fold or 'may pos' in compact_fold:
            pay_methods.append('N\u1ed9p qua th\u1ebb ATM n\u1ed9i \u0111\u1ecba t\u1ea1i Ph\u00f2ng K\u1ebf ho\u1ea1ch - T\u00e0i ch\u00ednh (m\u00e1y POS).')

        portal = ''
        m_url = re.search(r'https?://\S+', working_ctx)
        if m_url:
            portal = m_url.group(0).rstrip('.),;')

        if not tuition_vals and not fee_rows:
            return None

        lines = [f'**{title}**', '']
        meta = []
        if so:
            meta.append(f'**S\u1ed1:** {so}')
        if ngay:
            meta.append(f'**Ng\u00e0y:** {ngay}')
        if meta:
            lines.append(' | '.join(meta))
            lines.append('')

        if tuition_vals:
            lines.append('**M\u1ee9c h\u1ecdc ph\u00ed (\u0111\u1ed3ng/t\u00edn ch\u1ec9):**')
            lines.append(f'- Kh\u00f3a 11: **{tuition_vals[0]}**')
            lines.append(f'- Kh\u00f3a 12: **{tuition_vals[1]}**')
            lines.append(f'- Kh\u00f3a 13: **{tuition_vals[2]}**')
            lines.append('')

        if fee_rows:
            lines.append('**C\u00e1c kho\u1ea3n l\u1ec7 ph\u00ed:**')
            for item, amount in fee_rows[:5]:
                lines.append(f'- {item}: **{amount}**')
            if total_fee:
                lines.append(f'- T\u1ed5ng c\u1ed9ng: **{total_fee}**')
            lines.append('')

        if time_range:
            lines.append(f'**Th\u1eddi gian thu:** {time_range}')
        if portal:
            lines.append(f'**C\u1ed5ng thanh to\u00e1n:** {portal}')
        if pay_methods:
            lines.append('**Ph\u01b0\u01a1ng th\u1ee9c n\u1ed9p:**')
            for method in pay_methods[:3]:
                lines.append(f'- {method}')

        return '\n'.join(lines).strip()


    def _clean_directive_body(self, text: str) -> str:
        cleaned = self._normalize_text(str(text))
        cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
        cleaned = re.sub(r'\[[^\]]+\]', ' ', cleaned)
        cleaned = cleaned.replace('|', ' ')
        cleaned = cleaned.replace('---', ' ')
        for marker in ['Trân trọng', '- Nơi nhận', 'KT. BỘ TRƯỞNG', 'KT. BO TRUONG', 'THỨ TRƯỞNG', 'THU TRUONG']:
            idx = cleaned.find(marker)
            if idx != -1:
                cleaned = cleaned[:idx]
        cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -;,. ')
        return cleaned
    def _build_tet_notice_answer(self, query: str, context_text: str) -> str | None:
        """Deterministic extractor for Tet notice content to avoid LLM omitting key directives."""
        if not query or not context_text:
            return None

        q_fold = self._fold_for_match(query)
        if not ('tet' in q_fold and 'nguyen dan' in q_fold):
            return None

        ctx_fold = self._fold_for_match(context_text)
        if 'tet' not in ctx_fold:
            return None

        working = context_text
        anchor = re.search(r'các công việc sau đây\s*[:.]', working, flags=re.IGNORECASE)
        if anchor:
            working = working[anchor.end():]

        tail_markers = ['- Nơi nhận', 'Trân trọng', 'KT. BỘ TRƯỞNG', 'KT. BO TRUONG', 'THỨ TRƯỞNG', 'THU TRUONG']
        cut_idx = len(working)
        for marker in tail_markers:
            pos = working.find(marker)
            if pos != -1 and pos < cut_idx:
                cut_idx = pos
        working = working[:cut_idx]

        item_pattern = re.compile(
            r'(?m)(?<!\d)(\d{1,2})\s*[\.,]\s*(.+?)(?=(?:\n\s*\d{1,2}\s*[\.,]\s)|\Z)',
            re.S
        )
        directives: Dict[int, str] = {}
        for num_str, body in item_pattern.findall(working):
            num = int(num_str)
            if num < 1 or num > 12:
                continue
            cleaned = self._clean_directive_body(body)
            if len(cleaned) < 40:
                continue
            current = directives.get(num, '')
            if len(cleaned) > len(current):
                directives[num] = cleaned

        if not directives:
            return None

        so = ''
        ngay = ''
        header_match = re.search(r'\[(.*?)\]', context_text, flags=re.S)
        if header_match:
            header = header_match.group(1)
            m_so = re.search(r'Số:\s*([^|]+)', header)
            if m_so:
                so = self._normalize_text(m_so.group(1)).strip()
            m_ngay = re.search(r'Ngày:\s*([^|]+)', header)
            if m_ngay:
                ngay = self._normalize_text(m_ngay.group(1)).strip()

        lines = ['**Thông báo nghỉ Tết Nguyên đán 2026**', '']
        meta = []
        if so:
            meta.append(f'**Số:** {so}')
        if ngay:
            meta.append(f'**Ngày ban hành:** {ngay}')
        if meta:
            lines.append(' | '.join(meta))
            lines.append('')

        for num in sorted(directives.keys()):
            lines.append(f'**Điều {num}:** {directives[num]}')
            lines.append('')

        return '\n'.join(lines).strip()

    def _is_markdown_table_separator(self, line: str) -> bool:
        if not line:
            return False
        return bool(re.match(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$', line))

    def _is_placeholder_cell(self, cell: str) -> bool:
        if cell is None:
            return True
        value = self._normalize_text(str(cell)).strip().lower()
        if not value:
            return True
        if value in {'.', '..', '...', '…', '-', '--', '---', '_'}:
            return True
        if re.fullmatch(r'[\.\-–_\s]+', value):
            return True
        return False

    def _suppress_placeholder_tables(self, response: str) -> str:
        """Remove markdown tables that are only template placeholders (e.g. rows filled with "..." )."""
        if not response or '|' not in response:
            return response

        lines = response.split('\n')
        output = []
        i = 0

        while i < len(lines):
            line = lines[i]
            next_line = lines[i + 1] if i + 1 < len(lines) else ''

            if '|' in line and self._is_markdown_table_separator(next_line):
                j = i + 2
                while j < len(lines) and '|' in lines[j]:
                    j += 1

                table_lines = lines[i:j]
                rows = []
                for row in table_lines:
                    if self._is_markdown_table_separator(row):
                        continue
                    cells = [c.strip() for c in row.strip().strip('|').split('|')]
                    if cells:
                        rows.append(cells)

                data_rows = rows[1:] if len(rows) > 1 else []
                placeholder_rows = 0
                for cells in data_rows:
                    check_cells = cells[1:] if len(cells) > 1 else cells
                    meaningful_cells = [c for c in check_cells if not self._is_placeholder_cell(c)]
                    if not meaningful_cells:
                        placeholder_rows += 1

                if data_rows and placeholder_rows >= max(1, int(len(data_rows) * 0.6)):
                    output.append("*Bảng trong văn bản là biểu mẫu trống/placeholder nên mình không liệt kê từng dòng để tránh gây hiểu sai.*")
                else:
                    output.extend(table_lines)

                i = j
                continue

            output.append(line)
            i += 1

        cleaned = '\n'.join(output)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        return cleaned

    def _clean_context_line(self, line: str) -> str:
        if not line:
            return ""
        text = self._normalize_text(str(line))
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'^[-*]+\s*', '', text)
        text = re.sub(r'^\d+\.\s*', '', text)
        if not text:
            return ""
        lowered = text.lower()
        if text in {'---', '|', '||'}:
            return ""
        if lowered.startswith('[') and lowered.endswith(']'):
            return ""
        if '[đã cắt bớt]' in lowered:
            return ""
        if '|' in text:
            return ""
        return text

    def _detect_document_section(self, line: str) -> str | None:
        folded = self._fold_for_match(line)
        if not folded:
            return None
        if 'doi tuong' in folded and any(k in folded for k in ['ho so', 'mien giam hoc phi', 'nop ho so']):
            return 'Đối tượng và hồ sơ'
        if 'thoi gian' in folded and any(k in folded for k in ['nop ho so', 'nhan ho so', 'han nop']):
            return 'Thời gian nộp hồ sơ'
        if 'dia diem' in folded and any(k in folded for k in ['nop ho so', 'nhan ho so']):
            return 'Địa điểm nộp hồ sơ'
        if 'luu y' in folded or 'han nop hoc phi' in folded:
            return 'Lưu ý'
        return None

    def _collect_document_sections(self, context_text: str) -> Dict[str, List[str]]:
        sections: Dict[str, List[str]] = {
            'Đối tượng và hồ sơ': [],
            'Thời gian nộp hồ sơ': [],
            'Địa điểm nộp hồ sơ': [],
            'Lưu ý': [],
        }
        current_section: str | None = None

        for raw in context_text.split('\n'):
            raw_text = self._normalize_text(str(raw)).strip()
            marker = self._detect_document_section(raw_text)
            if marker:
                current_section = marker

                # Nếu marker line có dữ liệu thực tế (không chỉ là heading), giữ lại làm ý.
                tail = ''
                if ':' in raw_text:
                    tail = raw_text.split(':', 1)[1].strip()
                candidate_tail = self._clean_context_line(tail)
                candidate_full = self._clean_context_line(raw_text)
                candidate = candidate_full if candidate_full else candidate_tail

                is_heading_only = raw_text.endswith(':') and not candidate_tail
                if candidate and not is_heading_only:
                    if candidate not in sections[current_section]:
                        sections[current_section].append(candidate)
                    if len(sections[current_section]) >= 8:
                        current_section = None
                continue

            line = self._clean_context_line(raw_text)
            if not line:
                continue

            if current_section:
                if line not in sections[current_section]:
                    sections[current_section].append(line)
                if len(sections[current_section]) >= 8:
                    current_section = None

        return sections
    def _detect_generic_heading(self, line: str) -> str | None:
        text = self._normalize_text(line).strip()
        if not text:
            return None

        folded = self._fold_for_match(text)
        if not folded:
            return None

        if any(stop in folded for stop in ['noi nhan', 'hieu truong', 'doc lap tu do hanh phuc']):
            return None

        if re.match(r'^(dieu|muc|phan|chuong|khoan)\s*[0-9ivxlc]+', folded):
            return text.rstrip(':').strip()

        numbered = re.match(r'^\s*\d+\.\s*(.+)$', text)
        if numbered:
            candidate = numbered.group(1).strip().rstrip(':')
            candidate_fold = self._fold_for_match(candidate)
            section_tokens = [
                'doi tuong', 'thoi gian', 'dia diem', 'ho so', 'luu y',
                'muc thu', 'hoc phi', 'le phi', 'phuong thuc', 'dieu kien',
                'quyen loi', 'nghia vu', 'thoi han', 'thanh phan',
            ]
            if len(candidate.split()) <= 15 and (
                text.rstrip().endswith(':') or any(tok in candidate_fold for tok in section_tokens)
            ):
                return candidate

        if text.endswith(':'):
            candidate = text.rstrip(':').strip()
            candidate_fold = self._fold_for_match(candidate)
            if 2 <= len(candidate.split()) <= 15 and not re.search(r'\b20\d{2}\b', candidate) and candidate_fold:
                return candidate

        return None

    def _collect_generic_document_sections(self, context_text: str, max_sections: int = 8, max_items: int = 8) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []
        current_section: Dict[str, Any] | None = None

        def get_or_create_section(title: str) -> Dict[str, Any]:
            for sec in sections:
                if self._fold_for_match(sec.get('title', '')) == self._fold_for_match(title):
                    return sec
            sec = {'title': title, 'items': []}
            sections.append(sec)
            return sec

        for raw in context_text.split('\n'):
            raw_text = self._normalize_text(str(raw)).strip()
            if not raw_text:
                continue

            if raw_text.startswith('[') and raw_text.endswith(']'):
                continue

            raw_fold = self._fold_for_match(raw_text)
            if any(skip in raw_fold for skip in ['cong hoa xa hoi chu nghia', 'doc lap tu do hanh phuc']):
                continue

            heading = self._detect_generic_heading(raw_text)
            if heading:
                current_section = get_or_create_section(heading)
                continue

            cleaned = self._clean_context_line(raw_text)
            if not cleaned:
                continue
            if len(cleaned) > 260:
                continue

            if current_section is None:
                continue

            cleaned_fold = self._fold_for_match(cleaned)
            if any(skip in cleaned_fold for skip in ['noi nhan', 'hieu truong', 'ky ten', 'doc lap tu do hanh phuc']):
                continue

            if cleaned not in current_section['items']:
                current_section['items'].append(cleaned)
                if len(current_section['items']) >= max_items:
                    current_section = None

        filtered: List[Dict[str, Any]] = []
        for sec in sections:
            title = str(sec.get('title', '')).strip()
            items = [str(x).strip() for x in sec.get('items', []) if str(x).strip()]
            if not title or not items:
                continue
            if len(title) > 140:
                continue
            filtered.append({'title': title, 'items': items[:max_items]})

        return filtered[:max_sections]

    def _collect_relevant_tables(self, context_text: str, max_tables: int = 2, max_rows: int = 6) -> List[Dict[str, Any]]:
        tables: List[Dict[str, Any]] = []
        lines = context_text.split('\n')
        i = 0

        while i < len(lines) - 1:
            line = lines[i].strip()
            next_line = lines[i + 1].strip()

            if '|' in line and self._is_markdown_table_separator(next_line):
                j = i + 2
                while j < len(lines) and '|' in lines[j]:
                    j += 1

                block = lines[i:j]
                header_cells = [c.strip() for c in block[0].strip().strip('|').split('|') if c.strip()]
                if not header_cells:
                    i = j
                    continue

                rows: List[List[str]] = []
                for raw_row in block[2:]:
                    cells = [c.strip() for c in raw_row.strip().strip('|').split('|')]
                    if not any(cells):
                        continue
                    if all(self._is_placeholder_cell(c) for c in cells):
                        continue
                    if any(re.search(r'\d{1,3}(?:[\.,]\d{3})+', c) for c in cells):
                        norm_row = cells[:len(header_cells)]
                        if len(norm_row) < len(header_cells):
                            norm_row += [''] * (len(header_cells) - len(norm_row))
                        rows.append(norm_row)

                if rows:
                    table_fold = self._fold_for_match(' '.join(header_cells) + ' ' + ' '.join(' '.join(r) for r in rows))
                    tables.append({'headers': header_cells, 'rows': rows[:max_rows], 'table_fold': table_fold})

                i = j
                continue

            i += 1

        return tables[:max_tables]

    def _render_compact_markdown_table(self, headers: List[str], rows: List[List[str]]) -> List[str]:
        if not headers:
            return []

        col_count = max(len(headers), max((len(r) for r in rows), default=0))
        norm_headers = headers[:col_count] + [f'C\u1ed9t {idx}' for idx in range(len(headers) + 1, col_count + 1)]

        rendered = [
            '| ' + ' | '.join(norm_headers) + ' |',
            '| ' + ' | '.join(['---'] * col_count) + ' |',
        ]

        for row in rows:
            norm_row = row[:col_count]
            if len(norm_row) < col_count:
                norm_row += [''] * (col_count - len(norm_row))
            rendered.append('| ' + ' | '.join(norm_row) + ' |')

        return rendered

    def _build_generic_document_outline(self, query: str, context_text: str) -> str | None:
        if not query or not context_text:
            return None

        sections = self._collect_generic_document_sections(context_text)
        tables = self._collect_relevant_tables(context_text)

        if len(sections) < 2 and not tables:
            return None

        q_fold = self._fold_for_match(query)
        stop_tokens = {'cho', 'toi', 'biet', 've', 'va', 'la', 'gi', 'noi', 'dung', 'cua', 'nam', 'hoc', 'ky'}
        query_tokens = [t for t in q_fold.split() if len(t) >= 3 and t not in stop_tokens]

        scored_sections: List[Tuple[int, int, Dict[str, Any]]] = []
        for idx, sec in enumerate(sections):
            haystack = self._fold_for_match(sec['title'] + ' ' + ' '.join(sec['items'][:6]))
            score = sum(1 for token in query_tokens if token in haystack)

            if any(k in q_fold for k in ['hoc phi', 'le phi', 'muc thu', 'chi phi']) and any(k in haystack for k in ['hoc phi', 'le phi', 'muc thu']):
                score += 4
            if 'noi dung' in q_fold:
                score += max(0, 2 - idx)

            scored_sections.append((score, idx, sec))

        scored_sections.sort(key=lambda item: (-item[0], item[1]))
        selected = [sec for _, _, sec in scored_sections[:4]] if scored_sections else sections[:4]

        header = ''
        for raw in context_text.split('\n'):
            t = raw.strip()
            if t.startswith('[') and t.endswith(']'):
                header = t.strip('[]')
                break

        lines: List[str] = []
        if header:
            lines.append(f'**{header}**')
            lines.append('')

        normalized_query = self._normalize_text(query).strip()
        lines.append(f'**N\u1ed9i dung ch\u00ednh theo y\u00eau c\u1ea7u:** {normalized_query}')
        lines.append('')

        for sec in selected:
            title = sec.get('title', '').strip()
            items = sec.get('items', [])
            if not title or not items:
                continue
            lines.append(f'**{title}:**')
            for item in items[:6]:
                lines.append(f'- {item}')
            lines.append('')

        query_needs_table = any(k in q_fold for k in ['hoc phi', 'le phi', 'muc thu', 'so tien', 'bang'])
        if tables and (query_needs_table or len(selected) < 2):
            chosen_table = tables[0]
            if 'hoc phi' in q_fold:
                for table in tables:
                    tf = str(table.get('table_fold', ''))
                    if any(k in tf for k in ['chuong trinh', 'khoa 11', 'tin chi', 'muc thu hoc phi']):
                        chosen_table = table
                        break
            elif 'le phi' in q_fold:
                for table in tables:
                    tf = str(table.get('table_fold', ''))
                    if any(k in tf for k in ['le phi', 'noi dung thu', 'tong cong']):
                        chosen_table = table
                        break

            lines.append('**B\u1ea3ng d\u1eef li\u1ec7u li\u00ean quan:**')
            lines.append('')
            lines.extend(self._render_compact_markdown_table(chosen_table['headers'], chosen_table['rows']))
            lines.append('')

        rebuilt = '\n'.join(lines).strip()
        if len(rebuilt) < 120:
            return None
        return rebuilt

    def _enrich_document_info_response(self, response: str, context_text: str, query: str) -> str:
        """Generalized post-processing: rebuild answer from sections/tables when LLM output is partial."""
        if not response or not context_text:
            return response

        generic = self._build_generic_document_outline(query, context_text)
        if not generic:
            return response

        folded_response = self._fold_for_match(response)
        query_fold = self._fold_for_match(query)

        # N?u LLM tr? l?i/no-data ng?n nh?ng context c? d? li?u th? tr? b?n outline t?ng qu?t.
        if any(err in folded_response for err in ['xin loi', 'su co ket noi', 'khong tim thay thong tin']) and len(folded_response) < 240:
            return generic

        generic_titles = []
        for line in generic.split('\n'):
            m = re.match(r'^\*\*(.+?):\*\*$', line.strip())
            if m:
                generic_titles.append(m.group(1))

        section_overlap = 0
        for title in generic_titles[:5]:
            if self._fold_for_match(title) in folded_response:
                section_overlap += 1

        context_money_count = len(re.findall(r'\d{1,3}(?:[\.,]\d{3})+', context_text))
        response_money_count = len(re.findall(r'\d{1,3}(?:[\.,]\d{3})+', response))

        if len(generic_titles) >= 3 and section_overlap <= 1:
            return generic

        if context_money_count >= 3 and response_money_count < 2:
            return generic

        if 'noi dung' in query_fold and len(response) < int(len(generic) * 0.55):
            return generic

        return response

    def _needs_document_search(self, query: str, history: List[str] = None) -> bool:
        """
        Pattern matching nhanh để quyết định có cần tìm kiếm tài liệu không.
        Sử dụng regex thay vì gọi LLM để nhanh hơn ~3 giây.
        """
        query = self._normalize_text(query)
        query_lower = query.lower().strip()
        
        # Strip dấu câu cuối để match chính xác (VD: "bạn là ai?" → "bạn là ai")
        query_stripped = query_lower.rstrip('?!.,;: ')

        # Nhận diện biến thể chào hỏi/cảm ơn để không kéo vào RAG
        if re.match(r'^(xin\s+chào|chào\b|hello\b|hi\b|hey\b)', query_stripped):
            return False
        if re.match(r'^(cảm\s*ơn|thanks\b|thank you\b)', query_stripped):
            return False
        
        # Các patterns hội thoại - KHÔNG cần RAG
        conversational_patterns = [
            'xin chào', 'chào bạn', 'chào', 'hello', 'hi', 'hey',
            'bạn là ai', 'cảm ơn', 'thanks', 'thank you', 'tạm biệt', 'bye',
            'bạn khỏe không', 'có gì mới', 'bạn tên gì', 'ai tạo ra bạn',
            'bạn có thể làm gì', 'bạn giúp gì được'
        ]
        
        # Trả về False cho lời chào/hội thoại (dùng query đã strip dấu câu)
        if query_stripped in conversational_patterns:
            return False
        
        # Các từ khóa gợi ý cần tìm kiếm tài liệu
        rag_keywords = [
            # Liên quan đến trường/đại học
            'fbu', 'trường', 'đại học', 'tài chính', 'ngân hàng',
            # Các patterns tìm kiếm thông tin
            'thông tin', 'biết gì', 'cho biết', 'giới thiệu', 'là gì', 'như thế nào',
            'ở đâu', 'khi nào', 'bao nhiêu', 'có những', 'danh sách',
            # Liên quan học vụ
            'học phí', 'quy định', 'thủ tục', 'lịch', 'đăng ký',
            'miễn giảm', 'học bổng', 'hồ sơ', 'thông báo', 'chính sách',
            'điểm', 'môn học', 'tín chỉ', 'khoa','viện', 'ngành', 'chương trình',
            'học kỳ', 'kỳ thi', 'tốt nghiệp', 'bằng', 'chứng chỉ',
            # Liên hệ/địa điểm
            'phòng', 'văn phòng', 'liên hệ', 'địa chỉ', 'email', 'số điện thoại',
            # Con người
            'giảng viên', 'sinh viên', 'cán bộ', 'nhân viên', 'hiệu trưởng',
            # Cơ sở vật chất
            'cơ sở', 'ký túc xá', 'thư viện', 'phòng học', 'sân', 'câu lạc bộ'
        ]
        
        if any(kw in query_lower for kw in rag_keywords):
            return True
        
        # Follow-up patterns - cần RAG nếu có lịch sử hội thoại
        if history and len(history) > 0:
            # Các cụm dài → match substring bình thường
            followup_long = [
                'còn', 'khác', 'thì sao', 'nữa không', 'nữa', 'thêm',
                'chi tiết', 'rõ hơn', 'cụ thể', 'giải thích', 'tại sao',
                'vậy sao', 'bao giờ', 'như nào'
            ]
            # Các từ ngắn → dùng word boundary (\b) để tránh false positive
            # VD: 'ai' trong 'bạn là ai' KHÔNG phải follow-up
            followup_short = ['vậy', 'thế', 'sao', 'hả', 'nhỉ', 'đâu', 'mấy', 'gì', 'ai', 'nào']
            
            if any(p in query_lower for p in followup_long):
                print(f"[DEBUG] Follow-up detected (long): '{query}' → trigger RAG")
                return True
            
            # Từ ngắn: chỉ match nếu là từ đứng riêng (không nằm trong conversational pattern)
            if query_stripped not in conversational_patterns:
                # MỚI: Xử lý các câu follow-up rất ngắn hỏi về đối tượng khác (VD: "của Tươi", "về Nam")
                if len(query_lower.split()) <= 6 and query_lower.startswith(('của ', 'về ', 'còn ', 'cho ')):
                    print(f"[DEBUG] Follow-up detected (short object): '{query}' → trigger RAG")
                    return True

                for p in followup_short:
                    if re.search(r'\b' + re.escape(p) + r'\b', query_lower):
                        # Kiểm tra query không phải là câu hội thoại ngắn
                        if len(query_lower.split()) > 3:  # Câu có > 3 từ mới tính follow-up
                            print(f"[DEBUG] Follow-up detected (short): '{query}' → trigger RAG")
                            return True
        
        # FIX 7: Câu hỏi có dấu ? luôn trigger RAG (người dùng đang hỏi thật)
        # NHƯNG: Bỏ qua nếu là câu hội thoại (đã check ở trên không match vì có history)
        if '?' in query_lower and len(query_lower) > 8 and query_stripped not in conversational_patterns:
            return True
        
        # Mặc định: nếu query dài hơn 10 ký tự, có thể là câu hỏi cần RAG
        if len(query_lower) > 15:
            return True
        
        return False

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Trích xuất keywords quan trọng từ query cho keyword search.
        FIX 3: Ưu tiên tìm cụm tên đầy đủ (2-4 từ viết hoa liên tiếp) trước,
        sau đó mới fallback sang từ đơn.
        """
        query = self._normalize_text(query)
        keywords = []
        
        # === MỚI: Tìm chuỗi tên đầy đủ (2-4 từ viết hoa liên tiếp) ===
        # VD: "Nguyễn Hoàng Nam" thay vì chỉ "Nam"
        full_name_pattern = re.findall(
            r'\b(?:[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][a-zàáâãèéêìíòóôõùúăđĩũơưạ-ỹ]+\s+){1,3}'
            r'[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][a-zàáâãèéêìíòóôõùúăđĩũơưạ-ỹ]+\b',
            query
        )
        keywords.extend(full_name_pattern)
        
        # Các từ phổ biến tiếng Việt KHÔNG phải tên riêng
        common_words = {
            'cho', 'của', 'và', 'hoặc', 'trong', 'về', 'với', 'theo',
            'tôi', 'bạn', 'này', 'đó', 'các', 'những', 'một', 'hai',
            'xin', 'hãy', 'nếu', 'khi', 'sau', 'trước', 'từ', 'đến',
            'tại', 'trên', 'dưới', 'là', 'có', 'được', 'không', 'đã',
            'sẽ', 'đang', 'rất', 'nhiều', 'ít', 'thì', 'mà', 'để',
            'vì', 'nên', 'cũng', 'còn', 'lại', 'ra', 'vào', 'lên',
            'xuống', 'biết', 'làm', 'gì', 'nào', 'đâu', 'sao', 'thế',
            'như', 'nữa', 'đây', 'kia', 'ấy', 'họ', 'chúng',
            # Từ liên quan học vụ (không phải tên riêng)
            'điểm', 'rèn', 'luyện', 'học', 'kỳ', 'sinh', 'viên',
            'lớp', 'khoa', 'viện', 'trường', 'môn', 'tín', 'chỉ',
            'thông', 'tin', 'phí', 'quy', 'định', 'hồ', 'sơ',
            'thủ', 'tục', 'đăng', 'ký', 'năm', 'kết', 'quả',
            'danh', 'sách', 'bảng', 'xếp', 'loại', 'giỏi', 'khá',
            'trung', 'bình', 'yếu', 'kém', 'xuất', 'sắc', 'tốt',
        }
        
        # Từng từ đơn viết hoa (fallback) — chỉ thêm nếu chưa có trong full_name
        words = query.split()
        for word in words:
            clean = word.strip('?,.!')
            if len(clean) >= 2 and clean[0].isupper() and clean.lower() not in common_words:
                # Chỉ thêm nếu chưa nằm trong cụm tên đầy đủ
                already_in_full = any(clean in fn for fn in full_name_pattern)
                if not already_in_full:
                    keywords.append(clean)

        # Add lowercase domain phrases so keyword/hybrid still works when embeddings fail.
        q_lower = query.lower()
        q_folded = self._fold_for_match(query)
        domain_phrases = [
            'điểm rèn luyện', 'công nhận', 'quyết định', 'thông báo',
            'học phí', 'miễn giảm', 'học bổng', 'lịch thi', 'tốt nghiệp'
        ]
        for phrase in domain_phrases:
            phrase_folded = self._fold_for_match(phrase)
            if phrase in q_lower or (phrase_folded and phrase_folded in q_folded):
                keywords.append(phrase)

        # --- TASK 9: BOOST BM25 VOCABULARY ---
        # Ánh xạ từ đồng nghĩa hành chính cho Keyword Search để Vector Store 
        # bắt được các từ khóa đồng nghĩa cứng mà Embedding có thể bỏ sót
        admin_synonyms = {
            "lệ phí": ["học phí", "lệ phí", "tiền học", "thu tiền"],
            "học phí": ["học phí", "lệ phí", "tiền học", "thu tiền"],
            "nước uống": ["nước uống", "tiền nước", "thu tiền nước"],
            "nhập học": ["nhập học", "tân sinh viên", "trúng tuyển"]
        }
        
        for root_word, variants in admin_synonyms.items():
            if any(v in q_lower for v in variants):
                keywords.extend(variants)

        # Lowercase token fallback (keep Vietnamese letters)
        lower_tokens = re.findall(r'[\wÀ-ỹ]{3,}', q_lower)
        for token in lower_tokens:
            if token not in common_words and not token.isdigit():
                keywords.append(token)

        # Tìm mã sinh viên (chuỗi số 7-10 ký tự)
        student_ids = re.findall(r'\b(\d{7,10})\b', query)
        keywords.extend(student_ids)
        # Tìm năm học/năm để khóa đúng tài liệu theo niên khóa
        year_ranges = re.findall(r'\b(20\d{2}\s*[-/]\s*20\d{2})\b', query)
        for yr in year_ranges:
            cleaned_range = re.sub(r'\s+', '', yr)
            keywords.append(cleaned_range)
            keywords.append(cleaned_range.replace('/', '-'))

        years = re.findall(r'\b20\d{2}\b', query)
        keywords.extend(years)

        
        # Tìm các cụm từ đặc biệt trong ngoặc kép
        quoted = re.findall(r'["\'](.+?)["\']', query)
        keywords.extend(quoted)
        
        # Deduplicate giữ thứ tự
        seen = set()
        result = []
        for kw in keywords:
            if kw.lower() not in seen and len(kw) >= 2:
                seen.add(kw.lower())
                result.append(kw)
        
        return result

    async def _generate_conversational_response(self, query: str, history: List[str]) -> str:
        """
        Tạo phản hồi cho các câu hỏi hội thoại không cần RAG.
        """
        prompt = f"""{FORMATTING_SYSTEM_PROMPT}

Bạn là Chat Bot AI của FBU.
- Nếu hỏi "bạn là ai": trả lời là chatbot FBU, trường đại học Tài chính - Ngân hàng Hà Nội
- Nếu hỏi "ai tạo ra": trả lời Nguyễn Văn Lợi, SV năm 4 FBU khóa 11
Trả lời ngắn gọn, thân thiện bằng tiếng Việt.

Câu hỏi: {query}
Trả lời:"""

        return await self.llm.generate_response(prompt)

    def _filter_results(self, search_results, query_analysis, search_strategy: str = 'hybrid'):
        if not search_results:
            return []
        
        # Lấy score cao nhất làm baseline
        max_score = max((r.score for r in search_results if hasattr(r, 'score') and r.score), default=0)
        if max_score <= 1e-9 and search_strategy != 'keyword':
            # Semantic/hybrid all-zero scores usually indicates embedding failure.
            print('[WARN] All vector scores are 0.0 -> drop semantic/hybrid hits.')
            return []
        
        # Nếu score cao nhất < 0.5 → kết quả tệ, hạ ngưỡng xuống để không bỏ sót
        if max_score < 0.5:
            threshold = max_score * 0.7  # Lấy top 30% tốt nhất
        else:
            threshold = 0.45  # Ngưỡng thực tế hợp lý hơn cho tiếng Việt
        
        valid = []
        for hit in search_results:
            content = hit.payload.get('content', '')
            content_type = hit.payload.get('content_type', '')
            
            # FIX A: Lọc rác HTML mạnh hơn
            # 1. Kiểm tra tỷ lệ empty <td></td> tags
            td_empty = content.count('<td></td>')
            td_total = content.count('<td')
            if td_total > 0 and td_empty / max(td_total, 1) > 0.4:
                print(f"[DEBUG] SKIP chunk (empty-td ratio {td_empty}/{td_total}): {content[:60]}...")
                continue
            
            # 2. Với table chunk: strip html/markdown noise rồi kiểm tra text thực tế
            if content_type in {'table_html_scan', 'table_md_scan', 'table_md'}:
                stripped = re.sub(r'<[^>]+>', ' ', content)
                stripped = stripped.replace('|', ' ')
                stripped = re.sub(r'\s+', ' ', stripped).strip()
                if len(stripped) < 50:
                    print(f"[DEBUG] SKIP garbage table chunk (stripped len={len(stripped)})")
                    continue
            
            score = getattr(hit, 'score', 0) or 0
            if score >= threshold:
                valid.append(hit)
        
        print(f"[DEBUG] max_score={max_score:.3f}, threshold={threshold:.3f}, valid={len(valid)}/{len(search_results)}")
        return valid

    async def _expand_with_same_doc_chunks(self, hits: List, excluded_content_types: List[str] = None) -> List:
        """
        DOCUMENT-LEVEL EXPANSION (Fix tổng quát):
        Khi search trả về 1-2 chunks từ 1 document, tự động lấy thêm
        TẤT CẢ chunks còn lại từ cùng document đó.
        
        CHỈ expand top 2 documents (theo số hits) để tránh nhiễu.
        """
        if not hits:
            return hits
        
        # Thu thập doc_ids và đếm hits per doc
        seen_ids = set()
        doc_hit_count = {}  # doc_id → count of hits
        for hit in hits:
            seen_ids.add(str(hit.id))
            doc_id = hit.payload.get('doc_id')
            if doc_id:
                doc_hit_count[doc_id] = doc_hit_count.get(doc_id, 0) + 1
        
        if not doc_hit_count:
            return hits
        
        # Chỉ expand TOP 2 documents có nhiều hits nhất
        sorted_docs = sorted(doc_hit_count.items(), key=lambda x: x[1], reverse=True)
        top_doc_ids = [doc_id for doc_id, _ in sorted_docs[:2]]
        
        print(f"📄 [Expansion] Top docs: {[(d, doc_hit_count[d]) for d in top_doc_ids]}")
        
        expanded = list(hits)  # Giữ nguyên hits gốc
        MAX_EXPANSION_PER_DOC = 10  # Giới hạn chunks thêm per doc
        
        for doc_id in top_doc_ids:
            all_doc_chunks = await self.vector_store.scroll_by_doc_id(doc_id)
            all_doc_chunks = sorted(all_doc_chunks, key=self._chunk_order_key)
            added = 0
            for chunk in all_doc_chunks:
                if added >= MAX_EXPANSION_PER_DOC:
                    break
                    
                chunk_id = str(chunk.id)
                if chunk_id in seen_ids:
                    continue
                
                # Kiểm tra content_type exclusion
                content_type = chunk.payload.get('content_type', '')
                if excluded_content_types and content_type in excluded_content_types:
                    continue
                
                # Bỏ qua chunk rác (quá ngắn hoặc HTML rỗng)
                content = chunk.payload.get('content', '')
                if not content or len(content.strip()) < 30:
                    continue
                
                seen_ids.add(chunk_id)
                expanded.append(chunk)
                added += 1
            
            if added > 0:
                print(f"📄 [Expansion] doc_id={doc_id}: +{added} chunks (total: {len(expanded)})")
        
        return expanded


    def _extract_query_year_constraints(self, query: str) -> Tuple[set, set]:
        query = self._normalize_text(query)
        years = {int(y) for y in re.findall(r'\b20\d{2}\b', query)}
        ranges = {
            tuple(sorted((int(a), int(b))))
            for a, b in re.findall(r'\b(20\d{2})\s*[-/]\s*(20\d{2})\b', query)
        }
        return years, ranges

    def _extract_hit_year_constraints(self, hit) -> Tuple[set, set]:
        payload = getattr(hit, 'payload', {}) or {}
        text = ' '.join([
            str(payload.get('title', '')),
            str(payload.get('date', '')),
            str(payload.get('source', '')),
            str(payload.get('content', '')),
        ])
        years = {int(y) for y in re.findall(r'\b20\d{2}\b', text)}
        ranges = {
            tuple(sorted((int(a), int(b))))
            for a, b in re.findall(r'\b(20\d{2})\s*[-/]\s*(20\d{2})\b', text)
        }
        return years, ranges

    def _extract_query_topic_terms(self, query: str) -> List[str]:
        q = self._normalize_text(query).lower()
        candidate_terms = [
            'miễn giảm học phí', 'miễn, giảm học phí', 'miễn giảm', 'học phí', 'hồ sơ',
            'học bổng', 'điểm rèn luyện', 'lịch thi', 'đổi lịch thi', 'tết', 'nguyên đán',
            'thu học phí', 'lệ phí', 'tốt nghiệp', 'học kỳ'
        ]
        terms = []
        for t in candidate_terms:
            if t in q and t not in terms:
                terms.append(t)
        return terms[:5]

    def _fold_for_match(self, text: str) -> str:
        """Accent-insensitive normalization for robust OCR/text matching."""
        base = self._normalize_text(text)
        if not base:
            return ""
        decomposed = unicodedata.normalize("NFKD", base)
        without_marks = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
        lowered = without_marks.lower()
        lowered = re.sub(r'[^0-9a-z]+', ' ', lowered)
        return re.sub(r'\s+', ' ', lowered).strip()

    def _topic_matches(self, text: str, topic_terms: List[str]) -> bool:
        if not topic_terms:
            return True
        folded_text = self._fold_for_match(text)
        if not folded_text:
            return False
        for term in topic_terms:
            folded_term = self._fold_for_match(term)
            if folded_term and folded_term in folded_text:
                return True
        return False

    def _apply_topic_guard(self, hits: List, query: str) -> List:
        """
        Guard against cross-topic false positives.
        For strict topics (e.g. Tết/Nguyên đán), if no hit matches topic terms,
        return empty list so system falls back to deterministic "no data" response.
        """
        if not hits:
            return hits

        q = self._normalize_text(query).lower()
        topic_terms = self._extract_query_topic_terms(query)
        if not topic_terms:
            return hits

        matched = []
        for hit in hits:
            payload = getattr(hit, 'payload', {}) or {}
            haystack = ' '.join([
                str(payload.get('title', '')),
                str(payload.get('source', '')),
                str(payload.get('content', '')),
            ])
            if self._topic_matches(haystack, topic_terms):
                matched.append(hit)

        if matched:
            return matched

        strict_topics = ['tết', 'nguyên đán']
        if any(term in q for term in strict_topics):
            print("[Topic Guard] Strict topic requested but no topic-matched hit found.")
            return []

        return hits

    def _apply_explicit_year_filter(self, hits: List, query: str) -> List:
        """Apply hard preference for explicit year/year-range in user query."""
        if not hits:
            return hits

        query_years, query_ranges = self._extract_query_year_constraints(query)
        topic_terms = self._extract_query_topic_terms(query)
        if not query_years:
            return hits

        def collect_matches(require_topic: bool):
            exact_matches = []
            full_year_matches = []
            partial_matches = []

            for hit in hits:
                hit_payload = getattr(hit, 'payload', {}) or {}
                hit_text = ' '.join([
                    str(hit_payload.get('title', '')),
                    str(hit_payload.get('source', '')),
                    str(hit_payload.get('content', '')),
                ])
                if require_topic and topic_terms and not self._topic_matches(hit_text, topic_terms):
                    continue

                hit_years, hit_ranges = self._extract_hit_year_constraints(hit)
                if query_ranges and hit_ranges and query_ranges.intersection(hit_ranges):
                    exact_matches.append(hit)
                    continue

                if query_years and hit_years and query_years.issubset(hit_years):
                    full_year_matches.append(hit)
                    continue

                if query_years and hit_years and query_years.intersection(hit_years):
                    partial_matches.append(hit)
                    continue

            return exact_matches, full_year_matches, partial_matches

        exact_matches, full_year_matches, partial_matches = collect_matches(require_topic=True)
        if topic_terms and not (exact_matches or full_year_matches or partial_matches):
            # OCR scan/source names may not pass strict topic term check; retry with year-only.
            print("📅 [Year Filter] No strict topic+year match. Reverting to base hits to preserve topic.")
            return hits

        if query_ranges:
            if exact_matches:
                print(f"📅 [Year Filter] exact year-range hits: {len(exact_matches)}/{len(hits)}")
                return exact_matches
            if full_year_matches:
                print(f"📅 [Year Filter] full-year hits (range fallback): {len(full_year_matches)}/{len(hits)}")
                return full_year_matches
            if partial_matches:
                print(f"📅 [Year Filter] partial-year hits (range fallback): {len(partial_matches)}/{len(hits)}")
                return partial_matches
            return hits

        if len(query_years) >= 2:
            if full_year_matches:
                print(f"📅 [Year Filter] full multi-year hits: {len(full_year_matches)}/{len(hits)}")
                return full_year_matches
            if partial_matches:
                print(f"📅 [Year Filter] partial multi-year hits: {len(partial_matches)}/{len(hits)}")
                return partial_matches
            return hits

        # Single year: allow partial matches directly
        if partial_matches:
            print(f"📅 [Year Filter] single-year hits: {len(partial_matches)}/{len(hits)}")
            return partial_matches

        return hits

    def _chunk_order_key(self, hit) -> Tuple[int, str]:
        payload = getattr(hit, 'payload', {}) or {}
        chunk_id = str(payload.get('chunk_id', ''))
        m = re.search(r'(\d+)$', chunk_id)
        if m:
            return int(m.group(1)), chunk_id
        return 10**9, chunk_id

    def _focus_on_primary_document(self, hits: List) -> List:
        """Keep chunks from the dominant doc_id to avoid mixing unrelated documents."""
        if not hits:
            return hits

        doc_stats = defaultdict(lambda: {'count': 0, 'best_score': 0.0})
        for hit in hits:
            doc_id = hit.payload.get('doc_id')
            if doc_id is None:
                continue
            doc_stats[doc_id]['count'] += 1
            score = float(getattr(hit, 'score', 0) or 0)
            if score > doc_stats[doc_id]['best_score']:
                doc_stats[doc_id]['best_score'] = score

        if not doc_stats:
            return hits

        primary_doc = max(doc_stats.items(), key=lambda item: (item[1]['count'], item[1]['best_score']))[0]
        focused = [h for h in hits if h.payload.get('doc_id') == primary_doc]
        focused = sorted(focused, key=self._chunk_order_key)
        print(f"🎯 [Doc Focus] Keep doc_id={primary_doc}: {len(focused)}/{len(hits)} chunks")
        return focused if focused else hits

    def _rerank_by_query_type(self, results: List, analysis: Dict) -> List:
        """Re-rank results dựa trên query type để ưu tiên chunks phù hợp và DỮ LIỆU MỚI"""
        scored_results = []
        original_query_lower = unicodedata.normalize('NFC', analysis.get('original_query', '')).lower()
        current_year = datetime.datetime.now().year
        query_years = {int(y) for y in re.findall(r'\b20\d{2}\b', original_query_lower)}
        query_year_ranges = {tuple(sorted((int(a), int(b)))) for a, b in re.findall(r'\b(20\d{2})\s*[-/]\s*(20\d{2})\b', original_query_lower)}
        
        for r in results:
            score_raw = getattr(r, 'score', None)
            # Keep real 0.0 score to avoid artificial boost.
            score = float(score_raw) if score_raw is not None else 0.5
            chunk_type = r.payload.get('chunk_type', '')
            content_lower = r.payload.get('content', '').lower()
            
            # Bonus cho preferred chunk types
            if chunk_type in analysis.get('preferred_chunk_types', []):
                bonus = 0.3 / max(len(analysis['preferred_chunk_types']), 1)
                score += bonus
            
            # Bonus cho time match
            if analysis.get('time_filter') and 'time_info' in r.payload:
                if analysis['time_filter'] in r.payload['time_info']:
                    score += 0.2
            
            # Bonus cho column match
            column_mentions = analysis.get('column_mentions', [])
            if column_mentions:
                matches = sum(1 for col in column_mentions if col.lower() in content_lower)
                if matches > 0:
                    score += 0.15 * (matches / len(column_mentions))

            # =========================================================
            # DOCUMENT TITLE RELEVANCE BONUS (FIX TỔNG QUÁT)
            # =========================================================
            # Sử dụng TOPIC GROUPS để phân biệt các chủ đề gần giống nhau.
            doc_title = r.payload.get('title', '').lower()
            if doc_title and original_query_lower:
                topic_groups = {
                    'thu_hoc_phi': ['thu học phí', 'thu phí', 'lệ phí'],
                    'mien_giam': ['miễn', 'giảm học phí', 'miễn, giảm'],
                    'hoc_bong': ['học bổng', 'cấp học bổng'],
                    'diem_ren_luyen': ['điểm rèn luyện', 'rèn luyện'],
                    'lich_thi': ['lịch thi', 'đổi lịch'],
                    'tet': ['tết', 'nguyên đán'],
                    'tot_nghiep': ['tốt nghiệp']
                }
                
                # Phân loại query_group theo mức độ ưu tiên (để tránh overlap "học phí" & "miễn giảm")
                query_group = None
                if any(m in original_query_lower for m in ['miễn giảm', 'miễn, giảm', 'giảm học phí', 'đối tượng miễn', 'hồ sơ miễn']):
                    query_group = 'mien_giam'
                elif any(m in original_query_lower for m in ['học phí', 'lệ phí', 'thu phí', 'phí kỳ', 'phương thức nộp', 'cách nộp', 'tiền mặt']):
                    query_group = 'thu_hoc_phi'
                elif any(m in original_query_lower for m in ['học bổng', 'thành tích']):
                    query_group = 'hoc_bong'
                elif any(m in original_query_lower for m in ['điểm rèn luyện', 'rèn luyện']):
                    query_group = 'diem_ren_luyen'
                elif any(m in original_query_lower for m in ['lịch thi', 'ngày thi']):
                    query_group = 'lich_thi'
                elif any(m in original_query_lower for m in ['tết', 'nguyên đán', 'bính ngọ']):
                    query_group = 'tet'
                elif any(m in original_query_lower for m in ['tốt nghiệp']):
                    query_group = 'tot_nghiep'
                
                if query_group:
                    title_markers = topic_groups[query_group]
                    # Doc title khớp cùng group → BONUS mạnh
                    title_matches_same = any(m in doc_title for m in title_markers)
                    if title_matches_same:
                        score += 0.20
                    else:
                        # Doc title khớp group KHÁC → PENALTY
                        for other_group, other_markers in topic_groups.items():
                            if other_group != query_group:
                                if any(m in doc_title for m in other_markers):
                                    score -= 0.10
                                    break

            # =========================================================
            # =========================================================
            # YEAR MATCH FIRST (nếu user chỉ định năm thì ưu tiên đúng năm)
            # =========================================================
            doc_date = r.payload.get('date', '')
            doc_title = r.payload.get('title', '')
            scan_text = f"{doc_title} {content_lower}"

            doc_years = set(int(y) for y in re.findall(r'\b20\d{2}\b', str(doc_date)))
            doc_years.update(int(y) for y in re.findall(r'\b20\d{2}\b', scan_text))

            doc_year_ranges = {
                tuple(sorted((int(a), int(b))))
                for a, b in re.findall(r'\b(20\d{2})\s*[-/]\s*(20\d{2})\b', f"{doc_date} {scan_text}")
            }

            doc_max_year = max(doc_years) if doc_years else None

            if query_year_ranges and doc_year_ranges:
                if query_year_ranges.intersection(doc_year_ranges):
                    score += 0.35  # Khớp đúng cặp năm học (VD 2024-2025)
                elif query_years.intersection(doc_years):
                    score -= 0.10  # Chỉ khớp 1 năm trong cặp => khả năng lệch niên khóa
                else:
                    score -= 0.30
            elif query_years and doc_years:
                if query_years.intersection(doc_years):
                    score += 0.25
                else:
                    score -= 0.25
            elif query_years and not doc_years:
                score -= 0.05

            # =========================================================
            # RECENCY BIAS (chỉ dùng khi query KHÔNG chỉ định năm cụ thể)
            # =========================================================
            if doc_max_year and not query_years:
                year_diff = doc_max_year - current_year

                if year_diff >= 0:
                    score += 0.15
                elif year_diff == -1:
                    score += 0.05
                elif year_diff <= -2:
                    score -= 0.10

            # Xếp hạng Học kỳ: CHỈ áp dụng nếu query YÊU CẦU CỤ THỂ HOẶC nếu KHÔNG ĐỀ CẬP thì mới ưu tiên kỳ mới.
            requested_hk1 = any(q in original_query_lower for q in ["kỳ 1", "kỳ i", "hk1"])
            requested_hk2 = any(q in original_query_lower for q in ["kỳ 2", "kỳ ii", "hk2"])
            requested_hk3 = any(q in original_query_lower for q in ["kỳ 3", "kỳ phụ", "hk3"])
            
            # Xử lý khi user có hỏi cụ thể về kỳ
            if requested_hk1 or requested_hk2 or requested_hk3:
                # Nếu hỏi Kỳ 1, thưởng mạnh cho văn bản chứa Kỳ 1, phạt văn bản chứa kỳ 2, 3
                if requested_hk1:
                    if "hk1" in content_lower or "kỳ 1" in content_lower or "kỳ i" in content_lower:
                        score += 0.15
                    if "hk2" in content_lower or "kỳ 2" in content_lower or "kỳ ii" in content_lower:
                        score -= 0.10
                elif requested_hk2:
                    if "hk2" in content_lower or "kỳ 2" in content_lower or "kỳ ii" in content_lower:
                        score += 0.15
                    if "hk1" in content_lower or "kỳ 1" in content_lower or "kỳ i" in content_lower:
                        score -= 0.10
                elif requested_hk3:
                    if "hk3" in content_lower or "kỳ 3" in content_lower or "kỳ phụ" in content_lower:
                        score += 0.15
                    if "hk1" in content_lower or "kỳ 1" in content_lower or "kỳ i" in content_lower:
                        score -= 0.10
            else:
                # Nếu user KO HỎI kỳ nào -> MỚI áp dụng fallback là Ưu tiên kỳ sau đè kỳ trước "mặc định"
                if "hk3" in content_lower or "kỳ 3" in content_lower or "kỳ phụ" in content_lower:
                    score += 0.015
                elif "hk2" in content_lower or "kỳ 2" in content_lower or "kỳ ii" in content_lower:
                    score += 0.010
                elif "hk1" in content_lower or "kỳ 1" in content_lower or "kỳ i" in content_lower:
                    score += 0.005
            
            scored_results.append((r, score))
        
        # =========================================================
        # QUERY KEYWORD MATCH BONUS
        # =========================================================
        query_keywords = analysis.get('keywords', [])
        if query_keywords:
            for i, (r, score) in enumerate(scored_results):
                content_lower = r.payload.get('content', '').lower()
                kw_matches = sum(1 for kw in query_keywords if kw.lower() in content_lower)
                if kw_matches > 0:
                    bonus = 0.05 * (kw_matches / len(query_keywords))
                    scored_results[i] = (r, score + bonus)
        
        # Sort by score descending
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored_results]

    def _build_optimized_context(self, valid_hits: List) -> str:
        MAX_CONTEXT_LENGTH = 15000  # Tăng lên (15k libs~ 4k tokens) để đảm bảo không bị cắt mất thông tin quan trọng ở cuối (dễ mất field Date)
        context_parts = []
        current_length = 0

        # Nhóm hits theo doc_id để các chunks cùng tài liệu được xếp liền nhau
        from collections import OrderedDict
        doc_groups = OrderedDict()
        for hit in valid_hits:
            doc_id = hit.payload.get('doc_id', 'unknown')
            if doc_id not in doc_groups:
                doc_groups[doc_id] = []
            doc_groups[doc_id].append(hit)
        
        # Flatten: giữ thứ tự ưu tiên nhưng nhóm liền các chunk cùng doc
        grouped_hits = []
        for doc_id, hits in doc_groups.items():
            hits_sorted = sorted(hits, key=self._chunk_order_key)
            grouped_hits.extend(hits_sorted)

        for hit in grouped_hits:
            if current_length >= MAX_CONTEXT_LENGTH:
                break

            payload = hit.payload
            content = payload.get('content', '')
            content_type = payload.get('content_type', payload.get('chunk_type', ''))

            # Bỏ qua chunk rác HTML (mở rộng filter)
            if not content or len(content.strip()) < 20:
                continue
            td_empty = content.count('<td></td>')
            td_total = content.count('<td')
            if td_total > 0 and td_empty / max(td_total, 1) > 0.4:
                continue  # Hơn 40% cell rỗng → rác

            # FIX B: Giữ cấu trúc bảng cho markdown table, chỉ clean tối thiểu
            if content_type in {'table_html_scan', 'table_md_scan', 'table_md'}:
                if content_type == 'table_html_scan':
                    content = re.sub(r'\s+', ' ', content).strip()
                    if len(re.sub(r'<[^>]+>', '', content)) < 30:
                        continue
                else:
                    content = re.sub(r'\n{3,}', '\n\n', content).strip()
                    if len(content.replace('|', ' ').strip()) < 30:
                        continue
            # Cắt content nếu quá dài
            if len(content) > 2000:
                content = content[:2000] + "\n...[đã cắt bớt]"

            # Build header từ metadata
            header_parts = []
            for field, label in [('title', 'Văn bản'), ('doc_number', 'Số'),
                                  ('date', 'Ngày'), ('issuer', 'Cơ quan')]:
                val = payload.get(field, '')
                if val and val != 'Không xác định':
                    header_parts.append(f"{label}: {val}")

            # FIX context: Chỉ giữ metadata hữu ích, bỏ score/type debug info
            header = f"[{' | '.join(header_parts) if header_parts else payload.get('source', 'Tài liệu')}]"

            part = f"{header}\n{content}"
            context_parts.append(part)
            current_length += len(part)

        return "\n\n---\n\n".join(context_parts)

    # =================================================================
    # Conversation Summary Memory
    # =================================================================
    def _build_context_history(self, session: UserSession) -> List[str]:
        """Ghép summary + recent turns → history ngắn gọn, đủ ngữ cảnh."""
        history = []
        
        if session.summary:
            history.append(f"[Tóm tắt hội thoại trước: {session.summary}]")
        
        # Thêm các tin nhắn gần nhất (raw)
        history.extend(session.recent_turns[-4:])
        
        return history

    async def _update_session_memory(self, session: UserSession,
                                     user_msg: str, bot_msg: str):
        """Sau mỗi lượt hỏi-đáp, cập nhật memory."""
        
        # Thêm vào recent_turns (cắt bot response dài)
        session.recent_turns.append(f"User: {user_msg}")
        session.recent_turns.append(f"Bot: {bot_msg[:400]}")  # FIX 6: Lưu dài hơn để nhớ ngữ cảnh tốt
        session.turn_count += 1
        
        # Cứ 4 lượt → tóm tắt lại, xóa bớt history cũ
        if session.turn_count % 4 == 0 and len(session.recent_turns) > 4:
            summary_prompt = f"""Tóm tắt ngắn gọn (tối đa 100 từ) nội dung cuộc hội thoại sau,
giữ lại các thông tin quan trọng như tên sinh viên, MSV, điểm số đã hỏi:

{chr(10).join(session.recent_turns)}

Tóm tắt:"""
            try:
                new_summary = await self.llm.generate_response(summary_prompt)
                if session.summary:
                    session.summary = f"{session.summary} | {new_summary[:200]}"
                else:
                    session.summary = new_summary[:200]
                # Xóa history cũ, chỉ giữ 4 tin nhắn cuối
                session.recent_turns = session.recent_turns[-4:]
                print(f"[DEBUG] Session summary updated: {session.summary[:80]}...")
            except Exception:
                # Nếu lỗi → cắt bớt để tránh phình
                session.recent_turns = session.recent_turns[-6:]

    # =================================================================
    # Helper: Pre-lookup MSV bằng tên (Fix cho RAG Semantic nhiễu)
    # =================================================================
    async def _lookup_student_msv_by_name(self, name: str) -> List[Tuple[str, str]]:
        """
        Tra cứu trực tiếp vào VectorDB chỉ lấy học sinh (MSV, Tên đầy đủ)
        dựa trên tên được cung cấp. Cố gắng tìm trong các file excel_table, student_list.
        Returns: List of tuples [(msv, full_name), ...]
        """
        if not name:
            return []
            
        print(f"🔍 [Pre-Lookup] Tự động tra cứu MSV cho tên: '{name}'")
        name_words = name.split()
        
        # Chỉ tập trung vào file chứa danh sách sinh viên
        filter_dict = {
            "should": [
                {"key": "content_type", "match": {"value": "student_list"}},
                {"key": "content_type", "match": {"value": "excel_table"}}
            ]
        }
        
        # Search bằng keyword search với tên
        results = await self.vector_store.keyword_search(
            keywords=name_words,
            limit=20,
            filter_dict=filter_dict
        )
        
        matched_students = []
        for hit in results:
            content = hit.payload.get('content', '')
            # Tìm trong bảng markdown: | STT | MSV | Họ tên |
            rows = re.findall(
                r'\|\s*\d+\s*\|\s*(\d{10})\s*\|\s*([^|]+?)\s*\|',
                content
            )
            for msv, full_name in rows:
                msv = msv.strip()
                full_name = full_name.strip()
                # Kiểm tra tất cả cụm từ của tên có xuất hiện trong full_name không
                if all(w.lower() in full_name.lower() for w in name_words):
                    entry = (msv, full_name)
                    if entry not in matched_students:
                        matched_students.append(entry)
                        
        print(f"📊 [Pre-Lookup] Kết quả tìm MSV cho '{name}': {matched_students}")
        return matched_students

    # =================================================================
    # Helper: Trích xuất tên người từ câu hỏi
    # =================================================================
    def _looks_like_person_name(self, candidate: str) -> bool:
        """Heuristic guard to avoid treating document topics as personal names."""
        if not candidate:
            return False

        cleaned = self._normalize_text(candidate)
        if re.search(r'\d', cleaned):
            return False

        tokens = [t for t in cleaned.split() if t]
        if len(tokens) < 2 or len(tokens) > 5:
            return False

        forbidden = {
            'thông', 'báo', 'quyết', 'định', 'công', 'văn', 'nội', 'dung',
            'điểm', 'rèn', 'luyện', 'học', 'phí', 'học', 'bổng', 'miễn',
            'giảm', 'hồ', 'sơ', 'quy', 'trình', 'thủ', 'tục', 'nghỉ',
            'tết', 'nguyên', 'đán', 'năm', 'học', 'kỳ', 'thời', 'gian'
        }

        hit_forbidden = sum(1 for t in tokens if t.lower() in forbidden)
        if hit_forbidden >= max(2, len(tokens) - 1):
            return False

        return True

    def _extract_person_name(self, query: str) -> str | None:
        """Trích xuất tên người trong ngữ cảnh tra cứu sinh viên, tránh bắt nhầm chủ đề văn bản."""
        query = self._normalize_text(query)
        q = query.lower()

        person_hints = [
            'msv', 'mã sinh viên', 'sinh viên', 'điểm của',
            'điểm rèn luyện', 'điểm thi', 'điểm rèn luyện của',
            'xếp loại của', 'kết quả học tập của', 'của'
        ]
        if not any(h in q for h in person_hints):
            return None

        # [NEW] Ưu tiên tìm các cụm từ viết hoa rõ ràng (đúng chuẩn tên riêng) vì refined_query thường viết hoa đúng chuẩn
        spans = re.findall(
            r'\b[A-ZÀ-Ỹ][\wÀ-ỹ]{1,6}(?:\s+[A-ZÀ-Ỹ][\wÀ-ỹ]{1,6}){1,4}\b',
            query
        )
        for span in reversed(spans):
            # Tránh các cụm như 'Đại Học', 'Tài Chính', 'Ngân Hàng', 'Hà Nội'
            if 'Đại Học' not in span and 'Tài Chính' not in span and 'Ngân Hàng' not in span and 'Hà Nội' not in span:
                if self._looks_like_person_name(span):
                    return span

        # Fallback: Ưu tiên cụm ngay sau "của"/"về" (cho trường hợp user query không viết hoa)
        match = re.search(
            r'(?:của|hỏi về|về)\s+(?:sinh viên|bạn|bạn tên|người tên)?\s*([\wÀ-ỹ]+(?:\s+[\wÀ-ỹ]+){1,4})',
            query,
            re.IGNORECASE
        )
        if match:
            candidate = match.group(1).strip()
            # Cắt các hậu tố câu hỏi phổ biến (nếu có)
            candidate = re.split(r'\b(là|bao nhiêu|như thế nào|ra sao|học|tại)\b', candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            if self._looks_like_person_name(candidate):
                return " ".join(word.capitalize() for word in candidate.split())

        return None

    # =================================================================
    def _should_use_safe_ocr_answer(self, query: str, query_intent: str, hits: List) -> bool:
        """Detect low-quality OCR-only contexts where LLM is likely to hallucinate."""
        if not hits or query_intent == 'student_lookup':
            return False

        q = self._normalize_text(query).lower()
        doc_like_query = any(k in q for k in [
            'nội dung', 'quy định', 'thông báo', 'quyết định', 'hồ sơ',
            'thủ tục', 'miễn giảm', 'học phí', 'lịch'
        ])
        if not doc_like_query:
            return False

        content_types = [str(h.payload.get('content_type', '')).lower() for h in hits]
        table_scan_count = sum(1 for ct in content_types if ct in {'table_html_scan', 'table_md_scan', 'table_md'})
        text_count = sum(1 for ct in content_types if ct == 'text')
        unknown_titles = 0
        for h in hits:
            title = self._normalize_text(str(h.payload.get('title', ''))).lower()
            if not title or title == 'không xác định':
                unknown_titles += 1

        mostly_table_scan = table_scan_count >= max(3, int(len(hits) * 0.7))
        mostly_unknown_meta = unknown_titles >= max(2, int(len(hits) * 0.6))

        return mostly_table_scan and text_count == 0 and mostly_unknown_meta

    def _build_safe_ocr_answer(self, user_query: str, query_intent: str, hits: List) -> str | None:
        """Return deterministic low-risk summary for noisy OCR contexts."""
        if not self._should_use_safe_ocr_answer(user_query, query_intent, hits):
            return None

        top_source = ''
        for h in hits:
            src = self._normalize_text(str(h.payload.get('source', '')))
            if src:
                top_source = src
                break

        display_source = top_source or 'Tài liệu scan (OCR)'
        display_source = re.sub(r'^\d{14}_', '', display_source)
        display_source = re.sub(r'_(\d{4})\.pdf$', r'.pdf', display_source, flags=re.IGNORECASE)

        snippets = []
        for hit in hits[:20]:
            content = str(hit.payload.get('content', ''))
            if not content:
                continue
            cleaned = re.sub(r'<[^>]+>', ' ', content)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if len(cleaned) >= 30:
                snippets.append(cleaned)

        combined_text = ' '.join(snippets)
        folded = self._fold_for_match(f"{display_source} {combined_text}")

        facts = []
        year_ranges = re.findall(r'\b20\d{2}\s*[-/]\s*20\d{2}\b', f"{display_source} {combined_text}")
        if year_ranges:
            yr = re.sub(r'\s+', '', year_ranges[0]).replace('/', '-')
            facts.append(f"Nội dung có nhắc tới năm học **{yr}**.")

        if 'mien giam hoc phi' in folded:
            facts.append("Tài liệu đề cập hồ sơ **miễn, giảm học phí** cho sinh viên.")

        if 'hoc ky ii' in folded or 'hk ii' in folded or 'hk2' in folded:
            facts.append("Phạm vi áp dụng có nhắc tới **học kỳ II**.")

        if 'giay khai sinh' in folded:
            facts.append("Trong hồ sơ có nhắc tới **giấy khai sinh**.")

        if any(k in folded for k in ['ho ngheo', 'can ngheo', 'xac nhan']):
            facts.append("Có nhắc tới giấy tờ **xác nhận đối tượng/hộ nghèo-cận nghèo**.")

        dates = []
        for d in re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b', combined_text):
            if d not in dates:
                dates.append(d)
            if len(dates) >= 2:
                break
        if dates:
            facts.append(f"Mốc thời gian OCR đọc được: {', '.join(f'`{d}`' for d in dates)}.")

        if not facts:
            facts.append("Bản OCR bị nhiễu mạnh, chưa đủ dữ liệu để trích xuất chính xác từng điều khoản.")

        lines = [
            f"**Tài liệu liên quan:** {display_source}",
            "",
            "Dữ liệu OCR khá nhiễu nên mình chỉ nêu các ý chắc chắn đọc được:",
        ]
        lines.extend([f"- {f}" for f in facts])
        lines.append("")
        lines.append("Nếu bạn cần độ chính xác cao theo từng điều/mục, mình sẽ trích nguyên văn từng đoạn OCR để bạn đối chiếu trực tiếp.")

        return '\n'.join(lines)

    # FIX 5: Phát hiện hallucination — LLM bịa MSV không có trong context
    # =================================================================
    def _validate_response(self, response: str, context: str) -> str:
        """Kiểm tra response có chứa MSV bịa không có trong context."""
        if not response or not context:
            return response
        
        # Tìm tất cả MSV (10 chữ số) trong response và context
        resp_ids = set(re.findall(r'\b\d{10}\b', response))
        ctx_ids = set(re.findall(r'\b\d{10}\b', context))
        
        # MSV có trong response nhưng KHÔNG có trong context = bịa
        fake_ids = resp_ids - ctx_ids
        
        if fake_ids:
            print(f"⚠️ [HALLUCINATION] Phát hiện MSV bịa: {fake_ids}")
            # Xóa các dòng chứa MSV bịa khỏi response
            lines = response.split('\n')
            clean_lines = []
            for line in lines:
                line_ids = set(re.findall(r'\b\d{10}\b', line))
                if not line_ids.intersection(fake_ids):
                    clean_lines.append(line)
            
            cleaned = '\n'.join(clean_lines).strip()
            if cleaned and len(cleaned) > 20:
                return cleaned
            # Nếu xóa hết thì giữ nguyên nhưng thêm cảnh báo
            return response + "\n\n⚠️ *Lưu ý: Một số thông tin có thể chưa được xác minh chính xác.*"
        
        return response

    # =================================================================
    # FIX 1: Xử lý tên người mơ hồ — hỏi lại thay vì đoán mò
    # =================================================================
    def _detect_ambiguous_name(self, query: str, hits: List) -> str | None:
        """
        Nếu user hỏi bằng tên (không MSV) và tìm thấy >1 người khớp → trả về tên đó.
        """
        # Không check nếu có MSV trong query
        if re.search(r'\b\d{10}\b', query):
            return None
        
        # Trích xuất tên từ query (chữ hoa đầu, không phải từ thông thường)
        name_words = re.findall(
            r'\b[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][a-zàáâãèéêìíòóôõùúăđĩũơưạ-ỹ]+\b',
            query
        )
        if not name_words:
            return None
        
        # Gom tất cả tên sinh viên từ hits
        matched_students = []
        for hit in hits:
            content = hit.payload.get('content', '')
            for name_word in name_words:
                # Tìm trong bảng markdown: | STT | MSV | Họ tên |
                rows = re.findall(
                    r'\|\s*\d+\s*\|\s*(\d{10})\s*\|\s*([^|]+?)\s*\|',
                    content
                )
                for msv, full_name in rows:
                    if name_word.lower() in full_name.lower():
                        entry = (msv.strip(), full_name.strip())
                        if entry not in matched_students:
                            matched_students.append(entry)
        
        # Chỉ báo mơ hồ nếu tìm thấy >1 người
        if len(matched_students) > 1:
            print(f"[DEBUG] Ambiguous name detected: '{name_words[0]}' → {len(matched_students)} matches")
            return name_words[0]  # Trả về từ khóa tên gây mơ hồ
        
        return None

    def _build_clarification_response(self, name_keyword: str, hits: List) -> str:
        """Tạo câu hỏi làm rõ với danh sách sinh viên tìm được."""
        matched = []
        for hit in hits:
            content = hit.payload.get('content', '')
            rows = re.findall(
                r'\|\s*\d+\s*\|\s*(\d{10})\s*\|\s*([^|]+?)\s*\|',
                content
            )
            for msv, full_name in rows:
                if name_keyword.lower() in full_name.lower():
                    entry = (msv.strip(), full_name.strip())
                    if entry not in matched:
                        matched.append(entry)
        
        if not matched:
            return f"Mình không tìm thấy sinh viên nào tên **{name_keyword}** trong dữ liệu."
        
        lines = [f"Mình tìm thấy **{len(matched)} sinh viên** có tên chứa \"{name_keyword}\", bạn muốn hỏi về ai?\n"]
        for msv, name in matched:
            lines.append(f"- **{name}** — MSV: `{msv}`")
        lines.append("\nBạn hãy nhập **mã sinh viên** để mình tìm chính xác nhé!")
        
        return "\n".join(lines)

    # =================================================================
    # FIX 5: Parse chính xác dữ liệu SV từ markdown table — bypass LLM
    # =================================================================
    def _extract_student_data_from_hits(self, hits: List, target_id: str) -> List[dict]:
        """
        Parse regex trực tiếp từ markdown table — chính xác 100%, không qua LLM.
        Giải quyết vấn đề LLM đọc nhầm dòng giữa 2 chunk.
        """
        records = []
        
        for hit in hits:
            payload = hit.payload
            content = payload.get('content', '')
            
            # Chỉ xử lý chunk có chứa MSV này
            if target_id not in content:
                continue
            
            # === Lấy học kỳ từ content ===
            hk_match = re.search(
                r'(?:Đợt|đợt)\s*[:\s]*([HKhk]+\d)\s*[\(\[]?\s*(20\d{2}[-–]\d{2,4})',
                content, re.IGNORECASE
            )
            if not hk_match:
                # Thử tìm trong title của doc
                title = payload.get('title', '')
                hk_match = re.search(
                    r'(HK\d|Kỳ\s*[I1-9]+|học kỳ\s*\d)\s*[,\s]*(20\d{2}[-–]\d{2,4})',
                    title, re.IGNORECASE
                )
            hoc_ky = f"{hk_match.group(1).upper()} ({hk_match.group(2)})" if hk_match else "Không rõ kỳ"
            
            # === Parse đúng dòng chứa target_id ===
            # Bảng markdown: | STT | MSV | Họ tên | Giới tính | Ngày sinh | Điểm | Xếp loại |
            row_pattern = re.compile(
                r'\|\s*\d+\s*\|'                              # STT
                r'\s*' + re.escape(target_id) + r'\s*\|'       # MSV khớp chính xác
                r'\s*([^|]+?)\s*\|'                            # Họ tên
                r'\s*([^|]*?)\s*\|'                            # Giới tính  
                r'\s*([^|]*?)\s*\|'                            # Ngày sinh
                r'\s*(\d+)\s*\|'                               # Điểm số
                r'\s*([^|]+?)\s*\|'                            # Xếp loại
            )
            
            for match in row_pattern.finditer(content):
                records.append({
                    'msv': target_id,
                    'ho_ten': match.group(1).strip(),
                    'diem': match.group(4).strip(),
                    'xep_loai': match.group(5).strip(),
                    'hoc_ky': hoc_ky,
                })
        
        # Deduplicate: cùng MSV + cùng HK + cùng điểm → giữ 1
        seen = set()
        unique = []
        for r in records:
            key = (r['msv'], r['hoc_ky'], r['diem'])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        
        # Sắp xếp mới nhất trước
        def sort_key(r):
            hk = r['hoc_ky']
            year_m = re.search(r'20(\d{2})', hk)
            hk_m = re.search(r'HK(\d)', hk, re.IGNORECASE)
            year = int(year_m.group(1)) if year_m else 0
            hk_num = int(hk_m.group(1)) if hk_m else 0
            return (year, hk_num)
        
        unique.sort(key=sort_key, reverse=True)
        print(f"[DEBUG] Extracted {len(unique)} student records for MSV {target_id}")
        return unique

    def _build_security_filter(self, user: User) -> Dict:
        # Cấu trúc filter của Qdrant
        # Chỉ tìm kiếm tài liệu active và có quyền truy cập
        return {
            "must": [
                # Chỉ tìm tài liệu đang active
                {"key": "is_active", "match": {"value": True}}
            ],
            "should": [
                {"key": "access_scope", "match": {"value": "public"}},
                {"key": "scope", "match": {"value": "public"}},  # Key thay thế
            ]
        }


























