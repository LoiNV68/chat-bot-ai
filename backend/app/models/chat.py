from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from app.db.base_class import Base

class ChatHistory(Base):
    __tablename__ = "chat_history"

    session_id = Column(String, primary_key=True) # UUID
    user_id = Column(Integer, ForeignKey("users.id"))
    user_query = Column(String, nullable=False)
    ai_response = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FeedbackLoop(Base):
    __tablename__ = "feedback_loop"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey("chat_history.session_id"))
    score = Column(Integer) # 1 or 5
    
    # Data for DPO Training
    rejected_response = Column(String, nullable=True) # The wrong AI response
    chosen_response = Column(String, nullable=True)   # The corrected response by admin/expert
    
    status = Column(String, default="pending") # pending, reviewed, trained
    created_at = Column(DateTime, default=datetime.utcnow)
