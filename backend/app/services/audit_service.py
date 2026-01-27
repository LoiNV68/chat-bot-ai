from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
import json
from typing import Optional, Any

class AuditService:
    @staticmethod
    def log(
        db: Session, 
        user_id: Optional[int], 
        action: str, 
        entity_type: str, 
        entity_id: str, 
        details: Any = None
    ):
        """
        Logs an action to the audit_logs table.
        """
        try:
            details_str = ""
            if details:
                if isinstance(details, (dict, list)):
                    details_str = json.dumps(details, default=str)
                else:
                    details_str = str(details)
            
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                details=details_str
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            # Fallback to avoid crashing the main transaction
            print(f"Failed to write audit log: {e}")
            db.rollback()
