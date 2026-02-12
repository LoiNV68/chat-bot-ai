from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core import security
from app.core.config import settings
from app.models.user import User
from app.schemas.auth_schema import TokenPayload
from app.db.session import get_db

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể xác thực thông tin đăng nhập",
        )
    
    stmt = select(User).where(User.id == token_data.sub)
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản không còn hoạt động")
    return user

async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Chỉ admin mới có quyền truy cập"""
    if not current_user.is_superuser and current_user.role != "admin":
        raise HTTPException(
            status_code=400, detail="Người dùng không có đủ quyền hạn"
        )
    return current_user

async def get_current_content_manager(
    current_user: User = Depends(get_current_user),
) -> User:
    """Admin và Giảng viên có thể quản lý nội dung (tài liệu)"""
    allowed_roles = ["admin", "lecturer"]
    if not current_user.is_superuser and current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=400, detail="Bạn cần quyền Giảng viên hoặc Admin để thực hiện thao tác này"
        )
    return current_user

# Biệt danh để thuận tiện
get_current_superuser = get_current_active_superuser
get_current_lecturer = get_current_content_manager
