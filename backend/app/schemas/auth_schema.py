from typing import Optional
from pydantic import BaseModel, EmailStr
from enum import Enum

class UserRoleEnum(str, Enum):
    ADMIN = "admin"
    LECTURER = "lecturer"
    USER = "user"

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None

class UserLogin(BaseModel):
    username: str # This is actually email in our case usually, but OAuth2 uses username field
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserCreateByAdmin(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    is_superuser: bool = False
    role: str = "user"  # admin, lecturer, user

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool = False
    role: Optional[UserRoleEnum] = UserRoleEnum.USER
    
    class Config:
        from_attributes = True
