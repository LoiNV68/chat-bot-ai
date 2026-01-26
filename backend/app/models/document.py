import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from app.db.base_class import Base

class AccessScope(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    version = Column(Integer, default=1)
    
    # Versioning Control
    is_active = Column(Boolean, default=True)
    effective_date = Column(DateTime, nullable=True) # Start date of validity
    expiry_date = Column(DateTime, nullable=True)    # Expiry date
    parent_id = Column(Integer, ForeignKey("documents.id"), nullable=True) # Link to old version
    
    # Security
    access_scope = Column(Enum(AccessScope), default=AccessScope.PUBLIC)
    target_id = Column(String, nullable=True) # Student ID / Class ID if private
    
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
