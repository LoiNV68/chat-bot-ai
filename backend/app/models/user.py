import enum
from sqlalchemy import Boolean, Column, Integer, String
from app.db.base_class import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"       # Full access
    LECTURER = "lecturer" # Can manage documents, but not users
    USER = "user"         # Basic user (chat only)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)  # Kept for backward compatibility
    role = Column(String, default="user")  # Store as string: admin, lecturer, user
