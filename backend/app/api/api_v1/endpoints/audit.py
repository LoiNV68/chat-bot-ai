from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.api import deps
from app.models.user import User
from app.models.audit_log import AuditLog
from sqlalchemy import desc

router = APIRouter()

@router.get("/", response_model=List[dict])  # Simplified Schema for now
def get_audit_logs(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve audit logs.
    """
    logs = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit).all()
    
    # Simple manual serialization to avoid circular dependencies or complex Pydantic setup for now
    result = []
    for log in logs:
        # Fetch user name if possible (n+1 issue here but acceptable for prototype/low volume)
        user_name = "Unknown"
        if log.user_id:
             user = db.query(User).filter(User.id == log.user_id).first()
             if user:
                 user_name = user.full_name or user.email

        result.append({
            "id": log.id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "timestamp": log.timestamp,
            "user_name": user_name
        })
    return result
