from __future__ import annotations

import os
import tempfile
from typing import Iterable

import fitz
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.excel_processor import process_excel_file
from app.services.pdf_processor import (
    extract_metadata_with_llamacpp,
    extract_tables_from_scan,
    extract_tables_to_markdown,
    extract_text_pymupdf,
    run_hybrid_ocr,
)
from app.services.text_normalization import (
    clean_ocr_text,
    fold_text_for_search,
    normalize_metadata_strings,
)


TEXT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=850,
    chunk_overlap=120,
    length_function=len,
    separators=["\nĐiều ", "\nKhoản ", "\nMục ", "\n\n", "\n", ". ", " ", ""],
)


def _safe_log(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", "replace").decode("ascii"))


def _detect_pdf_profile(pdf_path: str) -> tuple[bool, str, int]:
    has_native_text = False
    first_page_text = ""
    total_pages = 0

    try:
        pdf = fitz.open(pdf_path)
        total_pages = len(pdf)
        if total_pages > 0:
            first_page_text = (pdf[0].get_text("text") or "").strip()
            has_native_text = len(first_page_text) >= 60
        pdf.close()
    except Exception:
        pass

    return has_native_text, first_page_text, max(total_pages, 1)


def _deduplicate_documents(docs: Iterable[Document]) -> list[Document]:
    deduped: list[Document] = []
    seen: set[str] = set()

    for doc in docs:
        content = doc.page_content or ""
        meta = doc.metadata or {}
        page = int(meta.get("page", 0) or 0)
        ctype = str(meta.get("content_type", "")).lower()
        key = f"{page}|{ctype}|{fold_text_for_search(content)}"
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(doc)

    return deduped


def _normalize_text_documents(text_docs: list[Document], table_pages: set[int]) -> list[Document]:
    normalized: list[Document] = []

    for doc in text_docs:
        page = int(doc.metadata.get("page", 0) or 0)
        drop_table_noise = page in table_pages
        cleaned = clean_ocr_text(doc.page_content, drop_table_like_lines=drop_table_noise)
        if len(cleaned) < 30:
            continue

        meta = normalize_metadata_strings(dict(doc.metadata))
        meta.setdefault("content_type", "text")
        meta.setdefault("chunk_type", "text")
        normalized.append(Document(page_content=cleaned, metadata=meta))

    return normalized


def _apply_global_metadata(text_docs: list[Document], global_metadata: dict) -> list[Document]:
    merged_docs: list[Document] = []

    for doc in text_docs:
        meta = dict(global_metadata)
        meta.update(normalize_metadata_strings(dict(doc.metadata)))
        merged_docs.append(Document(page_content=doc.page_content, metadata=meta))

    return merged_docs


def _attach_chunk_metadata(docs: list[Document], total_pages: int) -> list[Document]:
    docs.sort(
        key=lambda d: (
            int(d.metadata.get("page", 0) or 0),
            0 if d.metadata.get("chunk_type") == "text" else 1,
        )
    )

    for idx, doc in enumerate(docs, start=1):
        meta = normalize_metadata_strings(dict(doc.metadata))
        meta["chunk_order"] = idx
        meta["chunk_id"] = f"chunk_{idx}"
        meta["doc_total_pages"] = total_pages
        meta["ingest_version"] = 2
        doc.metadata = meta

    return docs


def process_single_file(pdf_file_path: bytes | str, filename: str | None = None) -> list[Document]:
    """Parse a single file (PDF/Excel) and return normalized chunk documents."""
    is_temp_file = False

    if isinstance(pdf_file_path, bytes):
        if not filename:
            filename = "document.pdf"
        ext = os.path.splitext(filename)[1].lower() or ".pdf"
        fd, temp_path = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, "wb") as handle:
            handle.write(pdf_file_path)
        pdf_file_path = temp_path
        is_temp_file = True
    else:
        if not filename:
            filename = os.path.basename(pdf_file_path)

    _safe_log(f"[ingest] start file={filename}")

    extension = os.path.splitext(filename)[1].lower()
    if extension in [".xls", ".xlsx", ".csv"]:
        base_meta = {
            "doc_type": "Danh_sách",
            "issuer": "TRƯỜNG ĐẠI HỌC TÀI CHÍNH - NGÂN HÀNG HÀ NỘI",
            "title": filename.replace(extension, "").replace("_", " ").replace("-", " "),
        }
        excel_docs = process_excel_file(pdf_file_path, base_meta)
        excel_docs = _attach_chunk_metadata(_deduplicate_documents(excel_docs), total_pages=1)
        if is_temp_file and os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)
        return excel_docs

    try:
        has_native_text, page_1_text, total_pages = _detect_pdf_profile(pdf_file_path)
        ocr_page_docs: list[Document] = []

        if not has_native_text:
            ocr_page_docs = run_hybrid_ocr(pdf_file_path, {})
            if ocr_page_docs:
                page_1_text = ocr_page_docs[0].page_content

        global_metadata = extract_metadata_with_llamacpp(page_1_text, filename)
        _safe_log(f"[ingest] metadata={global_metadata}")

        table_docs = extract_tables_to_markdown(pdf_file_path, global_metadata)
        if not table_docs:
            table_docs = extract_tables_from_scan(pdf_file_path, global_metadata)

        text_docs = (
            extract_text_pymupdf(pdf_file_path, global_metadata)
            if has_native_text
            else (_apply_global_metadata(ocr_page_docs, global_metadata) if ocr_page_docs else run_hybrid_ocr(pdf_file_path, global_metadata))
        )

        table_pages = {
            int(doc.metadata.get("page", 0) or 0)
            for doc in table_docs
            if doc.metadata.get("chunk_type") == "table"
        }
        normalized_text_docs = _normalize_text_documents(text_docs, table_pages)
        text_chunks = TEXT_SPLITTER.split_documents(normalized_text_docs)

        all_docs = _deduplicate_documents(text_chunks + table_docs)
        all_docs = _attach_chunk_metadata(all_docs, total_pages=total_pages)

        _safe_log(
            f"[ingest] done text_chunks={len(text_chunks)} table_chunks={len(table_docs)} total={len(all_docs)}"
        )
        return all_docs

    finally:
        if is_temp_file and os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)


if __name__ == "__main__":
    upload_dir = os.path.join(os.getcwd(), "uploads")
    pdfs = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]

    if pdfs:
        target = os.path.join(upload_dir, pdfs[0])
        chunks = process_single_file(target)
        _safe_log(f"[ingest] sample file={target}")
        for idx, chunk in enumerate(chunks[:3], start=1):
            _safe_log(
                f"chunk={idx} type={chunk.metadata.get('content_type')} page={chunk.metadata.get('page')}"
            )
            _safe_log(chunk.page_content[:200])
    else:
        _safe_log("[ingest] no pdf found in uploads")
