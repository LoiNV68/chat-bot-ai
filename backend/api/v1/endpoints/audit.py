from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.api import deps
from app.models.audit_log import AuditLog
from app.schemas.audit_schema import AuditLog as AuditLogSchema

router = APIRouter()

@router.get("/", response_model=List[AuditLogSchema])
async def read_audit_logs(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    # current_user: User = Depends(deps.get_current_active_superuser), # Uncomment to restrict to admins
) -> Any:
    """
    Retrieve audit logs.
    """
    result = await db.execute(select(AuditLog).offset(skip).limit(limit))
    logs = result.scalars().all()
    return logs
