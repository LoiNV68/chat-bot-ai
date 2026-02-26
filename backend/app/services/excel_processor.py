import os
import pandas as pd
from langchain_core.documents import Document

# =====================================================================
# MODULE: XỬ LÝ EXCEL BATCHING TÌM KIẾM
# =====================================================================
def process_excel_file(excel_path: str, global_metadata: dict) -> list[Document]:
    print(f"📊 Đang xử lý file Excel: {os.path.basename(excel_path)}...")
    excel_docs = []
    
    # Số dòng sinh viên gom vào 1 chunk
    ROWS_PER_CHUNK = 20
    
    try:
        # Đọc tất cả các sheet trong file Excel
        xls = pd.ExcelFile(excel_path)
        
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            
            # 1. Tìm dòng Header của Bảng (dòng chứa 'STT' hoặc 'Mã sinh viên')
            header_idx = 0
            for i, row in df.iterrows():
                row_str = " ".join([str(x) for x in row.dropna()]).lower()
                if "stt" in row_str or "mã sinh viên" in row_str or "họ và tên" in row_str:
                    header_idx = i
                    break
                    
            # 2. Rút trích Bối cảnh chung (Global Context) từ các dòng bên trên Header
            context_lines = []
            for i in range(header_idx):
                # Lấy các ô có dữ liệu, ghép lại thành câu
                row_data = [str(x).strip() for x in df.iloc[i] if pd.notna(x) and str(x).strip()]
                if row_data:
                    context_lines.append(" - " + " | ".join(row_data))
            
            sheet_context_text = "\n".join(context_lines)
            if sheet_context_text:
                sheet_context_text = f"**THÔNG TIN CHUNG:**\n{sheet_context_text}\n\n**DANH SÁCH CHI TIẾT:**\n"
            else:
                sheet_context_text = "**DANH SÁCH CHI TIẾT:**\n"
                
            # 3. Lấy dòng Header chuẩn
            headers = [str(x).replace('\n', ' ').strip() if pd.notna(x) else f"Column_{j}" for j, x in enumerate(df.iloc[header_idx])]
            
            # Xử lý trường hợp có Sub-header (như file Điểm rèn luyện)
            if header_idx + 1 < len(df):
                next_row_str = " ".join([str(x) for x in df.iloc[header_idx+1].dropna()]).lower()
                if "điểm số" in next_row_str or "lớp xếp loại" in next_row_str:
                    sub_headers = [str(x).replace('\n', ' ').strip() if pd.notna(x) else "" for x in df.iloc[header_idx+1]]
                    # Ghép 2 dòng header lại
                    headers = [f"{h} {sh}".strip() for h, sh in zip(headers, sub_headers)]
                    data_start_idx = header_idx + 2
                else:
                    data_start_idx = header_idx + 1
            else:
                data_start_idx = header_idx + 1

            data_rows = df.iloc[data_start_idx:]
            
            # 4. Chia lô dữ liệu (Batching)
            for i in range(0, len(data_rows), ROWS_PER_CHUNK):
                chunk = data_rows.iloc[i:i+ROWS_PER_CHUNK]
                
                md_lines = []
                # Chèn Header bảng
                md_lines.append("| " + " | ".join(headers) + " |")
                md_lines.append("|" + "|".join(["---"] * len(headers)) + "|")
                
                student_ids = []
                for _, row in chunk.iterrows():
                    clean_row = []
                    for idx, cell in enumerate(row):
                        val = str(cell).replace('\n', ' ') if pd.notna(cell) else ""
                        # Làm tròn số thập phân (nếu đuôi là .0)
                        if val.endswith(".0"): val = val[:-2] 
                        clean_row.append(val)
                        
                        # Bắt mã Sinh viên (thường có 10 chữ số) để lưu Metadata
                        if len(val) == 10 and val.isdigit():
                            student_ids.append(val)
                            
                    md_lines.append("| " + " | ".join(clean_row) + " |")
                
                markdown_table = "\n".join(md_lines)
                
                # Gộp Context chung và Bảng vào 1 nội dung duy nhất
                final_content = sheet_context_text + markdown_table
                
                # 5. Lưu vào Document
                meta = global_metadata.copy()
                meta.update({
                    "source": os.path.basename(excel_path), 
                    "sheet_name": sheet_name,
                    "content_type": "excel_table",
                    "student_ids_in_chunk": student_ids
                })
                excel_docs.append(Document(page_content=final_content, metadata=meta))
                
    except Exception as e:
        print(f"❌ Lỗi khi đọc file Excel: {e}")
        
    print(f"✅ Đã chia file Excel thành {len(excel_docs)} chunks chuẩn xác.")
    return excel_docs
