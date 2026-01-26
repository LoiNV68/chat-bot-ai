from typing import Any, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api import deps
from app.schemas.doc_schema import DocUploadSchema, DocumentResponse
from app.services.ingestion_service import IngestionService
from app.models.user import User
from app.models.document import AccessScope
from datetime import datetime

router = APIRouter()

@router.post("/upload")
async def upload_document(
    *,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    scope: AccessScope = Form(AccessScope.PUBLIC),
    effective_date: datetime = Form(None),
    expiry_date: datetime = Form(None),
    target_id: str = Form(None),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Upload a document (PDF/Excel)
    """
    ingestion_service = IngestionService(db)
    metadata = DocUploadSchema(
        scope=scope,
        effective_date=effective_date,
        expiry_date=expiry_date,
        target_id=target_id
    )
    
    result = await ingestion_service.process_upload(file, metadata, current_user.id)
    return result

@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve documents.
    """
    # Placeholder for logic to list docs
    # Should implement listing logic
    # checking permissions etc.
    from sqlalchemy import select
    from app.models.document import Document
    
    stmt = select(Document).offset(skip).limit(limit)
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return docs
