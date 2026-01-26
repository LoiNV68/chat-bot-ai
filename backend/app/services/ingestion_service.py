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

class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.vector_store = VectorStore()

    async def process_upload(self, file: UploadFile, metadata: DocUploadSchema, user_id: int):
        # 1. Version Control Check
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
            await self.db.commit() # Commit deactivation
            
        # 2. Create New Document Record
        new_doc = Document(
            filename=file.filename,
            version=new_version,
            is_active=True,
            effective_date=metadata.effective_date,
            expiry_date=metadata.expiry_date,
            parent_id=parent_id,
            access_scope=metadata.scope,
            target_id=metadata.target_id,
            uploaded_by=user_id
        )
        self.db.add(new_doc)
        await self.db.commit()
        await self.db.refresh(new_doc)
        
        # 3. Parse File Content
        content = await file.read()
        chunks = []
        if file.filename.endswith(".xlsx"):
            chunks = self._parse_excel(content, file.filename)
        elif file.filename.endswith(".pdf"):
            chunks = self._parse_pdf(file.file, file.filename) # pass file object for pdfplumber
            
        # 4. Enrich Metadata & Vector Store
        texts = [chunk["content"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        
        # Update metadata with DB info and INCLUDE CONTENT
        for i, meta in enumerate(metadatas):
            meta.update({
                "doc_id": new_doc.id,
                "version": new_version,
                "access_scope": metadata.scope.value,
                "target_id": metadata.target_id,
                "content": texts[i] # Critical for retrieval
            })
            
        ids = [str(uuid.uuid4()) for _ in range(len(texts))]
        
        await self.vector_store.upsert_vectors(texts, metadatas, ids)
        
        return {"status": "success", "doc_id": new_doc.id, "chunks_count": len(chunks)}

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
        
    def _parse_pdf(self, file_obj, filename: str) -> List[Dict]:
        import pdfplumber
        # Note: file_obj is an UploadFile's spool, which works with pdfplumber.open if it has a .name or we might need to wrap it.
        # But pdfplumber usually expects a path or file-like object. 
        # UploadFile.file is a SpooledTemporaryFile.
        
        chunks = []
        try:
            with pdfplumber.open(file_obj) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    text = page.extract_text() or ""
                    
                    # Store text
                    if text.strip():
                         # Simple chunking by paragraph or fixed size could go here. 
                         # For now, per page text.
                         chunks.append({
                             "content": text,
                             "metadata": {"source": filename, "page": page.page_number, "type": "text"}
                         })
                    
                    # Store tables
                    for table in tables:
                        table_str = str(table) # Simplify table to string for now
                        chunks.append({
                            "content": table_str,
                            "metadata": {"source": filename, "page": page.page_number, "type": "table"}
                        })
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            
        return chunks
