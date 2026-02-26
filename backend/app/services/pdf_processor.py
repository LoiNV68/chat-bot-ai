import os
import json
import gc
import tempfile
import pathlib
import uuid
import subprocess
import fitz  # PyMuPDF
import pdfplumber
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# =====================================================================
# MODULE 1: GỌI LLAMA.CPP LẤY METADATA TỰ ĐỘNG
# =====================================================================
def extract_metadata_with_llamacpp(page_1_text: str) -> dict:
    print("🤖 Đang nhờ Qwen2.5-7B/Llama (Llama.cpp) phân tích Metadata...")
    
    if not page_1_text.strip():
        print("⚠️ Không có text để LLM phân tích, dùng metadata mặc định.")
        return {"doc_type": "Khác", "issuer": "Không xác định", "doc_number": "Không xác định", "date": "Không xác định", "title": "Không xác định"}

    llm = ChatOpenAI(
        base_url="http://localhost:8080/v1", 
        api_key="sk-no-key-required", 
        # model="qwen", # Có thể thay bằng tên model thực tế của bạn hoặc để mặc định
        model="MẶC-ĐỊNH-BỎ-QUA-NẾU-DÙNG-LOCAL-LLAMACPP",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}} 
    )
    
    system_prompt = """
    Bạn là một chuyên gia văn thư xuất sắc. Hãy đọc văn bản và trích xuất thông tin vào ĐÚNG định dạng JSON sau. Không giải thích thêm.
    {
        "doc_type": "Chỉ chọn 1: Thông_báo, Quyết_định, Công_văn, Danh_sách, Kế_hoạch, Khuyến_nghị, Tờ_trình, Báo_cáo, Hợp_đồng, Khác",
        "issuer": "Tên cơ quan ban hành (VD: Trường Đại học Tài chính - Ngân hàng Hà Nội, Bộ Giáo dục và Đào tạo)",
        "doc_number": "Số hiệu văn bản (VD: 144/TB-ĐHTNH. Nếu không có: 'Không xác định')",
        "date": "Ngày tháng ban hành theo định dạng YYYY-MM-DD (VD: 2026-01-19). Nếu không có: 'Không xác định'",
        "title": "Trích yếu/Tiêu đề chính của văn bản (Ngắn gọn, bỏ qua phần Căn cứ)"
    }
    """
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Văn bản:\n{page_1_text[:2000]}") # Giới hạn token để tránh Llama bị lỗi context
    ]
    
    try:
        response = llm.invoke(messages)
        return json.loads(response.content)
    except Exception as e:
        print(f"❌ Lỗi LLM: {e}")
        return {"doc_type": "Khác", "issuer": "Không xác định", "doc_number": "Không xác định", "date": "Không xác định", "title": "Không xác định"}

