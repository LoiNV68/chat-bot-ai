from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.db.session import get_db
from app.api import deps
from app.models.user import User
from app.schemas.auth_schema import UserResponse, UserCreateByAdmin, UserUpdate
from app.core import security

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_superuser),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    List all users except current admin (Admin only)
    """
    stmt = select(User).where(User.id != current_user.id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return users


@router.post("/", response_model=UserResponse)
async def create_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreateByAdmin,
    current_user: User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Create new user (Admin only)
    """
    # Check if email exists
    stmt = select(User).where(User.email == user_in.email)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Email này đã tồn tại trong hệ thống",
        )
    
    # Role is stored as string directly
    user_role = user_in.role.value if hasattr(user_in.role, 'value') else user_in.role
    
    user = User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        is_superuser=user_in.is_superuser or user_role == "admin",
        role=user_role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Get user by ID (Admin only)
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Update user (Admin only)
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    # Prevent admin from demoting themselves
    if user.id == current_user.id and user_in.is_superuser is False:
        raise HTTPException(status_code=400, detail="Bạn không thể tự hạ quyền admin của mình")
    
    update_data = user_in.model_dump(exclude_unset=True)
    
    # Hash password if provided
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = security.get_password_hash(update_data["password"])
        del update_data["password"]
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Deactivate user (Admin only) - Soft delete
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Bạn không thể xóa tài khoản của chính mình")
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    user.is_active = False
    await db.commit()
    return {"message": "Đã vô hiệu hóa tài khoản"}


@router.patch("/{user_id}/toggle-admin", response_model=UserResponse)
async def toggle_admin_role(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Toggle superuser status (Admin only)
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Bạn không thể thay đổi quyền của chính mình")
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    user.is_superuser = not user.is_superuser
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}/toggle-active", response_model=UserResponse)
async def toggle_active_status(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Toggle user active status (Admin only)
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Bạn không thể vô hiệu hóa tài khoản của chính mình")
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)
    return user
