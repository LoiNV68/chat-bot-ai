from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class Document(Base):
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    effective_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    parent_id = Column(Integer, ForeignKey("document.id"), nullable=True)
    file_hash = Column(String, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("user.id"), nullable=True)
    
    uploader = relationship("User")
    parent = relationship("Document", remote_side=[id])
