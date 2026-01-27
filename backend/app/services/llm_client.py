from typing import List, Generator
from app.core.config import settings
try:
    from langchain_ollama import OllamaLLM as Ollama
    from langchain_ollama import OllamaEmbeddings
except ImportError:
    from langchain_community.llms import Ollama
    from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.callbacks import CallbackManager, StreamingStdOutCallbackHandler

class LLMClient:
    def __init__(self):
        self.embedding_model = OllamaEmbeddings(
            base_url=settings.OLLAMA_BASE_URL,
            model="nomic-embed-text"
        )
        self.generation_model = Ollama(
            base_url=settings.OLLAMA_BASE_URL,
            model="qwen2.5:3b",
            callbacks=[StreamingStdOutCallbackHandler()]
        )

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self.embedding_model.embed_documents(texts)
    
    async def generate_response(self, prompt: str):
        # Langchain Ollama implementation might be sync or support sync.
        # For stream, we might need to use proper async calls or use the stream method.
        # This is a simplified wrapper.
        return self.generation_model.invoke(prompt)

    async def rewrite_query(self, query: str, history: List[str]) -> str:
        prompt = f"""
        Given the following conversation history and a new user query, rephrase the query to be standalone and contextually complete.
        IMPORTANT: Preserve the original language of the query (likely Vietnamese). Do not translate it to English unless the user asks to.
        
        History: {history}
        Query: {query}
        Câu hỏi:
        """
        return self.generation_model.invoke(prompt)
