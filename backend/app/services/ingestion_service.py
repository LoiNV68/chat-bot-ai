from typing import List, Dict, Any
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.document import Document, AccessScope
from app.services.vector_store import VectorStore
from app.schemas.doc_schema import DocUploadSchema
import pandas as pd
import pdfplumber
import uuid
import datetime
import datetime
import os

# Global cache for EasyOCR reader
ocr_reader = None

# Optimize PyTorch memory for shared GPU environments
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

def get_ocr_reader():
    global ocr_reader
    if ocr_reader is None:
        import easyocr
        import torch
        
        use_gpu = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if use_gpu else "CPU"
        print(f"[DEBUG] Initializing EasyOCR Reader (vi, en)... GPU Detected: {use_gpu} ({gpu_name})")
        
        ocr_reader = easyocr.Reader(['vi', 'en'], gpu=use_gpu)
    return ocr_reader

def perform_ocr_on_image(image_obj):
    """
    Helper function to run in a separate thread.
    Takes a PIL Image or bytes and returns text.
    """
    try:
        reader = get_ocr_reader()
        import numpy as np
        # Convert PIL Image to numpy array
        result = reader.readtext(np.array(image_obj), detail=0)
        return "\n".join(result)
    except Exception as e:
        print(f"[DEBUG] OCR Error on GPU: {e}")
        if "out of memory" in str(e).lower():
             print("[DEBUG] Falling back to CPU for OCR due to OOM...")
             torch.cuda.empty_cache()
             try:
                 import easyocr
                 # Initialize a fresh reader on CPU
                 cpu_reader = easyocr.Reader(['vi', 'en'], gpu=False)
                 result = cpu_reader.readtext(np.array(image_obj), detail=0)
                 return "\n".join(result)
             except Exception as cpu_e:
                 print(f"[DEBUG] OCR CPU Fallback Error: {cpu_e}")
        return ""

