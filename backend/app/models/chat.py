from sqlalchemy import Column, Integer, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.db.base_class import Base

class ChatHistory(Base):
    __tablename__ = "chat_history"
    
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_query = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    feedback_score = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
