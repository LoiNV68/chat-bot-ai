from typing import Any, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api import deps
from app.schemas.doc_schema import DocUploadSchema, DocumentResponse
from app.services.ingestion_service import IngestionService, run_background_ingestion
from app.models.user import User
from app.models.document import AccessScope, Document
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
    background_tasks: BackgroundTasks,
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
    
    # 1. Fast Save & DB Insert
    result = await ingestion_service.save_document(file, metadata, current_user.id)
    
    if result["status"] == "success":
        # 2. Schedule Slow Vector Ingestion in Background
        background_tasks.add_task(
            run_background_ingestion,
            doc_id=result["doc_id"],
            file_path=result["file_path"],
            filename=result["filename"],
            version=result["version"],
            scope=result["scope"],
            target_id=result["target_id"]
        )
    
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
    from sqlalchemy.orm import joinedload
    from app.models.document import Document
    
    stmt = select(Document).options(joinedload(Document.uploader)).where(Document.is_active == True).offset(skip).limit(limit)
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return docs

@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Soft delete a document.
    """
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    doc.is_active = False
    await db.commit()
    return {"message": "Document deleted"}

@router.post("/{doc_id}/restore")
async def restore_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Restore a soft-deleted document.
    """
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    doc.is_active = True
    await db.commit()
    return {"message": "Document restored"}

@router.get("/trash", response_model=List[DocumentResponse])
async def list_trash(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve deleted documents.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.models.document import Document
    
    stmt = select(Document).options(joinedload(Document.uploader)).where(Document.is_active == False).offset(skip).limit(limit)
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return docs

from fastapi.responses import FileResponse
import os

@router.get("/{doc_id}/content")
async def get_document_content(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Download/Preview document content.
    """
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Tệp không tồn tại trên máy chủ")
    
    return FileResponse(doc.file_path, filename=doc.filename, media_type="application/pdf" if doc.filename.endswith(".pdf") else None)
