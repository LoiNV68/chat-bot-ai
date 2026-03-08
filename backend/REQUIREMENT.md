# Requirement

- input đầu vào là các file pdf, word, excel,... thuộc dạng tài liệu do Admin hoặc giảng viên thêm vào, AI có thể đọc hiểu các tài liệu, và tự học giao tiếp, tự học hỏi các kiến thức mới,...

- **output** khi người dùng hỏi về thông tin học tập ví dụ "lịch thi tuần này của khóa 11 là ngày bao nhiêu", "thầy cô nào dạy môn Lịch sử Đảng" - AI sẽ đọc file và trả kết quả. Hỗ trợ xử lý bảng biểu thông minh và nhận diện câu hỏi phức tạp (như "Học phí học kỳ 1" hay "Nghỉ tết") thông qua các cụm Heuristic Fallbacks để đảm bảo kết quả chính xác 100%.

- Có thể trả lời linh hoạt, nếu không có tài liệu hoặc thông tin sẽ từ chối trả lời khéo léo theo đúng quy trình ("Không tìm thấy thông tin... vui lòng liên hệ phòng ban..."), không được bịa đặt thông tin.

# Hướng dẫn chạy (Hybrid: Windows Code + WSL Data HOẶC Docker)

Bạn có thể chạy dự án theo 2 cách:

## Cách 1: Chạy Full Bằng Docker (Dành cho máy khác)

Nếu bạn mang sang máy khác, bạn có thể chạy toàn bộ dự án chỉ với một lệnh Docker.
Mở Terminal ở thư mục gốc chứa `docker-compose.yml` và chạy:

```bash
docker-compose up -d --build
```

Hệ thống sẽ tự build Frontend, Backend, và kéo Database (Postgres, Qdrant) về.

## Cách 2: Chạy Dev Cục Bộ (Windows + WSL)

- **WSL (Ubuntu)**: Chạy Data & AI (Postgres, Qdrant, llama-server).
- **Windows**: Chạy Code (Backend & Frontend).

### 2.1. Terminal 1 (WSL - Ubuntu)

**Bước A: AI Engine**
Bật llama-server của bạn (Port 8080).

**Bước B: Data Services**
Chạy script `run.sh` để bật Postgres & Qdrant:

```bash
./run.sh
```

### 2.2. Terminal 2 (Windows - PowerShell)

Chạy script `run.ps1` để bật Backend chạy uvicorn & Frontend chạy Vite:

```powershell
.\run.ps1
```

_(Nếu lỗi "Python not found", hãy cài Python trên Windows và thêm vào PATH)_
