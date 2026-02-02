from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.document import AccessScope

class DocUploadSchema(BaseModel):
    scope: AccessScope = AccessScope.PUBLIC
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    target_id: Optional[str] = None # Required if scope is PRIVATE

class DocumentResponse(BaseModel):
    id: int
    filename: str
    version: int
    is_active: bool
    is_processed: bool = False
    created_at: datetime
    access_scope: AccessScope
    
    class UserInfo(BaseModel):
        full_name: str
    
    uploader: Optional[UserInfo] = None
    
    class Config:
        from_attributes = True
