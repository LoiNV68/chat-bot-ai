from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.schemas.doc_schema import DocUploadSchema
from app.services.text_normalization import fold_text_for_search, normalize_metadata_strings
from app.services.vector_store import VectorStore


class IngestionService:
    def __init__(self, db: AsyncSession | None):
        self.db = db
        self.vector_store = VectorStore()

    async def save_document(self, file: UploadFile, metadata: DocUploadSchema, user_id: int):
        try:
            content = await file.read()
            if not content:
                raise ValueError("Empty file content")
        except Exception as exc:
            return {"status": "error", "message": f"Failed to read file: {exc}"}

        from datetime import datetime as dt

        upload_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = dt.now().strftime("%Y%m%d%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_filename)

        try:
            with open(file_path, "wb") as handle:
                handle.write(content)
        except Exception as exc:
            return {"status": "error", "message": f"Failed to save file: {exc}"}

        try:
            existing_query = select(Document).where(Document.filename == file.filename, Document.is_active.is_(True))
            existing_result = await self.db.execute(existing_query)
            existing_doc = existing_result.scalars().first()

            new_version = 1
            parent_id = None
            if existing_doc:
                existing_doc.is_active = False
                new_version = existing_doc.version + 1
                parent_id = existing_doc.id
                await self.vector_store.delete_document_vectors(existing_doc.id)

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
                file_path=file_path,
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
                "message": "Upload successful. AI processing in background.",
            }
        except Exception as exc:
            await self.db.rollback()
            if os.path.exists(file_path):
                os.remove(file_path)
            return {"status": "error", "message": f"Database error: {exc}"}

    def _build_vector_payload(
        self,
        doc_id: int,
        version: int,
        scope: str,
        target_id: str | None,
        text: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        payload = normalize_metadata_strings(dict(metadata or {}))
        payload.update(
            {
                "doc_id": doc_id,
                "version": version,
                "access_scope": scope,
                "target_id": target_id,
                "content": text,
                "content_folded": fold_text_for_search(text),
                "is_active": True,
            }
        )
        return payload

    def _build_stable_point_id(self, doc_id: int, version: int, chunk_id: str, text: str) -> str:
        seed = f"{doc_id}:{version}:{chunk_id}:{fold_text_for_search(text)[:160]}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

    async def ingest_file_content(
        self,
        doc_id: int,
        file_path: str,
        filename: str,
        version: int,
        scope: str,
        target_id: str | None,
    ):
        print(f"[ingest] start doc_id={doc_id} file={filename}")

        if not os.path.exists(file_path):
            print(f"[ingest] file missing: {file_path}")
            return

        try:
            import asyncio

            def extract_sync():
                from app.services.ingestion_master import process_single_file

                return process_single_file(file_path, filename)

            docs = await asyncio.to_thread(extract_sync)
            if docs is None:
                return
            print(f"[ingest] extracted_chunks={len(docs)}")
        except Exception as exc:
            import traceback

            traceback.print_exc()
            print(f"[ingest] parse failed: {exc}")
            return

        if not docs:
            print(f"[ingest] no chunks extracted for {filename}")
            return

        texts = [doc.page_content for doc in docs]
        metadatas = [
            self._build_vector_payload(doc_id, version, scope, target_id, text, docs[idx].metadata)
            for idx, text in enumerate(texts)
        ]

        ids: list[str] = []
        for idx, (meta, text) in enumerate(zip(metadatas, texts)):
            chunk_id = str(meta.get("chunk_id") or f"chunk_{idx + 1}")
            ids.append(self._build_stable_point_id(doc_id, version, chunk_id, text))

        print(f"[ingest] upserting_vectors={len(texts)}")
        try:
            await self.vector_store.upsert_vectors(texts, metadatas, ids)
            print(f"[ingest] qdrant upsert done doc_id={doc_id}")

            from app.db.session import AsyncSessionLocal

            if self.db is not None:
                async with self.db.begin():
                    await self.db.execute(update(Document).where(Document.id == doc_id).values(is_processed=True))
            else:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        await session.execute(
                            update(Document).where(Document.id == doc_id).values(is_processed=True)
                        )
            print(f"[ingest] marked processed doc_id={doc_id}")
        except Exception as exc:
            print(f"[ingest] vector upsert failed: {exc}")


async def run_background_ingestion(
    doc_id: int,
    file_path: str,
    filename: str,
    version: int,
    scope: str,
    target_id: str | None,
):
    print(f"[ingest] background task start doc_id={doc_id}")
    service = IngestionService(None)
    await service.ingest_file_content(doc_id, file_path, filename, version, scope, target_id)
