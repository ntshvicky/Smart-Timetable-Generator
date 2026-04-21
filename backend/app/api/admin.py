from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.api.deps import require_superadmin
from app.core.database import get_db
from app.models import AuditLog, School, Timetable, TimetableEntry, UploadBatch, User
from app.schemas.admin import AdminActivity, AdminOverview, AdminSchool, AdminStats, AdminUser

router = APIRouter(prefix="/admin", tags=["superadmin"])


@router.get("/overview", response_model=AdminOverview)
def overview(db: Session = Depends(get_db), _: User = Depends(require_superadmin)) -> AdminOverview:
    schools = db.scalars(select(School).order_by(School.created_at.desc())).all()
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    uploads = db.scalars(select(UploadBatch).order_by(UploadBatch.created_at.desc())).all()
    timetables = db.scalars(select(Timetable).order_by(Timetable.created_at.desc())).all()
    school_names = {school.id: school.name for school in schools}
    user_emails = {user.id: user.email for user in users}

    user_counts = dict(db.execute(select(User.school_id, func.count(User.id)).group_by(User.school_id)).all())
    upload_counts = dict(db.execute(select(UploadBatch.school_id, func.count(UploadBatch.id)).group_by(UploadBatch.school_id)).all())
    timetable_counts = dict(db.execute(select(Timetable.school_id, func.count(Timetable.id)).group_by(Timetable.school_id)).all())
    manual_edits = db.scalar(select(func.count(TimetableEntry.id)).where(TimetableEntry.is_manual.is_(True))) or 0
    activity = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)).all()

    return AdminOverview(
        stats=AdminStats(
            schools=len(schools),
            users=len(users),
            uploads=len(uploads),
            timetables=len(timetables),
            manual_edits=manual_edits,
        ),
        schools=[
            AdminSchool(
                id=school.id,
                name=school.name,
                created_at=school.created_at,
                users=int(user_counts.get(school.id, 0)),
                uploads=int(upload_counts.get(school.id, 0)),
                timetables=int(timetable_counts.get(school.id, 0)),
            )
            for school in schools
        ],
        users=[
            AdminUser(
                id=user.id,
                school_id=user.school_id,
                school_name=school_names.get(user.school_id, ""),
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                created_at=user.created_at,
            )
            for user in users
        ],
        activity=[
            AdminActivity(
                id=item.id,
                school_id=item.school_id,
                school_name=school_names.get(item.school_id) if item.school_id else None,
                user_id=item.user_id,
                user_email=user_emails.get(item.user_id) if item.user_id else None,
                action=item.action,
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                detail=item.detail,
                created_at=item.created_at,
            )
            for item in activity
        ],
    )
