from typing import List, Dict, Any
import re
from collections import defaultdict
from app.services.llm_client import LLMClient
from app.services.vector_store import VectorStore
from app.models.user import User
from pyvi import ViTokenizer

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

    async def chat(self, user_query: str, history: List[str], user_info: User) -> dict:
        """
        Trả về: dict với các key 'answer', 'sources', và 'has_related_docs'
        """
        # Bước 0: Kiểm tra người dùng có yêu cầu tài liệu rõ ràng không
        wants_documents = self._wants_documents(user_query)
        print(f"[DEBUG] Query: {user_query}, Wants documents: {wants_documents}")
        
        # Nếu người dùng yêu cầu tài liệu, trả về sources đã cache
        if wants_documents:
            user_id = str(user_info.id) if user_info else "anonymous"
            cached = self._cached_sources.get(user_id, [])
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
        needs_rag = self._needs_document_search(user_query, history)
        print(f"[DEBUG] Query: {user_query}, Needs RAG: {needs_rag}")
        
        if not needs_rag:
            # Với các câu hỏi hội thoại, trả lời trực tiếp không cần RAG
            response = await self._generate_conversational_response(user_query, history)
            return {'answer': response, 'sources': [], 'has_related_docs': False}
        
        # Bước 2: Viết lại Query để truy xuất tốt hơn
        refined_query = await self.llm.rewrite_query(user_query, history)
        print(f"[DEBUG] Refined query: {refined_query}")
        
        # Bước 3: Xây dựng Security Filter
        filters = self._build_security_filter(user_info)
        print(f"[DEBUG] Filter: {filters}")
        
        # Bước 4: Phân tích query (Excel optimization)
        query_analysis = self.query_processor.analyze_query(user_query)
        print(f"[DEBUG] Query Analysis: Type={query_analysis['query_type']}, Strategy={query_analysis['search_strategy']}, Preferred={query_analysis['preferred_chunk_types']}")
        
        # Bước 5: Trích xuất keywords từ cả query gốc và refined query
        keywords = self._extract_keywords(user_query)
        refined_keywords = self._extract_keywords(refined_query)
        # Gộp keywords, ưu tiên refined (chứa context từ history)
        all_kw = list(dict.fromkeys(keywords + refined_keywords))  # dedupe giữ thứ tự
        # Bổ sung keywords từ query analysis
        for kw in query_analysis.get('keywords', []):
            if kw not in all_kw:
                all_kw.append(kw)
        print(f"[DEBUG] Extracted keywords: {all_kw}")
        
        # Bước 6: Enhance filter với chunk_type và time_info preferences
        enhanced_filters = filters.copy()
        
        # Thêm chunk_type filter nếu có preference rõ ràng (≤ 2 types)
        if len(query_analysis['preferred_chunk_types']) <= 2 and query_analysis['preferred_chunk_types']:
            if 'should' not in enhanced_filters:
                enhanced_filters['should'] = []
            for chunk_type in query_analysis['preferred_chunk_types']:
                enhanced_filters['should'].append({
                    'key': 'chunk_type',
                    'match': {'value': chunk_type}
                })
        
        # Thêm time filter nếu có
        if query_analysis.get('time_filter'):
            if 'must' not in enhanced_filters:
                enhanced_filters['must'] = []
            enhanced_filters['must'].append({
                'key': 'time_info',
                'match': {'value': query_analysis['time_filter']}
            })
        
        # Bước 7: Tách từ tiếng Việt cho query (BẮT BUỘC)
        # Vì documents đã được tokenize bằng ViTokenizer khi ingestion,
        # query cũng phải tokenize để vector khoảng cách chính xác.
        tokenized_query = ViTokenizer.tokenize(refined_query)
        tokenized_kw = [ViTokenizer.tokenize(kw) for kw in all_kw] if all_kw else []
        print(f"[DEBUG] Tokenized query: {tokenized_query[:100]}")
        
        # Bước 8: Search dựa trên strategy từ query analysis
        search_strategy = query_analysis['search_strategy']
        
        if search_strategy == 'keyword' and tokenized_kw:
            search_results = await self.vector_store.keyword_search(
                keywords=tokenized_kw,
                limit=40,
                filter_dict=enhanced_filters
            )
        elif search_strategy == 'semantic' or not tokenized_kw:
            search_results = await self.vector_store.search(
                tokenized_query, limit=40, filter_dict=enhanced_filters
            )
        else:  # hybrid (default)
            search_results = await self.vector_store.hybrid_search(
                query=tokenized_query, 
                keywords=tokenized_kw, 
                limit=40, 
                filter_dict=enhanced_filters
            )

        print(f"[DEBUG] Raw search results count: {len(search_results)} (strategy: {search_strategy})")
        for i, hit in enumerate(search_results[:10]):  # Log top 10
            score = hit.score if hasattr(hit, 'score') and hit.score else 0
            filename = hit.payload.get('source', hit.payload.get('filename', 'N/A'))
            chunk_type = hit.payload.get('chunk_type', 'N/A')
            content_preview = hit.payload.get('content', '')[:80]
            print(f"[DEBUG] Result {i+1}: score={score:.4f}, type={chunk_type}, file={filename}, content={content_preview}")
        
        # Áp dụng ngưỡng độ tương đồng
        THRESHOLD = 0.5
        valid_hits = [hit for hit in search_results if (hasattr(hit, 'score') and hit.score and hit.score >= THRESHOLD) or not hasattr(hit, 'score')]
        
        # Bước 8: Re-rank results dựa trên query type
        valid_hits = self._rerank_by_query_type(valid_hits, query_analysis)
        
        print(f"[DEBUG] After threshold ({THRESHOLD}) + re-rank: {len(valid_hits)} valid hits")
        
        # --- Nếu không tìm thấy tài liệu nào phù hợp, để LLM trả lời linh hoạt ---
        if not valid_hits:
            no_doc_prompt = f"""Bạn là Chat Bot AI của FBU (Trường Đại học Tài chính - Ngân hàng Hà Nội).

Người dùng hỏi: {refined_query}

Bạn KHÔNG tìm thấy thông tin nào liên quan trong cơ sở dữ liệu tài liệu.

QUY TẮC:
1. Trả lời lịch sự, tự nhiên, thân thiện bằng tiếng Việt.
2. Thừa nhận rằng bạn chưa có dữ liệu về nội dung này.
3. Gợi ý người dùng thử hỏi cách khác, hoặc liên hệ phòng ban phù hợp nếu cần.
4. KHÔNG bịa đặt thông tin.
5. Giữ câu trả lời NGẮN GỌN (2-3 câu).

Trả lời:"""
            response = await self.llm.generate_response(no_doc_prompt)
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
                    'score': round(hit.score, 2)
                })
        
        # Cache sources cho user này (cho khi họ hỏi tài liệu sau)
        user_id = str(user_info.id) if user_info else "anonymous"
        self._cached_sources[user_id] = sources
        
        # Kiểm tra xem có tài liệu liên quan để gợi ý không
        has_related_docs = len(sources) > 0
        
        # 4. Tạo phản hồi - KHÔNG tự động đính kèm sources
        prompt = f"""Bạn là Chat Bot AI của FBU (Trường Đại học Tài chính - Ngân hàng Hà Nội).

Ngữ cảnh:
{context_text}

QUY TẮC BẮT BUỘC:
1. Trả lời NGẮN GỌN, CHÍNH XÁC, ĐI THẲNG VÀO CÂU TRẢ LỜI.
2. Đưa ra SỐ LIỆU CỤ THỂ (điểm, ngày, mã SV...) từ ngữ cảnh — KHÔNG làm tròn, không ước lượng.
3. Khi người dùng hỏi chung chung (ví dụ: "điểm"), nhưng ngữ cảnh chỉ có một loại cụ thể (ví dụ: "điểm rèn luyện"), phải NÓI RÕ loại điểm đó là gì (ví dụ: "Tìm thấy thông tin **Điểm rèn luyện**...").
4. Khi có nhiều kỳ: liệt kê TỪNG KỲ riêng biệt, sắp xếp MỚI NHẤT trước (dựa vào dòng "THỜI GIAN").
5. Khi hỏi "mới nhất"/"gần nhất": so sánh NĂM HỌC trước, rồi HỌC KỲ (HK2 > HK1).
6. TUYỆT ĐỐI KHÔNG đề cập tên file, tên nguồn, [Nguồn: ...].
7. KHÔNG bình phẩm, nhận xét, phân tích xu hướng.
8. KHÔNG viết "Dựa trên tài liệu", "Thông tin cho thấy".
9. Nếu ngữ cảnh KHÔNG CÓ thông tin chính xác về câu hỏi (ví dụ hỏi "điểm thi" mà chỉ có "điểm rèn luyện"), hãy trả lời: "Xin lỗi, hiện tại tôi chưa có dữ liệu chính xác cho câu hỏi này trong tài liệu." và gợi ý thông tin có sẵn nếu liên quan.
10. KHÔNG TỰ BỊA ĐẶT thông tin nếu không có trong ngữ cảnh.
11. 100% tiếng Việt, Markdown, **in đậm** ý chính.

VÍ DỤ 1 (Hỏi về điểm):
Hỏi: "điểm của Nguyễn Văn A"
Ngữ cảnh có: "Điểm rèn luyện HK1 2024: 90"
Đáp:
Thông tin **Điểm rèn luyện** của sinh viên **Nguyễn Văn A** (MSV: 225480xxxx):
- **HK1, 2024-2025**: **90 điểm** — Xuất sắc.
*(Lưu ý: Tài liệu chỉ chứa thông tin điểm rèn luyện, chưa có điểm học tập)*

VÍ DỤ 2 (Hỏi về kỳ mới nhất):
Hỏi: "kỳ mới nhất được bao nhiêu"
Đáp:
Kỳ mới nhất là **HK1, 2025-2026**: **90 điểm** — Xuất sắc.

Câu hỏi: {refined_query}

Trả lời:"""
        
        response = await self.llm.generate_response(prompt)
        
        # Trả về câu trả lời KHÔNG kèm sources, nhưng báo hiệu có tài liệu liên quan
        return {
            'answer': response,
            'sources': [],  # Không tự động đính kèm sources
            'has_related_docs': has_related_docs  # Flag cho frontend hiển thị gợi ý
        }

    def _wants_documents(self, query: str) -> bool:
        """
        Kiểm tra người dùng có yêu cầu xem tài liệu/nguồn không.
        """
        query_lower = query.lower().strip()
        
        # Các patterns chỉ ra người dùng muốn xem tài liệu
        doc_request_patterns = [
            'xem tài liệu', 'cho tôi tài liệu', 'tài liệu tham khảo',
            'xem văn bản', 'cho xem tài liệu', 'muốn xem tài liệu',
            'đưa tài liệu', 'gửi tài liệu', 'tải tài liệu', 'download',
            'nguồn tham khảo', 'xem nguồn', 'cho xem nguồn',
            'có', 'có muốn', 'muốn xem', 'xem', 'cho xem',
            'tài liệu nào', 'văn bản nào', 'file nào'
        ]
        
        # Cũng kiểm tra các câu trả lời xác nhận cho gợi ý tài liệu
        affirmative_patterns = [
            'có', 'ok', 'được', 'ừ', 'vâng', 'đồng ý', 'cho xem', 'xem đi'
        ]
        
        # Kiểm tra query có khớp patterns yêu cầu tài liệu không
        if any(p in query_lower for p in doc_request_patterns):
            return True
        
        # Câu trả lời xác nhận ngắn có thể có nghĩa "có" cho gợi ý tài liệu
        if query_lower in affirmative_patterns or len(query_lower) <= 5:
            # Chỉ coi là yêu cầu tài liệu nếu là câu xác nhận đơn giản
            if any(query_lower == p or query_lower.startswith(p) for p in affirmative_patterns):
                return True
        
        return False

    def _needs_document_search(self, query: str, history: List[str] = None) -> bool:
        """
        Pattern matching nhanh để quyết định có cần tìm kiếm tài liệu không.
        Sử dụng regex thay vì gọi LLM để nhanh hơn ~3 giây.
        """
        query_lower = query.lower().strip()
        
        # Các patterns hội thoại - KHÔNG cần RAG
        conversational_patterns = [
            'xin chào', 'chào bạn', 'chào', 'hello', 'hi', 'hey',
            'bạn là ai', 'cảm ơn', 'thanks', 'thank you', 'tạm biệt', 'bye',
            'bạn khỏe không', 'có gì mới'
        ]
        
        # Chỉ trả về False cho lời chào chính xác
        if query_lower in conversational_patterns:
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
            followup_patterns = [
                'còn', 'khác', 'thì sao', 'nữa không', 'nữa', 'thêm',
                'chi tiết', 'rõ hơn', 'cụ thể', 'giải thích', 'tại sao',
                'vậy', 'thế', 'sao', 'hả', 'nhỉ', 'vậy sao', 'đâu',
                'bao giờ', 'mấy', 'gì', 'ai', 'nào', 'như nào'
            ]
            if any(p in query_lower for p in followup_patterns):
                print(f"[DEBUG] Follow-up detected: '{query}' → trigger RAG")
                return True
        
        # Mặc định: nếu query dài hơn 10 ký tự, có thể là câu hỏi cần RAG
        if len(query_lower) > 15:
            return True
        
        return False

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Trích xuất keywords quan trọng từ query cho keyword search.
        Chỉ tìm: tên riêng (viết hoa đúng), mã SV, cụm từ trong ngoặc.
        """
        keywords = []
        
        # 1. Tìm tên riêng: từ có chữ cái đầu viết HOA (dùng Python isupper)
        words = query.split()
        
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
        
        for word in words:
            # Chỉ lấy từ có chữ cái đầu viết HOA (tên riêng)
            if len(word) >= 2 and word[0].isupper() and word.lower() not in common_words:
                keywords.append(word)
        
        # 2. Tìm mã sinh viên (chuỗi số 7-10 ký tự)
        student_ids = re.findall(r'\b(\d{7,10})\b', query)
        keywords.extend(student_ids)
        
        # 3. Tìm các cụm từ đặc biệt trong ngoặc kép
        quoted = re.findall(r'["\'](.+?)["\']', query)
        keywords.extend(quoted)
        
        # Deduplicate giữ thứ tự
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw.lower() not in seen and len(kw) >= 2:
                seen.add(kw.lower())
                unique_keywords.append(kw)
        
        return unique_keywords

    async def _generate_conversational_response(self, query: str, history: List[str]) -> str:
        """
        Tạo phản hồi cho các câu hỏi hội thoại không cần RAG.
        """
        prompt = f"""Bạn là Chat Bot AI của FBU (Trường Đại học Tài chính - Ngân hàng Hà Nội).
