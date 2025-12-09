# UNIMIND CORE 2.0 – SYSTEM ARCHITECTURE DOCUMENT

| Metadata | Details |
| :--- | :--- |
| **Author** | Chief Scientist |
| **Version** | 2.0.0 (Final Architecture) |
| **Architecture** | Private Local RAG + Offline DPO Loop |
| **Deployment** | On-Premise (Offline/Localhost) |
| **Core AI** | Qwen 2.5 (7B) + LoRA Adapters |

---

## 1. TỔNG QUAN (OVERVIEW)

### 1.1. Mục tiêu
Hệ thống chatbot đại học thông minh, chạy cục bộ, có khả năng tự cải thiện qua phản hồi của giảng viên.
* **Time-Aware:** Trả lời đúng theo thời điểm hiệu lực của văn bản.
* **Security:** Phân quyền dữ liệu (Public/Private).
* **Continuous Learning:** Tự học từ Feedback (Like/Dislike) qua quy trình DPO Offline.

### 1.2. Tech Stack
* **AI Engine:** Ollama (Qwen 2.5 7B) + LoRA Adapters.
* **Backend:** FastAPI, LangChain, Python (PDFPlumber, OpenPyXL).
* **Frontend:** React (Vite) + TailwindCSS + Shadcn/UI.
* **Database:** PostgreSQL 16 (Metadata) + Qdrant (Vector).
* **Infrastructure:** Docker Compose.

---

## 2. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)

Biểu đồ dưới đây tách biệt rõ ràng giữa **Luồng Chạy Thật (Online)** và **Luồng Huấn Luyện (Offline)** để đảm bảo an toàn hệ thống.

```mermaid
graph TD
    subgraph "Online Layer (Serving Users)"
        User[Sinh viên/GV] -->|1. Chat Request| API[API Gateway]
        API -->|2. Check Auth| Auth[Auth Service]
        
        subgraph "RAG Inference Flow"
            API -->|3. Rewrite Query| LLM_RW[Qwen Rewrite]
            LLM_RW -->|4. Retrieve (Filter Time/Scope)| VectorDB[(Qdrant)]
            VectorDB -->|5. Generate Answer| LLM_GEN[Qwen Generate]
        end
        
        LLM_GEN -->|6. Response + Citation| User
        User -->|7. Feedback (Like/Dislike)| DB[(PostgreSQL)]
    end

    subgraph "Offline Layer (Weekend Training)"
        DB -->|8. Export Bad Cases| Expert[Giảng viên Review]
        Expert -->|9. Correction| Dataset[(Golden Dataset)]
        Dataset -->|10. Fine-tune (DPO/LoRA)| Trainer[Training Process]
        Trainer -->|11. Update Adapter| LLM_GEN
    end
3. THIẾT KẾ CƠ SỞ DỮ LIỆU (DATABASE SCHEMA)
Kết hợp tính năng Versioning, Security (v1.1) và Feedback Loop (v2.0).

3.1. Relational DB (PostgreSQL)
Table users

id, username, password_hash, role

Table documents (Quản lý Version & Quyền hạn) | Column | Type | Description | | :--- | :--- | :--- | | id | Serial | PK | | filename | Varchar | Tên file | | version | Int | Phiên bản (1, 2...) | | is_active | Bool | Trạng thái hiện hành | | effective_date | Timestamp | Ngày hiệu lực | | expiry_date | Timestamp | Ngày hết hạn | | access_scope | Enum | 'public', 'private' (Bảo mật) | | target_id | Varchar | Mã SV/Lớp (nếu private) | | uploaded_by | FK | Giảng viên upload |

Table chat_history (Lịch sử Chat)

session_id (UUID), user_query, ai_response, created_at

Table feedback_loop (Dữ liệu Huấn luyện) | Column | Type | Description | | :--- | :--- | :--- | | id | Serial | PK | | chat_id | UUID | FK tới chat_history | | score | Int | 1 (Dislike) hoặc 5 (Like) | | rejected_response| Text | Câu trả lời AI sai (để train DPO) | | chosen_response | Text | Câu trả lời Giảng viên sửa lại (để train DPO) | | status | Varchar | 'pending', 'reviewed', 'trained' |

3.2. Vector Payload (Qdrant)
JSON

{
  "source_id": 101,
  "content": "Quy chế đào tạo tín chỉ...",
  "metadata": {
    "version": 2,
    "is_current": true,
    "effective_date": "2024-01-01",
    "access_scope": "public",
    "doc_type": "pdf_table" // Đánh dấu đây là bảng trích xuất từ PDF
  }
}
4. QUY TRÌNH XỬ LÝ DỮ LIỆU (DATA PIPELINES)
4.1. Ingestion Pipeline (Nạp liệu Đa định dạng)
Module xử lý đầu vào thông minh.

Excel Processor:

Dùng openpyxl: Unmerge cells (gỡ ô gộp).

Row-to-Text: Convert dòng thành câu văn.

PDF Processor (Nâng cấp v2.0):

Dùng pdfplumber: Quét từng trang.

Detect Table: Nếu phát hiện bảng -> Extract cấu trúc -> Convert sang Markdown Table -> Chunk nguyên khối (không cắt bảng).

Text thường: Cắt bằng RecursiveCharacterTextSplitter (chunk size ~500 chars).

Indexing:

Gắn Metadata: Time, Access Scope.

Vector hóa và lưu Qdrant.

4.2. Retrieval & Generation Pipeline
Rewrite: Viết lại câu hỏi user dựa trên lịch sử.

Filter:

is_current = True (Mặc định).

access_scope = 'public' OR (scope='private' AND user=target_id).

Generate: Qwen 2.5 sinh câu trả lời + Trích dẫn nguồn.

5. CHIẾN LƯỢC HUẤN LUYỆN (OFFLINE TRAINING STRATEGY)
Lưu ý: Không chạy training khi đang phục vụ sinh viên.

Thu thập: Sinh viên bấm Dislike -> Lưu vào feedback_loop.

Review (Human-in-the-loop): Cuối tuần, giảng viên vào Admin Dashboard, sửa lại câu trả lời sai -> Lưu vào cột chosen_response.

Training:

Khi có >100 mẫu dữ liệu đã sửa.

Chạy script Fine-tuning (DPO) tạo ra file Adapter (.gguf hoặc .safetensors).

Update: Load lại Ollama với Adapter mới vào sáng thứ 2.

6. FRONTEND DESIGN (REACT VITE)
Student Portal:

Chat Interface (Streaming Text).

Nút Feedback (👍 / 👎) sau mỗi câu trả lời.

Admin Portal:

Document Management (Upload, Version History).

Feedback Review UI: Giao diện cho giảng viên sửa câu trả lời sai của AI (So sánh Side-by-Side: Câu AI vs Câu sửa).