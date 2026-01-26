from typing import List, Optional
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    history: List[str] = [] # List of previous Q&A strings if needed, or session_id logic

class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []

class FeedbackCreate(BaseModel):
    session_id: str
    score: int # 1 or 5
    rejected_response: Optional[str] = None
    chosen_response: Optional[str] = None
