from typing import List, Generator
from app.core.config import settings
try:
    from langchain_ollama import OllamaLLM as Ollama
except ImportError:
    from langchain_community.llms import Ollama

from langchain_ollama import OllamaEmbeddings
from langchain_core.callbacks import CallbackManager, StreamingStdOutCallbackHandler
import torch

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
            model="qwen2.5:3b",
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
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return self.generation_model.invoke(prompt)

    async def rewrite_query(self, query: str, history: List[str]) -> str:
        prompt = f"""
        Given the following conversation history and a new user query, rephrase the query to be standalone and contextually complete.
        
        CRITICAL INSTRUCTION: The output MUST be in the same language as the user's query (usually Vietnamese). 
        Do NOT translate the query to English or Chinese or any other language.
        If the query is in Vietnamese, keeping it in Vietnamese is mandatory.
        
        History: {history}
        Query: {query}
        
        Rephrased Query (in Vietnamese):
        """
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return self.generation_model.invoke(prompt)
