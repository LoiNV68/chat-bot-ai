from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate

from app.api import deps
from app.models.chat import ChatHistory
from app.services.vector_store import VectorStore
from app.core.config import settings
from app.core.limiter import limiter

router = APIRouter()
vector_store = VectorStore()
llm = Ollama(base_url=settings.OLLAMA_BASE_URL, model="qwen2.5:7b")

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[str]

@router.post("/", response_model=ChatResponse)
@limiter.limit("5/minute")
def chat(
    request: Request,
    chat_request: ChatRequest,
    db: Session = Depends(deps.get_db)
):
    # 1. Retrieve Context
    # Embed query is handled inside search (assumed, actually Qdrant search needs vector, 
    # but my VectorStore.search takes vector. I need to embed query here first)
    # Wait, my VectorStore.search takes query_vector. I need to embed.
    
    from langchain_community.embeddings import OllamaEmbeddings
    embeddings_model = OllamaEmbeddings(
        base_url=settings.OLLAMA_BASE_URL,
        model="nomic-embed-text"
    )
    query_vector = embeddings_model.embed_query(chat_request.query)
    
    search_results = vector_store.search(query_vector=query_vector, limit=3)
    
    context = "\n\n".join([res.payload.get("text", "") for res in search_results])
    sources = [res.payload.get("filename", "unknown") for res in search_results]
    
    # 2. Generate Answer
    prompt = ChatPromptTemplate.from_template("""
    Answer the question based only on the following context:
    {context}
    
    Question: {question}
    """)
    
    chain = prompt | llm
    answer = chain.invoke({"context": context, "question": chat_request.query})
    
    # 3. Save History
    # (Simplified: logic to save to DB)
    db_history = ChatHistory(
        user_query=chat_request.query,
        ai_response=answer
    )
    db.add(db_history)
    db.commit()
    
    return ChatResponse(response=answer, sources=list(set(sources)))

@router.put("/{session_id}/feedback")
def feedback(
    session_id: str,
    score: int,
    db: Session = Depends(deps.get_db)
):
    history = db.query(ChatHistory).filter(ChatHistory.session_id == session_id).first()
    if not history:
        raise HTTPException(status_code=404, detail="Session not found")
    
    history.feedback_score = score
    db.commit()
    return {"status": "success"}
