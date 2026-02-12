from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
import shutil
import os
import uuid
from datetime import datetime

from app.api import deps
from app.models.document import Document
from app.services.pdf_processor import PDFProcessor
from app.services.excel_processor import ExcelProcessor
from app.services.vector_store import VectorStore
from app.services.audit_service import AuditService
from app.models.user import User

router = APIRouter()
UPLOAD_DIR = "uploads"
vector_store = VectorStore()

@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    # 1. Lưu file
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ["pdf", "xlsx", "xls"]:
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.{file_ext}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. Tạo bản ghi DB
    db_doc = Document(
        filename=file.filename,
        effective_date=datetime.now(), # Placeholder tạm thời
        file_hash="pending"
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    
    # Ghi log kiểm toán
    AuditService.log(
        db=db,
        user_id=current_user.id,
        action="UPLOAD",
        entity_type="Document",
        entity_id=db_doc.id,
        details={"filename": file.filename}
    )
    
    # 3. Xử lý
    try:
        chunks = []
        if file_ext == "pdf":
            chunks = PDFProcessor().process(file_path)
        elif file_ext in ["xlsx", "xls"]:
            chunks = ExcelProcessor.process(file_path)
            
        # 4. Cập nhật Vector Store
        metadatas = [{"source_id": db_doc.id, "filename": file.filename, "text": chunk} for chunk in chunks]
        vector_store.upsert_vectors(
            texts=chunks,
            metadatas=metadatas
        )
        
        return {"filename": file.filename, "status": "processed", "chunks": len(chunks)}
        
    except Exception as e:
        db.delete(db_doc)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
def list_documents(db: Session = Depends(deps.get_db)):
    return db.query(Document).all()