# =====================================================================
# MODULE 2: TRÍCH XUẤT BẢNG BIỂU THÀNH MARKDOWN
# =====================================================================
def extract_tables_to_markdown(pdf_path: str, global_metadata: dict) -> list[Document]:
    print("📊 Đang xử lý Danh sách dài (Smart Table Chunking)...")
    table_docs = []
    
    # Cấu hình: Gom bao nhiêu dòng (sinh viên) vào 1 chunk?
    # 20 dòng là con số đẹp để AI vừa đủ hiểu mà không bị quá tải token
    ROWS_PER_CHUNK = 20 
    
    saved_header = None # Lưu trữ tiêu đề để dùng cho các trang sau bị mất tiêu đề
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Cấu hình extract_tables để bắt bảng tốt nhất
            tables = page.extract_tables(table_settings={
                "vertical_strategy": "lines", 
                "horizontal_strategy": "lines",
                "snap_tolerance": 3,
            })
            
            # Nếu không bắt được bằng lines, thử text (cho các bảng không kẻ ô)
            if not tables:
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "text", 
                    "horizontal_strategy": "text"
                })

            for table in tables:
                if not table or len(table) < 2: continue
                
                # 1. Xử lý Header (Tiêu đề cột)
                current_rows = table
                
                # Logic thông minh: Kiểm tra xem dòng đầu tiên có phải là Header không?
                # Nếu dòng đầu chứa các từ khóa như "Mã SV", "Họ tên", "STT"... thì nó là Header
                first_row_str = " ".join([str(c) for c in current_rows[0] if c]).lower()
                is_header = "mã" in first_row_str or "stt" in first_row_str or "họ" in first_row_str
                
                if is_header:
                    saved_header = [str(cell).replace('\n', ' ') if cell else "" for cell in current_rows[0]]
                    data_rows = current_rows[1:] # Bỏ dòng header ra khỏi data
                else:
                    # Nếu trang này không có header, dùng lại header của trang trước (QUAN TRỌNG)
                    if saved_header:
                        data_rows = current_rows
                    else:
                        # Trường hợp xấu nhất: Không tìm thấy header nào cả
                        continue

                # 2. Chia nhỏ dữ liệu (Batching)
                # Thay vì lưu cả bảng to, ta cắt nhỏ ra từng cụm 20 sinh viên
                for i in range(0, len(data_rows), ROWS_PER_CHUNK):
                    chunk_rows = data_rows[i : i + ROWS_PER_CHUNK]
                    
                    md_lines = []
                    
                    # Luôn luôn chèn Header vào đầu mỗi chunk
                    if saved_header:
                        md_lines.append("| " + " | ".join(saved_header) + " |")
                        md_lines.append("|" + "|".join(["---" for _ in saved_header]) + "|")
                    
                    # Thêm dữ liệu sinh viên
                    for row in chunk_rows:
                        clean_row = [str(cell).replace('\n', ' ') if cell else "" for cell in row]
                        md_lines.append("| " + " | ".join(clean_row) + " |")
                    
                    md_text = "\n".join(md_lines)
                    
                    # 3. Tạo Metadata phong phú để tìm kiếm chính xác
                    # Trích xuất Mã SV từ trong bảng để đưa vào Metadata (Giúp search cực nhanh)
                    student_ids = []
                    for row in chunk_rows:
                        # Giả sử Mã SV thường nằm ở cột thứ 2 (index 1) - Tùy chỉnh theo thực tế
                        if len(row) > 1 and row[1] and str(row[1]).isdigit():
                            student_ids.append(str(row[1]))
                            
                    meta = global_metadata.copy()
                    meta.update({
                        "source": os.path.basename(pdf_path), 
                        "page": page_num + 1, 
                        "content_type": "student_list",
                        "student_ids_in_chunk": student_ids # Lưu danh sách Mã SV có trong chunk này
                    })
                    
                    table_docs.append(Document(page_content=md_text, metadata=meta))

            # Giải phóng RAM/VRAM sau mỗi trang để tránh tràn bộ nhớ khi file quá dài
            gc.collect()

    print(f"✅ Đã chia nhỏ danh sách thành {len(table_docs)} chunks (mỗi chunk {ROWS_PER_CHUNK} sinh viên).")
    return table_docs

# Chuyển hàm xử lý đường dẫn ra ngoài để tránh định nghĩa lại nhiều lần
def to_wsl_path(win_path):
    p = pathlib.Path(win_path).resolve()
    drive = p.drive.replace(":", "").lower()
    parts = list(p.parts[1:])
    return f"/mnt/{drive}/" + "/".join(parts)

def extract_tables_from_scan(pdf_path: str, global_metadata: dict) -> list[Document]:
    print("📊 Đang nhờ WSL (PP-Structure) quét bảng biểu từ ảnh scan...")
    
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    table_docs = []
    
    # Sinh một mã định danh ngẫu nhiên cho chuỗi xử lý này (Chống ghi đè file khi gọi API đồng thời)
    session_id = uuid.uuid4().hex
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        DPI = 200
        mat = fitz.Matrix(DPI / 72, DPI / 72)
        
        # Lấy thư mục gốc dạng WSL (Chỉ cần lấy 1 lần)
        wsl_cwd = to_wsl_path(os.getcwd())
        
        for page_num in range(total_pages):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            
            # 1. Lưu ảnh ra thư mục temp VỚI TÊN ĐỘC NHẤT
            temp_img_path = f"{temp_dir}/img_{session_id}_p{page_num}.jpg"
            temp_json_path = f"{temp_dir}/res_{session_id}_p{page_num}.json"
            
            pix.save(temp_img_path)
            
            # Chuyển đổi đường dẫn ảnh/json sang định dạng WSL để truyền vào lệnh
            wsl_img_path = f"{wsl_cwd}/{temp_img_path}"
            wsl_json_path = f"{wsl_cwd}/{temp_json_path}"
                
            # 2. Gọi lệnh WSL (loại bỏ nháy kép để CMD không bị lỗi quote lúc parse)
            wsl_command = f'wsl -d Ubuntu --cd {wsl_cwd} -e python3 app/services/ppstructure_service.py {wsl_img_path} {wsl_json_path}'
            
            result_data = None
            try:
                # Chạy lệnh
                res = subprocess.run(wsl_command, shell=True, capture_output=True)
                
                if res.returncode != 0:
                    raise subprocess.CalledProcessError(res.returncode, wsl_command, res.stdout, res.stderr)
                
                # 3. Đọc kết quả từ file JSON trung gian
                if os.path.exists(temp_json_path):
                    with open(temp_json_path, 'r', encoding='utf-8') as f:
                        result_data = json.load(f)
                        
                    if result_data.get("status") == "success":
                        tables = result_data.get("tables", [])
                        
                        print(f"✅ Trang {page_num+1}: Tìm thấy {len(tables)} bảng HTML.")
                            
                        # Khởi tạo splitter cho HTML tables để tránh lỗi vượt quá Context Length của API Embedding
                        html_splitter = RecursiveCharacterTextSplitter(
                            chunk_size=1000,
                            chunk_overlap=200,
                            length_function=len
                        )

                        for table_html in tables:
                            meta = global_metadata.copy()
                            meta.update({
                                "source": os.path.basename(pdf_path), 
                                "page": page_num + 1, 
                                "content_type": "table_html_scan"
                            })
                            
                            # Cắt nhỏ bảng HTML nếu nó quá lớn
                            html_chunks = html_splitter.split_text(table_html)
                            for chunk in html_chunks:
                                table_docs.append(Document(page_content=chunk, metadata=meta))
                    else:
                        print(f"⚠️ WSL báo lỗi ở trang {page_num + 1}: {result_data.get('message')}")
                        
            except subprocess.CalledProcessError as e:
                print(f"❌ Lỗi khi gọi WSL ở trang {page_num + 1} (Exit {e.returncode}).")
            except Exception as e:
                print(f"❌ Lỗi hệ thống khi gọi WSL: {e}")
                
            finally:
                # 4. Dọn dẹp rác ngay sau khi xử lý xong từng trang
                if os.path.exists(temp_img_path): os.remove(temp_img_path)
                if os.path.exists(temp_json_path): os.remove(temp_json_path)
            
            # Giải phóng RAM/VRAM sau mỗi trang để tránh tràn bộ nhớ
            gc.collect()
            
        doc.close()
    except Exception as e:
        print(f"❌ Lỗi xử lý PyMuPDF: {e}")
            
    print(f"✅ WSL đã trả về {len(table_docs)} bảng (HTML).")
    return table_docs

