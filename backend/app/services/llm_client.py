from typing import List, Generator
from app.core.config import settings
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
            model="qwen2:7b",
            callback_manager=CallbackManager([StreamingStdOutCallbackHandler()])
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
        History: {history}
        Query: {query}
        Refined Query:
        """
        return self.generation_model.invoke(prompt)
