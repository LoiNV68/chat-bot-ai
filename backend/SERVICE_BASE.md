/backend
/app
/api # API Route Handlers (Controller)
/v1
/endpoints
auth.py # Login, Token
chat.py # Chat, History, Feedback
documents.py # Upload, List, Versioning
api.py # Router Aggregator
/core # Core configurations
config.py # Env vars (DB URL, Secret Key)
security.py # JWT, Password Hashing
exceptions.py # Custom HTTP Exceptions
/db # Database Access
base.py # SQLAlchemy Base
session.py # Async Engine & Session
/models # ORM Models (User, Document...)
/schemas # Pydantic Models (Request/Response DTOs)
auth_schema.py
chat_schema.py
doc_schema.py
/services # BUSINESS LOGIC (Core Logic nằm ở đây)
auth_service.py
chat_engine.py # Logic RAG: Deterministic Fallbacks, Retrieve, Generate
ingestion_master.py # Core xử lý Document: PDF/Excel -> Chunks & Tables
ingestion_service.py # API pipeline lưu file -> DB -> Vector
vector_store.py # Giao tiếp Qdrant
llm_client.py # Giao tiếp Ollama
main.py # Entry point
/tests # Pytest
requirements.txt
docker-compose.yml 2. DATABASE MODELS (SQLALCHEMY ORM)File: app/db/modelsThiết kế ORM Map chính xác với Schema PostgreSQL đã chốt.2.1. Documents Model (Quản lý Version & Quyền)Pythonfrom sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from app.db.base import Base
import enum
from datetime import datetime

class AccessScope(str, enum.Enum):
PUBLIC = "public"
PRIVATE = "private"

class Document(Base):
**tablename** = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    version = Column(Integer, default=1)

    # Versioning Control
    is_active = Column(Boolean, default=True)
    effective_date = Column(DateTime, nullable=True) # Ngày bắt đầu hiệu lực
    expiry_date = Column(DateTime, nullable=True)    # Ngày hết hạn
    parent_id = Column(Integer, ForeignKey("documents.id"), nullable=True) # Link bản cũ

    # Security
    access_scope = Column(Enum(AccessScope), default=AccessScope.PUBLIC)
    target_id = Column(String, nullable=True) # Mã SV/Lớp nếu private

    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

2.2. Chat & Feedback ModelPythonclass ChatHistory(Base):
**tablename** = "chat_history"

    session_id = Column(String, primary_key=True) # UUID
    user_id = Column(Integer, ForeignKey("users.id"))
    user_query = Column(String, nullable=False)
    ai_response = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FeedbackLoop(Base):
**tablename** = "feedback_loop"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String, ForeignKey("chat_history.session_id"))
    score = Column(Integer) # 1 or 5

    # Dữ liệu cho DPO Training
    rejected_response = Column(String) # Câu AI trả lời sai
    chosen_response = Column(String)   # Câu giảng viên sửa lại

    status = Column(String, default="pending") # pending, reviewed, trained

