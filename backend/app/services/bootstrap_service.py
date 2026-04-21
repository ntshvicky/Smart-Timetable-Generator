from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import School, User
from app.services.audit_service import AuditService


def ensure_superadmin(db: Session) -> None:
    settings = get_settings()
    email = settings.superadmin_email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        if existing.role != "superadmin":
            existing.role = "superadmin"
            db.commit()
        return

    school = db.scalar(select(School).where(School.name == "Platform Administration"))
    if not school:
        school = School(name="Platform Administration")
        db.add(school)
        db.flush()

    user = User(
        school_id=school.id,
        email=email,
        full_name=settings.superadmin_name,
        password_hash=hash_password(settings.superadmin_password),
        role="superadmin",
    )
    db.add(user)
    db.flush()
    AuditService(db).record("superadmin_created", user=user, entity_type="user", entity_id=user.id, detail={"email": email})
    db.commit()
