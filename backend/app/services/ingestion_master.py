import os
import json
import gc
import tempfile
import pathlib
import uuid
import subprocess
import fitz # PyMuPDF
import pdfplumber
from pyvi import ViTokenizer
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Qdrant
import pandas as pd
import numpy as np

# =====================================================================
# MODULE IMPORTS
# =====================================================================
from app.services.excel_processor import process_excel_file
from app.services.pdf_processor import (
    extract_metadata_with_llamacpp,
    extract_tables_to_markdown,
    extract_tables_from_scan,
    run_hybrid_ocr_wsl
)

# =====================================================================
# LUỒNG CHÍNH ĐIỀU PHỐI (MAIN PIPELINE)
# =====================================================================
def process_single_file(pdf_file_path: bytes | str, filename: str = None) -> list[Document]:
    """
    Hàm xử lý cho một file PDF, trả về danh sách các chunks Document.
    Hỗ trợ byte nội dung (dùng cho luồng API) hoặc đường dẫn file thật.
    """
    is_temp_file = False
    
    if isinstance(pdf_file_path, bytes):
        if not filename:
             filename = "document.pdf"
        file_extension = os.path.splitext(filename)[1].lower()
        if not file_extension:
             file_extension = ".pdf"
        # Tạo temp file nếu truyền vào dạng byte (như từ FastAPI UploadFile)
        fd, temp_path = tempfile.mkstemp(suffix=file_extension)
        with os.fdopen(fd, 'wb') as f:
            f.write(pdf_file_path)
        pdf_file_path = temp_path
        is_temp_file = True
    else:
        if not filename:
            filename = os.path.basename(pdf_file_path)

    print(f"\n{'='*50}\nBẮT ĐẦU XỬ LÝ: {filename}\n{'='*50}")

    # ===== RẼ NHÁNH TÙY THEO ĐỊNH DẠNG FILE =====
    file_extension = os.path.splitext(filename)[1].lower()
    
    if file_extension in ['.xls', '.xlsx', '.csv']:
        # Khởi tạo Metadata cơ bản (vì Excel thường không có đoạn văn dài để LLM tự chẩn đoán)
        global_metadata = {
            "doc_type": "Danh_sách",
            "issuer": "TRƯỜNG ĐẠI HỌC TÀI CHÍNH - NGÂN HÀNG HÀ NỘI",
            "title": filename.replace(file_extension, "").replace("_", " ").replace("-", " ")
        }
        
        # Chạy module Excel
        excel_docs = process_excel_file(pdf_file_path, global_metadata)
        
        # Dọn dẹp temp_file nếu có và return luôn
        if is_temp_file and os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)
            
        return excel_docs
        
    # ===== NẾU LÀ PDF THÌ CHẠY XUỐNG DƯỚI =====
    try:
        # 1. Trích xuất text nháp trang 1 để lấy thông tin (sử dụng PyMuPDF cho nhẹ, hoặc Paddle nếu là bản scan)
        print("⚡ Quét nhanh trang 1 để lấy thông tin...")
        page_1_text = ""
        try:
            doc = fitz.open(pdf_file_path)
            if len(doc) > 0:
                page_1_text = doc[0].get_text("text").strip()
            doc.close()
        except:
            pass
            
        # Nếu PyMuPDF không thấy text (bản scan), làm mồi tạm bằng WSL OCR cho trang 1
        if not page_1_text or len(page_1_text) < 50:
            print("⚡ Bản scan, gọi OCR WSL để làm mồi LLM...")
            # Tạo 1 temp file chỉ chứa trang 1 để tối ưu OCR
            doc = fitz.open(pdf_file_path)
            if len(doc) > 0:
                temp_p1 = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                temp_p1.close()
                doc_p1 = fitz.open()
                doc_p1.insert_pdf(doc, from_page=0, to_page=0)
                doc_p1.save(temp_p1.name)
                doc_p1.close()
                doc.close()
                
                p1_docs = run_hybrid_ocr_wsl(temp_p1.name, {})
                if p1_docs:
                    page_1_text = p1_docs[0].page_content
                os.remove(temp_p1.name)
        
        # 2. Gọi LLM lấy Metadata chuẩn xác
        global_metadata = extract_metadata_with_llamacpp(page_1_text)
        print(f"🎯 Metadata đã chốt: {json.dumps(global_metadata, ensure_ascii=False, indent=2)}")
        
        # 3. Trích xuất Bảng biểu
        # Thử dùng pdfplumber trước (cho PDF điện tử)
        table_docs = extract_tables_to_markdown(pdf_file_path, global_metadata)
        
        # Nếu pdfplumber không tìm thấy bảng nào, hệ thống tự động gọi PP-Structure (cho PDF Scan)
        if len(table_docs) == 0:
            table_docs = extract_tables_from_scan(pdf_file_path, global_metadata)
        
        # 4. Trích xuất Chữ (OCR sâu bằng WSL)
        text_docs = run_hybrid_ocr_wsl(pdf_file_path, global_metadata)
        
        # 5. Làm sạch và Chunking (Chỉ cắt Text, không cắt Table Markdown)
        print("\n🧹 Tiền xử lý tiếng Việt và cắt đoạn...")
        processed_text_docs = []
        for doc_item in text_docs:
            clean_text = " ".join(doc_item.page_content.split())
            if not clean_text.strip(): continue
            try:
                segmented_text = ViTokenizer.tokenize(clean_text)
            except:
                segmented_text = clean_text # Fallback nếu pyvi lỗi
            processed_text_docs.append(Document(page_content=segmented_text, metadata=doc_item.metadata))
            
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=600, 
            chunk_overlap=150, 
            length_function=len,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        final_chunks = text_splitter.split_documents(processed_text_docs)
        
        # Gộp Chunk Text và Chunk Table lại
        all_final_docs = final_chunks + table_docs
        print(f"✂️ Tổng cộng: {len(final_chunks)} đoạn text, {len(table_docs)} bảng Markdown.")
        
        return all_final_docs
        
    finally:
        if is_temp_file and os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)

if __name__ == "__main__":
    import sys
    sys.path.append(os.getcwd())
    # Thử nghiệm độc lập
    upload_dir = os.path.join(os.getcwd(), "uploads")
    pdfs = [f for f in os.listdir(upload_dir) if f.endswith(".pdf")]
    
    if pdfs:
        target_file = os.path.join(upload_dir, pdfs[0])
        print(f"Thử nghiệm với file: {target_file}")
        
        chunks = process_single_file(target_file)
        
        print("\n--- SAMPLE CHUNKS ---")
        for i, c in enumerate(chunks[:3]):
            print(f"\nChunk {i+1}: Type = {c.metadata.get('content_type')} | Meta = {c.metadata.get('doc_number')}")
            print(c.page_content[:200] + "...")
    else:
        print("Không có tệp PDF nào trong /uploads để test.")
