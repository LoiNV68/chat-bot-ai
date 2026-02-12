from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.api import deps
from app.models.chat import ChatHistory
from app.services.vector_store import VectorStore
from app.services.llm_client import LLMClient
from app.core.config import settings
from app.core.limiter import limiter

router = APIRouter()

# Sử dụng singleton instances thay vì tạo mới cho mỗi request
_vector_store = None
_llm_client = None

def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store

def get_llm_client():
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[str]

@router.post("/", response_model=ChatResponse)
@limiter.limit("5/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    db: Session = Depends(deps.get_db)
):
    # Sử dụng singleton instances
    vector_store = get_vector_store()
    llm_client = get_llm_client()
    
    # VectorStore.search xử lý embedding nội bộ rồi
    search_results = await vector_store.search(query=chat_request.query, limit=3)
    
    context = "\n\n".join([res.payload.get("content", res.payload.get("text", "")) for res in search_results])
    sources = [res.payload.get("source", res.payload.get("filename", "unknown")) for res in search_results]
    
    # 2. Tạo câu trả lời sử dụng LLMClient singleton
    prompt = f"""Answer the question based only on the following context:
{context}

Question: {chat_request.query}
"""
    
    answer = await llm_client.generate_response(prompt)
    
    # 3. Lưu lịch sử
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