# =====================================================================
# MODULE 3: HYBRID OCR CHO PHẦN CHỮ (Gọi qua WSL)
# =====================================================================
def run_hybrid_ocr_wsl(pdf_path: str, global_metadata: dict) -> list[Document]:
    """
    Sử dụng kiến trúc lai (PaddleOCR + VietOCR) chạy qua WSL để đảm bảo ổn định.
    Đã điều chỉnh lại từ Code gốc để tích hợp liền mạch với Windows.
    """
    print("🚀 Đang quét OCR các trang văn bản (via WSL)...")
    text_docs = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        DPI = 200
        
        with tempfile.TemporaryDirectory() as temp_dir:
            image_paths_windows = []
            
            # 1. Chuyển PDF sang ảnh
            for page_num in range(total_pages):
                page = doc[page_num]
                mat = fitz.Matrix(DPI / 72, DPI / 72)
                pix = page.get_pixmap(matrix=mat)
                
                img_path = os.path.join(temp_dir, f"page_{page_num}.png")
                pix.save(img_path)
                image_paths_windows.append(img_path)
            
            doc.close()
            
            service_script_windows = os.path.join(os.getcwd(), "app", "services", "hybrid_ocr_service.py")
            service_script_wsl = to_wsl_path(service_script_windows)
            image_paths_wsl = [to_wsl_path(p) for p in image_paths_windows]
            
            # 3. Gọi WSL Subprocess
            cmd = ["wsl", "-d", "Ubuntu", "--", "python3", service_script_wsl] + image_paths_wsl
            
            process = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if process.returncode != 0:
                print(f"[ERROR] WSL OCR process failed: {process.stderr}")
                return []
            
            # 4. Parse JSON kết quả và bọc vào Document object
            output_str = process.stdout
            json_start = output_str.find("[")
            if json_start != -1:
                results = json.loads(output_str[json_start:])
                for idx, page_res in enumerate(results):
                    if "text" in page_res:
                        page_text = page_res["text"]
                        
                        # Lọc rác OCR cực ngắn trước khi lưu
                        clean_lines = []
                        import re
                        for line in page_text.split('\n'):
                            line_str = line.strip()
                            if not line_str: continue
                            if len(line_str) <= 3 and not re.search(r'[a-zA-ZáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĐ]', line_str):
                                continue
                            clean_lines.append(line_str.replace("_", " ")) # Bỏ gạch dưới lỗi
                        
                        clean_page_text = '\n'.join(clean_lines)
                        
                        meta = global_metadata.copy()
                        meta.update({"source": os.path.basename(pdf_path), "page": idx + 1, "content_type": "text"})
                        text_docs.append(Document(page_content=clean_page_text, metadata=meta))
            else:
                print(f"[ERROR] No JSON array found in output")
                
    except Exception as e:
        print(f"[ERROR] Hybrid OCR WSL failed: {e}")
        
    return text_docs
