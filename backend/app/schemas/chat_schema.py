from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

# --- Message Schemas ---
class ChatMessageBase(BaseModel):
    role: str
    content: str

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessage(ChatMessageBase):
    id: int
    session_id: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Session Schemas ---
class ChatSessionBase(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = False

class ChatSessionCreate(ChatSessionBase):
    pass

class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None

class ChatSession(ChatSessionBase):
    id: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    # messages: List[ChatMessage] = [] # Removed to prevent N+1/MissingGreenlet error in list view

    class Config:
        from_attributes = True

# --- API Interaction Schemas ---
class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None # If provided, continues session
    history: List[str] = [] # Legacy support or explicit context

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: List[str] = []

class FeedbackCreate(BaseModel):
    chat_message_id: int
    score: int # 1 or 5
    rejected_response: Optional[str] = None
    chosen_response: Optional[str] = None
