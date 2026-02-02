from typing import List, Generator
from app.core.config import settings
try:
    from langchain_ollama import OllamaLLM as Ollama
except ImportError:
    from langchain_community.llms import Ollama

from langchain_ollama import OllamaEmbeddings
from langchain_core.callbacks import CallbackManager, StreamingStdOutCallbackHandler
# import torch

class LLMClient:
    def __init__(self):
        # Using Ollama for Embeddings (External Service)
        self.embedding_model = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url=settings.OLLAMA_BASE_URL
        )
        
        # Chat Generation still uses Ollama
        self.generation_model = Ollama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.LLM_MODEL,
            callbacks=[StreamingStdOutCallbackHandler()],
            # CRITICAL for 6GB GPU: Aggressively unload model after use to prevent OOM
            keep_alive="1m" 
        )

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self.embedding_model.embed_documents(texts)
    
    async def generate_response(self, prompt: str):
        # Langchain Ollama implementation might be sync or support sync.
        # For stream, we might need to use proper async calls or use the stream method.
        # This is a simplified wrapper.
        # if torch.cuda.is_available():
        #     torch.cuda.empty_cache()
        return self.generation_model.invoke(prompt)

    async def rewrite_query(self, query: str, history: List[str]) -> str:
        query_lower = query.lower().strip()
        
        # Skip rewriting for simple greetings (exact match or very short)
        greeting_patterns = ['xin chào', 'chào bạn', 'chào', 'hello', 'hi', 'bạn là ai', 'cảm ơn', 'thanks', 'hey']
        
        # If it's a simple greeting (exact match or very short), skip rewriting
        if query_lower in greeting_patterns or len(query_lower) <= 5:
            return query

        # For follow-up queries with history, check if context-dependent and rewrite
        followup_patterns = ['chi tiết', 'thêm', 'rõ hơn', 'ví dụ', 'cụ thể', 'giải thích', 'còn gì', 'nữa không']
        is_context_dependent = any(p in query_lower for p in followup_patterns)
        
        # If no history and not context-dependent, return as-is
        if not history and not is_context_dependent:
            return query

            
        prompt = f"""Bạn là một trợ lý viết lại câu hỏi.

NHIỆM VỤ: Kết hợp câu hỏi hiện tại với ngữ cảnh từ lịch sử hội thoại để tạo thành câu hỏi hoàn chỉnh, độc lập.

VÍ DỤ:
- Lịch sử: "Quy trình nộp hồ sơ học phí" -> AI trả lời
- Câu hỏi: "chi tiết hơn"
- Kết quả: "Cho tôi biết chi tiết hơn về quy trình nộp hồ sơ miễn giảm học phí"

QUY TẮC BẮT BUỘC:
1. CHỈ xuất ra câu hỏi đã viết lại, KHÔNG thêm giải thích.
2. PHẢI viết 100% bằng tiếng Việt thuần túy.
3. KHÔNG thêm ký tự Nga, Trung, Hàn, Nhật.
4. Nếu không có ngữ cảnh liên quan, trả về câu hỏi gốc.

Lịch sử hội thoại (10 tin nhắn gần nhất):
{history[-10:] if history else 'Không có'}

Câu hỏi hiện tại: {query}

Câu hỏi hoàn chỉnh:"""
        result = self.generation_model.invoke(prompt)
        # Clean any non-Vietnamese characters that might slip through
        import re
        cleaned = re.sub(r'[а-яА-Яа-яёЁ\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', '', result)
        return cleaned.strip() if cleaned.strip() else query


