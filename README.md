<div align="center">

# CHAT-BOT-AI

_Nâng tầm Trò chuyện, Mở khóa Kiến thức Tức thì_

![GitHub last commit](https://img.shields.io/github/last-commit/LoiNV68/Chat-bot-AI?style=flat)
![GitHub top language](https://img.shields.io/github/languages/top/LoiNV68/Chat-bot-AI?style=flat)
![GitHub language count](https://img.shields.io/github/languages/count/LoiNV68/Chat-bot-AI?style=flat)

_Được xây dựng với các công cụ và công nghệ:_

![JSON](https://img.shields.io/badge/JSON-%23000000.svg?style=flat-square&logo=JSON&logoColor=white)
![Markdown](https://img.shields.io/badge/Markdown-%23000000.svg?style=flat-square&logo=markdown&logoColor=white)
![npm](https://img.shields.io/badge/npm-%23CB3837.svg?style=flat-square&logo=npm&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-%23D71F00.svg?style=flat-square&logo=sqlalchemy&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-%23323330.svg?style=flat-square&logo=javascript&logoColor=%23F7DF1E)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)
![LangChain](https://img.shields.io/badge/LangChain-%23005571.svg?style=flat-square&logo=langchain)
<br>
![React](https://img.shields.io/badge/React-%2320232a.svg?style=flat-square&logo=react&logoColor=%2361DAFB)
![Pytest](https://img.shields.io/badge/Pytest-%230A9EDC.svg?style=flat-square&logo=pytest&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-%230db7ed.svg?style=flat-square&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3670A0?style=flat-square&logo=python&logoColor=ffdd54)
![TypeScript](https://img.shields.io/badge/TypeScript-%23007ACC.svg?style=flat-square&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-%23646CFF.svg?style=flat-square&logo=vite&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=flat-square&logo=pandas&logoColor=white)

</div>

<div align="center">
  <strong><a href="README.md">Tiếng Việt</a> | <a href="README.en.md">English</a></strong>
</div>

---

## Mục lục

- [Tổng quan](#tổng-quan)
- [Bắt đầu](#bắt-đầu)
  - [Điều kiện tiên quyết](#điều-kiện-tiên-quyết)
  - [Cài đặt](#cài-đặt)
  - [Sử dụng (Triển khai Production)](#sử-dụng-triển-khai-production)
  - [Thử nghiệm (Môi trường Development Local)](#thử-nghiệm-môi-trường-development-local)
- [Kiến trúc](#kiến-trúc)

---

## Tổng quan

**chat-bot-ai** là một nền tảng toàn diện để phát triển các chatbot AI an toàn, có khả năng mở rộng, được thiết kế riêng cho các tổ chức giáo dục. Nó tích hợp quản lý tài liệu, tìm kiếm vector và AI đàm thoại trong một kiến trúc ứng dụng vùng chứa (containerized), cho phép triển khai liền mạch và tương tác trong thời gian thực.

### Tại sao nên chọn chat-bot-ai?

Dự án này trao quyền cho các nhà phát triển xây dựng các chatbot ngoại tuyến thông minh cho trường đại học với các tính năng như:

- 🧩 **Mảnh ghép**: Kiến trúc microservices dạng module hỗ trợ triển khai linh hoạt mở rộng (Build NGINX đa giai đoạn, Frontend cực nhẹ ~25MB).
- 🚀 **Tên lửa**: Tính năng RAG (Retrieval-augmented generation) cho các câu trả lời chính xác, nhận thức đúng ngữ cảnh (Deterministic RAG, độ chính xác tuyệt đối 100%).
- 🗄️ **Tủ hồ sơ**: Khả năng tiếp nhận, chuẩn hóa và tìm kiếm tài liệu nâng cao (Bảo toàn định dạng Markdown Tables).
- 🔒 **Khóa**: Xác thực người dùng mạnh mẽ và kiểm soát truy cập dựa trên vai trò.
- 💬 **Bong bóng chat**: Trò chuyện theo thời gian thực với các vòng lặp phản hồi và học tập liên tục.
- ⚙️ **Bánh răng**: Scripts khởi động tự động giúp hợp lý hóa quá trình phát triển và kiểm thử (Tích hợp PaddleOCR tự sửa lỗi dính chữ).

---

## Bắt đầu

### Điều kiện tiên quyết

Dự án này yêu cầu các thành phần phụ thuộc sau:

- **Ngôn ngữ lập trình:** Python 3.11, TypeScript
- **Trình quản lý gói:** Pip, Npm
- **Môi trường chạy Container:** Docker, Docker Compose

### Cài đặt

Build chat-bot-ai từ mã nguồn và cài đặt các thư viện:

1. Clone kho lưu trữ:

```bash
> git clone https://github.com/LoiNV68/Chat-bot-AI.git
```

2. Di chuyển vào thư mục dự án:

```bash
> cd Chat-bot-AI
```

### Sử dụng (Triển khai Production)

Sử dụng Docker:

```bash
> docker-compose up -d --build
```

_Hệ thống sẽ tự động build Frontend & Backend, tải Database (Postgres, Qdrant) và khởi chạy._

- **Giao diện Chatbot:** `http://localhost:5173` (hoặc `http://localhost:80`)

### Thử nghiệm (Môi trường Development Local)

Dự án được cấu hình để chạy theo dạng Hybrid: Database trên Linux (WSL) và Code chạy trực tiếp trên Windows.

1. Khởi động các dịch vụ Database (Sử dụng Docker trên bất kỳ máy nào):

```bash
> docker-compose -f docker-compose.db.yml up -d
```

2. Khởi động Backend & Frontend (Windows Terminal):

```powershell
> .\run.ps1
```

---

## Kiến trúc

Vui lòng tham khảo phân tích kỹ thuật và tài liệu kiến trúc của chúng tôi:

- [MASTER_DESIGN.md](./MASTER_DESIGN.md): Chi tiết Data Pipeline và Chiến lược Đào tạo DPO Offline.
- [SERVICE_BASE.md](./backend/SERVICE_BASE.md): Cấu trúc thư mục, luồng làm việc Backend và RAG Engine.
- [REQUIREMENT.md](./backend/REQUIREMENT.md): Đặc tả yêu cầu hệ thống.
