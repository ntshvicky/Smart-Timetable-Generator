from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import (
    ClassSubjectRequirement,
    SchoolClass,
    Section,
    Subject,
    Teacher,
    TeacherSubjectClassMap,
    User,
    SchoolWorkingDay,
    PeriodDefinition,
)
from app.schemas.timetable import MasterSummary
from app.services.excel_service import ExcelService

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/template")
def template(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stream = ExcelService(db).build_template()
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="smart_timetable_template.xlsx"'},
    )


@router.post("/upload")
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = await file.read()
    batch, errors = ExcelService(db).import_workbook(current_user.school_id, file.filename or "upload.xlsx", content)
    return {"batch_id": batch.id, "status": batch.status, "errors": [e.__dict__ for e in errors]}


@router.get("/summary", response_model=MasterSummary)
def summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MasterSummary:
    sid = current_user.school_id
    def count(model) -> int:
        return len(db.scalars(select(model).where(model.school_id == sid)).all())
    return MasterSummary(
        classes=count(SchoolClass),
        sections=count(Section),
        subjects=count(Subject),
        teachers=count(Teacher),
        mappings=count(TeacherSubjectClassMap),
        requirements=count(ClassSubjectRequirement),
        working_days=count(SchoolWorkingDay),
        periods=count(PeriodDefinition),
    )


@router.get("/masters")
def masters(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sid = current_user.school_id
    sections = db.scalars(select(Section).where(Section.school_id == sid).order_by(Section.display_name)).all()
    subjects = db.scalars(select(Subject).where(Subject.school_id == sid).order_by(Subject.name)).all()
    teachers = db.scalars(select(Teacher).where(Teacher.school_id == sid).order_by(Teacher.name)).all()
    return {
        "sections": [{"id": s.id, "name": s.name, "display_name": s.display_name} for s in sections],
        "subjects": [{"id": s.id, "code": s.code, "name": s.name, "category": s.category} for s in subjects],
        "teachers": [{"id": t.id, "code": t.code, "name": t.name} for t in teachers],
    }