QUAN TRỌNG: Bạn KHÔNG PHẢI là Qwen, GPT, hay bất kỳ AI nào khác. Bạn là Chat Bot AI của FBU.

NẾU ĐƯỢC HỎI "BẠN LÀ AI": Trả lời "Tôi là Chat Bot AI của FBU, sẵn sàng hỗ trợ bạn các thông tin về trường Đại học Tài chính - Ngân hàng Hà Nội."
NẾU ĐƯỢC HỎI "BẠN ĐƯỢC TẠO RA BỞI AI": Trả lời "Tôi được tạo ra bởi Nguyễn Văn Lợi, sinh viên năm 4 của trường Đại học Tài chính - Ngân hàng Hà Nội khóa 11."

Trả lời HOÀN TOÀN bằng tiếng Việt, ngắn gọn và thân thiện.

Câu hỏi: {query}
Trả lời:"""

        return await self.llm.generate_response(prompt)

    def _rerank_by_query_type(self, results: List, analysis: Dict) -> List:
        """Re-rank results dựa trên query type để ưu tiên chunks phù hợp"""
        scored_results = []
        
        for r in results:
            score = r.score if hasattr(r, 'score') and r.score else 0.5
            chunk_type = r.payload.get('chunk_type', '')
            
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
                content_lower = r.payload.get('content', '').lower()
                matches = sum(1 for col in column_mentions if col.lower() in content_lower)
                if matches > 0:
                    score += 0.15 * (matches / len(column_mentions))
            
            scored_results.append((r, score))
        
        # Sort by score descending
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored_results]

    def _build_optimized_context(self, valid_hits: List) -> str:
        """
        Build context grouped by source với priority order.
        Hiển thị metadata cấu trúc (title, doc_number, date, issuer) trong header.
        """
        # Group results by source and chunk_type
        grouped = defaultdict(lambda: defaultdict(list))
        
        for hit in valid_hits:
            source = hit.payload.get('source', 'Unknown')
            chunk_type = hit.payload.get('chunk_type', hit.payload.get('type', 'unknown'))
            grouped[source][chunk_type].append(hit)
        
        context_parts = []
        priority_order = ['overview', 'column_stats', 'grouped_rows', 'single_row',
                          'excel_summary', 'excel_group', 'excel_row', 'excel',
                          'text', 'table', 'unknown']
        
        for source, chunks_by_type in grouped.items():
            # Lấy metadata từ chunk đầu tiên
            first_hit = None
            for chunks in chunks_by_type.values():
                if chunks:
                    first_hit = chunks[0]
                    break
            
            # Build header với metadata cấu trúc
            header_parts = []
            if first_hit:
                title = first_hit.payload.get('title', '')
                doc_number = first_hit.payload.get('doc_number', '')
                date = first_hit.payload.get('date', '')
                issuer = first_hit.payload.get('issuer', '')
                doc_type = first_hit.payload.get('doc_type', '')
                
                if title:
                    header_parts.append(f"Văn bản: {title}")
                if doc_number:
                    header_parts.append(f"Số: {doc_number}")
                if date:
                    header_parts.append(f"Ngày: {date}")
                if issuer:
                    header_parts.append(f"Cơ quan: {issuer}")
                if doc_type and doc_type != 'khác':
                    header_parts.append(f"Loại: {doc_type}")
            
            if header_parts:
                header = f"[{' | '.join(header_parts)}]"
            else:
                header = f"[Nguồn: {source}]"
            
            # Tìm time_info từ bất kỳ chunk nào
            time_info = None
            for chunks in chunks_by_type.values():
                for chunk in chunks:
                    if chunk.payload.get('time_info'):
                        time_info = chunk.payload['time_info']
                        break
                if time_info:
                    break
            
            if time_info:
                header += f"\nTHỜI GIAN: {time_info}"
            
            context_parts.append(header)
            
            # Add chunks theo priority order
            for chunk_type in priority_order:
                if chunk_type not in chunks_by_type:
                    continue
                
                for chunk in chunks_by_type[chunk_type]:
                    content = chunk.payload.get('content', '')
                    if content:
                        context_parts.append(f"NỘI DUNG: {content}")
            
            # Add any chunk types not in priority_order
            for chunk_type, chunks in chunks_by_type.items():
                if chunk_type not in priority_order:
                    for chunk in chunks:
                        content = chunk.payload.get('content', '')
                        if content:
                            context_parts.append(f"NỘI DUNG: {content}")
        
        return "\n\n".join(context_parts)

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