3.  CORE SERVICES (BUSINESS LOGIC)Đây là "trái tim" của hệ thống.3.1. Ingestion Service (app/services/ingestion_service.py)Logic xử lý file đầu vào.Pythonclass IngestionService:
    def **init**(self, vector_store: VectorStoreService, db: AsyncSession):
    self.vector_store = vector_store
    self.db = db

        def process_upload(self, file: UploadFile, metadata: DocUploadSchema, user_id: int):
            # 1. Version Control Check
            # Kiểm tra xem có file nào tên giống vậy đang active không
            # Nếu có -> Xóa vectors cũ -> Tạo bản mới version++

            # 2. Extract & Parse
            # Chuyển việc bóc tách cho IngestionMaster
            # - Tự động nhận diện PDF bảng biểu (pdfplumber) -> Giữ nguyên Markdown Table
            # - Tự động gọi OCR nếu là bản scan (WSL PaddleOCR)
            # - Sửa lỗi chính tả OCR (Heuristics)
            # - Chia đoạn văn bản thông minh theo cấu trúc Luật (Điều, Khoản)

            # 3. Save to Vector DB
            await self.vector_store.upsert_vectors(chunks)

            return {"status": "success", "chunks_count": len(chunks)}

    3.2. Chat RAG Engine (app/services/chat_engine.py)Logic xử lý tìm kiếm và trả lời.Pythonclass ChatService:
    async def chat(self, user_query: str, history: List[str], user_info: User): # Bước 1: Rewrite Query (Dành riêng cho ngữ cảnh đối thoại)
    refined_query = await self.llm.rewrite_query(user_query, history)

            # Bước 2: Build Filter (Time + Security)
            filters = self._build_security_filter(user_info)

            # Bước 3: Retrieve (Tìm kiếm Vector)
            context_docs = await self.vector_store.search(refined_query, filters)

            # Bước 4: Heuristic Filters (Sàng lọc chủ đề & Năm học)
            valid_docs = self._apply_topic_guard(context_docs)

            # Bước 5: Deterministic Checking
            # Hệ thống dùng các hàm Code cứng tự trích xuất dữ liệu khó như Lệ Phí, Lịch Nghỉ Tết
            # Nếu bắt trúng Rule -> Trả về kết quả luôn để đảm bảo chính xác tuyệt đối.
            if rule_triggered:
                 return deterministic_answer

            # Bước 6: Generate (LLM trả lời)
            return self.llm.generate_stream(valid_docs, refined_query)

        def _build_security_filter(self, user: User):
            return {
                "should": [
                    { "key": "access_scope", "match": { "value": "public" } },
                    {
                        "must": [
                            { "key": "access_scope", "match": { "value": "private" } },
                            { "key": "target_id", "match": { "value": user.username } }
                        ]
                    }
                ]
            }

4.  API SPECIFICATION (ENDPOINTS)

4.1. Authentication (/api/v1/auth)
Method | Endpoint | Body/Params | Description
--- | --- | --- | ---
POST | /login | username, password | Trả về JWT Token
GET | /me | Header Auth | Lấy thông tin user hiện tại

4.2. Users Management (/api/v1/users) - Admin Only
Method | Endpoint | Body/Params | Description
--- | --- | --- | ---
GET | / | query skip, limit | Lấy danh sách tài khoản
POST | / | email, password, role | Tạo tài khoản mới
PUT | /{id} | email, password, role | Sửa đổi thông tin tài khoản
DELETE | /{id} | | Xóa vĩnh viễn tài khoản (Hard delete, cascade to chats)
PATCH | /{id}/toggle-active | | Khóa / Mở khóa tài khoản

4.3. Documents (/api/v1/documents)MethodEndpointBody/ParamsDescriptionPOST/uploadfile, effective_date, scopeUpload tài liệu (Multipart/Form-data)GET/?limit=10&active=trueLấy danh sách tài liệuGET/{id}/historyLấy các version cũ của 1 filePOST/{id}/rollbackKhôi phục version cũ4.3. Chat (/api/v1/chat)MethodEndpointBodyDescriptionPOST/completion{query, history}Chat Stream (Server-Sent Events)POST/feedback{session_id, score}Gửi like/dislike4.4. Feedback Loop (/api/v1/feedback) - Dành cho AdminMethodEndpointBodyDescriptionGET/bad-casesLấy danh sách câu trả lời bị DislikePOST/correct{id, chosen_response}Admin nhập câu trả lời đúng5. BẢO MẬT & PERFORMANCE5.1. Authentication MiddlewareFile: app/core/deps.pySử dụng OAuth2PasswordBearer. Mọi request vào các route bảo mật đều phải qua hàm get_current_user để decode JWT và lấy thông tin user.5.2. Async DatabaseSử dụng asyncpg driver cho PostgreSQL để đảm bảo non-blocking I/O. Khi có 100 sinh viên chat cùng lúc, server không bị treo chờ Database.5.3. Vector ConnectionSử dụng QdrantClient(url=..., prefer_grpc=True) để tối ưu tốc độ tìm kiếm.
