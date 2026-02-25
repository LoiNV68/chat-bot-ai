from typing import List, Generator
import re
import asyncio
from collections import OrderedDict
from app.core.config import settings

# Use OpenAI compatible client for llama.cpp server
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

class LRUCache:
    """LRU Cache đơn giản với giới hạn kích thước tối đa."""
    def __init__(self, max_size: int = 1000):
        self._cache = OrderedDict()
        self._max_size = max_size
    
    def get(self, key: str):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None
    
    def set(self, key: str, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
        self._cache[key] = value


class LLMClient:
    """Singleton LLM Client - khởi tạo một lần và tái sử dụng cho mọi request."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        # Bỏ qua nếu đã khởi tạo (Singleton)
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # Sử dụng OpenAIEmbeddings - có thể chạy trên server riêng (Windows)
        # Tách riêng khỏi LLM server (WSL) bằng EMBEDDING_BASE_URL
        self.embedding_model = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_base=settings.EMBEDDING_BASE_URL,
            openai_api_key="dummy", # llama.cpp doesn't require a real key
            check_embedding_ctx_length=False # Avoid checks that might fail with local servers
        )
        
        # Chat Generation dùng ChatOpenAI kết nối tới llama.cpp server
        self.generation_model = ChatOpenAI(
            model=settings.LLM_MODEL,
            openai_api_base=settings.OLLAMA_BASE_URL,
            openai_api_key="dummy",
            temperature=0.7,
            max_tokens=None, # Let server decide or infinite
            timeout=1800 # 30 minutes timeout
        )
        
        # LRU Cache cho embeddings (tối đa 1000 entries) cho các truy vấn thường dùng
        self._embedding_cache = LRUCache(max_size=1000)
        
        # Pre-compile các regex patterns để matching nhanh hơn
        self._non_vietnamese_pattern = re.compile(
            r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af\u0400-\u04ff\u3000-\u303f\uff00-\uffef]+'
        )
        self._prefix_pattern = re.compile(
            r'^(markdown\s*[-:]\s*|Trả lời\s*:\s*|Answer\s*:\s*)', re.IGNORECASE
        )
        self._cyrillic_cjk_pattern = re.compile(r'[а-яА-Яа-яёЁ\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')
        
        self._initialized = True

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Lấy embeddings với LRU caching và Batch processing an toàn."""
        results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []
        
        # Kiểm tra cache trước
        for i, text in enumerate(texts):
            cached = self._embedding_cache.get(text)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)
        
        # Chỉ tính embeddings cho các texts chưa được cache, CHIA BATCH NHỎ tránh quá tải
        if uncached_texts:
            BATCH_SIZE = 3  # Giảm xuống 1 để an toàn tối đa (tránh timeout/OOM)
            for i in range(0, len(uncached_texts), BATCH_SIZE):
                batch_texts = uncached_texts[i : i + BATCH_SIZE]
                
                # Retry logic simple
                attempts = 0
                max_attempts = 3
                success = False
                while attempts < max_attempts:
                    try:
                        batch_embeddings = self.embedding_model.embed_documents(batch_texts)
                        
                        # Map lại vào kết quả và cache
                        for j, emb in enumerate(batch_embeddings):
                            global_idx = uncached_indices[i + j]
                            original_text = uncached_texts[i + j]
                            
                            self._embedding_cache.set(original_text, emb)
                            results[global_idx] = emb
                        success = True
                        break # Success
                    except Exception as e:
                        attempts += 1
                        import time
                        print(f"[WARN] Embedding batch failed (attempt {attempts}/{max_attempts}): {e}")
                        time.sleep(1.5 * attempts) # Exponential backoff
                
                if not success:
                    print(f"[ERROR] Embedding failed for batch after {max_attempts} attempts.")
                    # Fill 0 size 768 to avoid crash loop
                    zero_vec = [0.0] * 768
                    for j in range(len(batch_texts)):
                        if (i+j) < len(uncached_indices):
                            results[uncached_indices[i+j]] = zero_vec
        
        return results
    
    async def get_embeddings_async(self, texts: List[str]) -> List[List[float]]:
        """Async wrapper cho embeddings - không block event loop."""
        return await asyncio.to_thread(self.get_embeddings, texts)
    
    async def generate_response(self, prompt: str):
        """Tạo phản hồi với pre-compiled regex cleaning."""
        try:
             # ChatOpenAI invoke returns an AIMessage, we need .content
            response_msg = await asyncio.to_thread(self.generation_model.invoke, prompt)
            response = response_msg.content
        except Exception as e:
            print(f"Error generating response: {e}")
            return "Xin lỗi, tôi đang gặp sự cố kết nối với AI Server."

        
        # Strip whitespace trước khi clean
        cleaned = response.strip()
        
        # Sử dụng pre-compiled patterns để matching regex nhanh hơn
        cleaned = self._non_vietnamese_pattern.sub('', cleaned)
        cleaned = self._prefix_pattern.sub('', cleaned)
        
        # Xóa "markdown" ở đầu (có hoặc không dấu phân cách)
        cleaned = re.sub(r'^(?:markdown|Markdown|MARKDOWN)\s*[-:—]?\s*', '', cleaned.strip(), flags=re.IGNORECASE)
        
        # Dọn dẹp nhiều khoảng trắng và dấu phẩy
        cleaned = re.sub(r'\s*,\s*,\s*', ', ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip() if cleaned.strip() else response

    async def rewrite_query(self, query: str, history: List[str]) -> str:
        query_lower = query.lower().strip()
        
        # Bỏ qua viết lại cho các lời chào đơn giản (khớp chính xác hoặc rất ngắn)
        greeting_patterns = ['xin chào', 'chào bạn', 'chào', 'hello', 'hi', 'bạn là ai', 'cảm ơn', 'thanks', 'hey']
        
        # Nếu là lời chào đơn giản (khớp chính xác hoặc rất ngắn), bỏ qua viết lại
        if query_lower in greeting_patterns or len(query_lower) <= 5:
            return query

        # Với các câu hỏi tiếp theo có lịch sử, kiểm tra xem có phụ thuộc ngữ cảnh không và viết lại
        followup_patterns = ['chi tiết', 'thêm', 'rõ hơn', 'ví dụ', 'cụ thể', 'giải thích', 'còn gì', 'nữa không']
        is_context_dependent = any(p in query_lower for p in followup_patterns)
        
        # Nếu không có lịch sử và không phụ thuộc ngữ cảnh, trả về nguyên gốc
        if not history and not is_context_dependent:
            return query

            
        prompt = f"""Bạn là một trợ lý viết lại câu hỏi cho hệ thống đại học (KHÔNG phải trường phổ thông).

NHIỆM VỤ: Kết hợp câu hỏi hiện tại với ngữ cảnh từ lịch sử hội thoại để tạo thành câu hỏi hoàn chỉnh, độc lập.

NGỮ CẢNH: Đây là hệ thống đại học, dùng từ "sinh viên" (KHÔNG dùng "học sinh").

VÍ DỤ:
- Lịch sử: "Quy trình nộp hồ sơ miễn giảm học phí" -> AI trả lời
- Câu hỏi: "chi tiết hơn"
- Kết quả: "Cho tôi biết chi tiết hơn về quy trình nộp hồ sơ miễn giảm học phí"

QUY TẮC BẮT BUỘC:
1. CHỈ xuất ra câu hỏi đã viết lại, KHÔNG thêm giải thích.
2. PHẢI viết 100% bằng tiếng Việt thuần túy.
3. KHÔNG thêm ký tự Nga, Trung, Hàn, Nhật.
4. Nếu không có ngữ cảnh liên quan, trả về câu hỏi gốc.
5. Giữ nguyên tên riêng (tên người, mã sinh viên) không thay đổi.

Lịch sử hội thoại (10 tin nhắn gần nhất):
{history[-10:] if history else 'Không có'}

Câu hỏi hiện tại: {query}

Câu hỏi hoàn chỉnh:"""
        # Sử dụng async invoke để không block event loop
        try:
            result_msg = await asyncio.to_thread(self.generation_model.invoke, prompt)
            result = result_msg.content
        except Exception as e:
            print(f"Error rewriting query: {e}")
            return query

        # Sử dụng pre-compiled pattern
        cleaned = self._cyrillic_cjk_pattern.sub('', result)
        return cleaned.strip() if cleaned.strip() else query
