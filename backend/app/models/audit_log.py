from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from app.db.base_class import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, index=True, nullable=False) # CREATE, UPDATE, DELETE
    entity_type = Column(String, index=True, nullable=False) # Document, User, etc.
    entity_id = Column(String, nullable=True) # ID of the affected entity
    details = Column(Text, nullable=True) # JSON or text description
    
    timestamp = Column(DateTime, default=datetime.utcnow)
