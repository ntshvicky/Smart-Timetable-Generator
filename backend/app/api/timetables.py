from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Section, Timetable, User
from app.schemas.timetable import GenerateRequest, ManualEditRequest, TimetableResponse
from app.services.scheduler_service import SchedulerService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/timetables", tags=["timetables"])


@router.post("/generate", response_model=TimetableResponse)
def generate(payload: GenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = SchedulerService(db).generate(current_user.school_id, current_user.id, payload.name)
    AuditService(db).record("timetable_generated", user=current_user, entity_type="timetable", entity_id=result.timetable_id, detail={"name": result.name, "status": result.status, "conflict_count": len(result.conflicts)})
    db.commit()
    return result


@router.get("")
def list_timetables(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.scalars(select(Timetable).where(Timetable.school_id == current_user.school_id).order_by(Timetable.id.desc())).all()
    return [{"id": row.id, "name": row.name, "status": row.status, "created_at": row.created_at.isoformat()} for row in rows]


@router.get("/{timetable_id}", response_model=TimetableResponse)
def get_timetable(timetable_id: int, section_id: int | None = None, teacher_id: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return SchedulerService(db).get_timetable(current_user.school_id, timetable_id, section_id, teacher_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{timetable_id}/entries", response_model=list)
def edit_entry(timetable_id: int, payload: ManualEditRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conflicts = SchedulerService(db).manual_edit(current_user.school_id, timetable_id, payload.section_id, payload.day, payload.period_number, payload.subject_id, payload.teacher_id, payload.notes)
    if not conflicts:
        AuditService(db).record("timetable_entry_edited", user=current_user, entity_type="timetable", entity_id=timetable_id, detail=payload.model_dump())
        db.commit()
    return [c.model_dump() for c in conflicts]


@router.post("/{timetable_id}/validate", response_model=list)
def validate_entry(timetable_id: int, payload: ManualEditRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conflicts = SchedulerService(db).validate_assignment(current_user.school_id, timetable_id, payload.section_id, payload.day, payload.period_number, payload.subject_id, payload.teacher_id)
    return [c.model_dump() for c in conflicts]


@router.get("/{timetable_id}/export")
def export_timetable(timetable_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    response = SchedulerService(db).get_timetable(current_user.school_id, timetable_id)
    AuditService(db).record("timetable_exported", user=current_user, entity_type="timetable", entity_id=timetable_id)
    db.commit()
    sections = {s.id: s.display_name for s in db.scalars(select(Section).where(Section.school_id == current_user.school_id)).all()}
    wb = Workbook()
    wb.remove(wb.active)
    for section_id, section_name in sections.items():
        ws = wb.create_sheet(section_name[:31])
        ws.append(["Day"] + [f"Period {p}" for p in response.periods])
        section_entries = [e for e in response.entries if e.section_id == section_id]
        for day in response.days:
            row = [day]
            for period in response.periods:
                cell = next((e for e in section_entries if e.day == day and e.period_number == period), None)
                row.append("Break" if cell and cell.is_break else (f"{cell.subject_code or ''} ({cell.teacher_name or ''})" if cell else ""))
            ws.append(row)
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="timetable_{timetable_id}.xlsx"'})
