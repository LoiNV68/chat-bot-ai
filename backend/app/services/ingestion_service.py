"""
Ingestion Service - Pipeline xử lý tài liệu cho RAG tiếng Việt.

Pipeline:
1. Trích xuất text: PyMuPDF (PDF) / pytesseract OCR fallback (scan) / pandas (Excel)
2. Làm sạch: Unicode NFC, bỏ ký tự rác, chuẩn hóa khoảng trắng
3. Tách từ tiếng Việt: pyvi ViTokenizer ("sinh viên" → "sinh_viên")
4. Chunking: RecursiveCharacterTextSplitter (600 chars, 100 overlap)
5. Metadata extraction: số văn bản, ngày, cơ quan, loại văn bản
6. Embedding + Qdrant upsert
"""
from typing import List, Dict, Any
import subprocess
import tempfile
import pathlib
from app.services.vector_store import VectorStore
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.document import Document, AccessScope
from app.schemas.doc_schema import DocUploadSchema
import uuid
import datetime
import os


class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.vector_store = VectorStore()


    async def save_document(self, file: UploadFile, metadata: DocUploadSchema, user_id: int):
        # 1. Đọc Nội dung File Trước
        try:
            content = await file.read()
            if not content:
                raise ValueError("Empty file content")
        except Exception as e:
            return {"status": "error", "message": f"Failed to read file: {str(e)}"}

        # 2. Lưu file vào đĩa
        from datetime import datetime as dt
        
        base_dir = os.getcwd()
        upload_dir = os.path.join(base_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        timestamp = dt.now().strftime("%Y%m%d%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        try:
            with open(file_path, "wb") as f:
                f.write(content)
        except Exception as e:
             return {"status": "error", "message": f"Failed to save file: {str(e)}"}

        # 3. Kiểm tra Version Control & Giao dịch DB
        try:
            existing_doc_query = select(Document).where(
                Document.filename == file.filename,
                Document.is_active == True
            )
            result = await self.db.execute(existing_doc_query)
            existing_doc = result.scalars().first()
            
            new_version = 1
            parent_id = None
            
            if existing_doc:
                existing_doc.is_active = False
                new_version = existing_doc.version + 1
                parent_id = existing_doc.id
                
                # --- TASK 8: CHỐNG TRÙNG LẶP DỮ LIỆU ---
                # Xóa sạch Vector của phiên bản PDF cũ khỏi Qdrant để ngăn ngừa 
                # Embeddings bị nhân đôi trả về 2 kết quả y hệt nhau
                await self.vector_store.delete_document_vectors(existing_doc.id)
                
            # 4. Tạo Bản ghi Tài liệu Mới
            new_doc = Document(
                filename=file.filename,
                version=new_version,
                is_active=True,
                effective_date=metadata.effective_date,
                expiry_date=metadata.expiry_date,
                parent_id=parent_id,
                access_scope=metadata.scope,
                target_id=metadata.target_id,
                uploaded_by=user_id,
                file_path=file_path
            )
            self.db.add(new_doc)
            await self.db.commit()
            await self.db.refresh(new_doc)
            
            return {
                "status": "success", 
                "doc_id": new_doc.id, 
                "file_path": file_path,
                "filename": file.filename,
                "version": new_version,
                "scope": metadata.scope.value,
                "target_id": metadata.target_id,
                "message": "Upload successful. AI processing in background."
            }
            
        except Exception as e:
            await self.db.rollback()
            if os.path.exists(file_path):
                os.remove(file_path)
            return {"status": "error", "message": f"Database error: {str(e)}"}


    async def ingest_file_content(self, doc_id: int, file_path: str, filename: str, version: int, scope: str, target_id: str):
        """
        Pipeline xử lý tài liệu:
        1. Đọc file → trích xuất text
        2. Làm sạch text
        3. Tách từ tiếng Việt (ViTokenizer)
        4. Chunking (RecursiveCharacterTextSplitter)
        5. Metadata extraction
        6. Upsert vào Qdrant
        """
        print(f"[DEBUG] Starting ingestion for doc_id={doc_id}, file={filename}")
        
        # Đọc nội dung từ đĩa
        try:
            if not os.path.exists(file_path):
                 print(f"[DEBUG] File NOT FOUND at {file_path}")
                 return

            with open(file_path, "rb") as f:
                content = f.read()
            print(f"[DEBUG] Read {len(content)} bytes from {file_path}")
        except Exception as e:
            print(f"[DEBUG] Background ingestion failed to read file {file_path}: {e}")
            return

        try:
            import asyncio
            
            def extract_sync():
                from app.services.ingestion_master import process_single_file
                return process_single_file(file_path, filename)
                
            # Đẩy toàn bộ quá trình parse/OCR/chunking (đồng bộ) sang một thread khác 
            # để không làm nghẽn (block) event loop chính của FastAPI.
            docs = await asyncio.to_thread(extract_sync)
            
            if docs is None:
                return
            
            print(f"[DEBUG] process_single_file extracted {len(docs)} chunks.")
        except Exception as e:
             import traceback
             traceback.print_exc()
             print(f"[DEBUG] Parsing error for {filename}: {e}")
             return

        if not docs:
             print(f"[DEBUG] Warning: No text content found in {filename}")
             return

        # ── Bước 6: Upsert vào Qdrant ──
        texts = [doc.page_content for doc in docs]
        metadatas_list = [doc.metadata for doc in docs]
        
        # Meta dictionary từ chunks đã có title, doc_type v.v (do Ingestion_Master nhúng)
        # Chúng ta cần thêm các thông tin quản lý DB vào.
        for i, meta in enumerate(metadatas_list):
            meta.update({
                "doc_id": doc_id,
                "version": version,
                "access_scope": scope,
                "target_id": target_id,
                "content": texts[i],   # Dành cho Qdrant (full text matching backup)
                "is_active": True,
            })
            
        ids = [str(uuid.uuid4()) for _ in range(len(texts))]
        
        print(f"[DEBUG] Upserting {len(texts)} vectors to Qdrant...")
        try:
            await self.vector_store.upsert_vectors(texts, metadatas_list, ids)
            print(f"[DEBUG] Background ingestion COMPLETED for doc {doc_id}.")
            
            from app.db.session import AsyncSessionLocal
            
            if self.db is not None:
                async with self.db.begin():
                    await self.db.execute(
                        update(Document).where(Document.id == doc_id).values(is_processed=True)
                    )
            else:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        await session.execute(
                            update(Document).where(Document.id == doc_id).values(is_processed=True)
                        )
            print(f"[DEBUG] Document {doc_id} marked as processed.")
        except Exception as e:
            print(f"[DEBUG] Vector upsert failed: {e}")




# ════════════════════════════════════════════════════════════════
#  BACKGROUND TASK
# ════════════════════════════════════════════════════════════════

async def run_background_ingestion(doc_id: int, file_path: str, filename: str, version: int, scope: str, target_id: str):
    import asyncio
    
    print(f"[DEBUG] Background task started for {filename} (ID: {doc_id})")
    service = IngestionService(None)
    await service.ingest_file_content(doc_id, file_path, filename, version, scope, target_id)
