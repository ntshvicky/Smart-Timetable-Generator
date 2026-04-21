import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        action: str,
        user: User | None = None,
        school_id: int | None = None,
        entity_type: str = "",
        entity_id: int | str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            AuditLog(
                school_id=school_id if school_id is not None else (user.school_id if user else None),
                user_id=user.id if user else None,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id or ""),
                detail=json.dumps(detail or {}, default=str),
            )
        )