class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.vector_store = VectorStore()

    async def save_document(self, file: UploadFile, metadata: DocUploadSchema, user_id: int):
        # 1. Read File Content First
        try:
            content = await file.read()
            if not content:
                raise ValueError("Empty file content")
        except Exception as e:
            return {"status": "error", "message": f"Failed to read file: {str(e)}"}

        # 2. Save file to disk
        from datetime import datetime
        
        # Use absolute path relative to project root (assuming execution from project root)
        base_dir = os.getcwd()
        upload_dir = os.path.join(base_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Use timestamp to avoid name collision
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        try:
            with open(file_path, "wb") as f:
                f.write(content)
        except Exception as e:
             return {"status": "error", "message": f"Failed to save file: {str(e)}"}

        # 3. Version Control Check & DB Transaction
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
                # Only mark inactive here, commit later
                
            # 4. Create New Document Record
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
            await self.db.commit() # Commit DB transaction
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
            # Clean up file
            if os.path.exists(file_path):
                os.remove(file_path)
            return {"status": "error", "message": f"Database error: {str(e)}"}



    async def ingest_file_content(self, doc_id: int, file_path: str, filename: str, version: int, scope: str, target_id: str):
        print(f"[DEBUG] Starting ingestion for doc_id={doc_id}, file={filename}")
        # Read content from DISK
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

        # Parse Content
        chunks = []
        ext = filename.lower()
        try:
            if ext.endswith(".xlsx"):
                print("[DEBUG] Parsing Excel...")
                chunks = self._parse_excel(content, filename)
            elif ext.endswith(".pdf"):
                print("[DEBUG] Parsing PDF (checking for OCR)...")
                # Now await the async method
                chunks = await self._parse_pdf(content, filename)
            elif ext.endswith(".docx"):
                print("[DEBUG] Parsing DOCX...")
                chunks = self._parse_docx(content, filename)
            else:
                print(f"[DEBUG] Skipping Qdrant ingestion for unsupported file type: {filename}")
                return
            
            print(f"[DEBUG] Extracted {len(chunks)} chunks.")
        except Exception as e:
             # Capture full traceback for debugging
             import traceback
             traceback.print_exc()
             print(f"[DEBUG] Parsing error for {filename}: {e}")
             return

        if not chunks:
             print(f"[DEBUG] Warning: No text content found in {filename}")
             return

        texts = [chunk["content"] for chunk in chunks]
        metadatas_list = [chunk["metadata"] for chunk in chunks]
        
        # Update metadata without DB query if possible, or we assume data passed is correct
        for i, meta in enumerate(metadatas_list):
            meta.update({
                "doc_id": doc_id,
                "version": version,
                "access_scope": scope,
                "target_id": target_id,
                "content": texts[i] 
            })
            
        ids = [str(uuid.uuid4()) for _ in range(len(texts))]
        
        print(f"[DEBUG] Upserting {len(texts)} vectors to Qdrant...")
        try:
            await self.vector_store.upsert_vectors(texts, metadatas_list, ids)
            print(f"[DEBUG] Background ingestion COMPLETED for doc {doc_id}.")
        except Exception as e:
            print(f"[DEBUG] Vector upsert failed: {e}")

    def _parse_excel(self, content: bytes, filename: str) -> List[Dict]:
        import io
        df = pd.read_excel(io.BytesIO(content))
        chunks = []
        for _, row in df.iterrows():
            row_str = ", ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
            if row_str.strip():
                chunks.append({
                    "content": row_str,
                    "metadata": {"source": filename, "type": "excel"}
                })
        return chunks
        
    async def _parse_pdf(self, content: bytes, filename: str) -> List[Dict]:
        import pdfplumber
        import io
        import asyncio
        
        chunks = []
        try:
            # We must load bytes into IO. 
            # Note: pdfplumber.open is sync. If the file is huge, this itself might block slightly, 
            # but usually parsing is the bottleneck.
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    # 1. Try Standard Text Extraction
                    text = page.extract_text() or ""
                    
                    if text.strip():
                         chunks.append({
                             "content": text,
                             "metadata": {"source": filename, "page": page.page_number, "type": "text"}
                         })
                    
                    # 2. Extract Tables
                    tables = page.extract_tables()
                    for table in tables:
                        table_str = str(table) 
                        chunks.append({
                             "content": table_str,
                             "metadata": {"source": filename, "page": page.page_number, "type": "table"}
                         })
                    
                    # 3. Fallback: OCR Logic if text is empty/sparse
                    if len(text.strip()) < 50:
                        # Only try rendering and OCR if we really need it.
                        print(f"[DEBUG] Page {page.page_number} has low text. Attempting OCR...")
                        
                        try:
                             # Render page to image. This can be slow/heavy, so maybe offload?
                             # page.to_image() with resolution=300 is CPU intensive.
                             # Let's run this in thread too if possible, but page object pickling is tricky.
                             # We'll run to_image in main loop (it uses C extensions often, release GIL?)
                             # But let's try to trust it's fast enough or offload the WHOLE thing?
                             # For now, just offload the OCR part which is the heaviest.
                             
                             # We need to catch if dependencies are missing early
                             try:
                                 # resolution=200 is faster than 300 and usually enough
                                 # Using a context manager for to_image sometimes helps cleanup?
                                 p_im = page.to_image(resolution=200)
                                 original_image = p_im.original
                             except Exception as render_err:
                                 print(f"[DEBUG] Page rendering failed (missing valid backend?): {render_err}")
                                 continue
                             
                             # Run OCR in separate thread
                             ocr_text = await asyncio.to_thread(perform_ocr_on_image, original_image)
                             
                             if ocr_text.strip():
                                 print(f"[DEBUG] OCR Success on page {page.page_number}: extracted {len(ocr_text)} chars.")
                                 chunks.append({
                                     "content": ocr_text,
                                     "metadata": {"source": filename, "page": page.page_number, "type": "ocr_text"}
                                 })
                        except Exception as e:
                            print(f"[DEBUG] OCR process failed on page {page.page_number}: {e}")

        except Exception as e:
            print(f"[DEBUG] Error parsing PDF: {e}")
            import traceback
            traceback.print_exc()
            
        return chunks

    def _parse_docx(self, content: bytes, filename: str) -> List[Dict]:
        import io
        from docx import Document as DocxDocument
        
        chunks = []
        try:
            doc = DocxDocument(io.BytesIO(content))
            # Extract paragraphs
            for i, para in enumerate(doc.paragraphs):
                text = para.text.strip()
                if text:
                    chunks.append({
                        "content": text,
                        "metadata": {"source": filename, "type": "text", "paragraph": i}
                    })
            
            # Extract tables
            for i, table in enumerate(doc.tables):
                table_data = []
                for row in table.rows:
                    row_data = [cell.text for cell in row.cells]
                    table_data.append(" | ".join(row_data))
                
                table_str = "\n".join(table_data)
                if table_str.strip():
                     chunks.append({
                        "content": table_str,
                        "metadata": {"source": filename, "type": "table", "table_index": i}
                    })
                    
        except Exception as e:
            print(f"[DEBUG] Error parsing DOCX: {e}")
        
        return chunks

# Define standalone function for background task to manage its own session lifecycle
async def run_background_ingestion(doc_id: int, file_path: str, filename: str, version: int, scope: str, target_id: str):
    from app.db.session import AsyncSessionLocal
    import asyncio
    
    print(f"[DEBUG] Background task started for {filename} (ID: {doc_id})")
    # Create a new session for the background task
    async with AsyncSessionLocal() as db:
        service = IngestionService(db)
        await service.ingest_file_content(doc_id, file_path, filename, version, scope, target_id)
