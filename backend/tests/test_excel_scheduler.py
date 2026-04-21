from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ClassSubjectRequirement, Section, Subject, Teacher, TimetableEntry
from app.services.excel_service import ExcelService
from app.services.gemini_service import GeminiConstraintService
from app.services.scheduler_service import SchedulerService


def import_demo(db: Session) -> None:
    service = ExcelService(db)
    stream = service.build_template()
    batch, errors = service.import_workbook(1, "template.xlsx", stream.getvalue())
    assert batch.status == "imported"
    assert errors == []


def test_excel_import_success(db: Session) -> None:
    import_demo(db)
    assert len(db.scalars(select(Section)).all()) == 3
    assert len(db.scalars(select(Subject)).all()) == 4
    assert len(db.scalars(select(Teacher)).all()) == 9


def test_excel_validation_duplicate_teacher(db: Session) -> None:
    service = ExcelService(db)
    stream = service.build_template()
    wb = load_workbook(stream)
    ws = wb["Teachers"]
    ws.append(["T-RAVI", "Duplicate Ravi", 5, 2])
    modified = BytesIO()
    wb.save(modified)
    batch, errors = service.import_workbook(1, "bad.xlsx", modified.getvalue())
    assert batch.status == "failed"
    assert any(error.column_name == "teacher_code" and "Duplicate" in error.message for error in errors)


def test_timetable_generation_success_and_subject_frequency(db: Session) -> None:
    import_demo(db)
    result = SchedulerService(db).generate(1, 1, "Test Timetable")
    section = db.scalar(select(Section).where(Section.display_name == "Class 5A"))
    math = db.scalar(select(Subject).where(Subject.code == "MATH"))
    count = len(db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_id == result.timetable_id, TimetableEntry.section_id == section.id, TimetableEntry.subject_id == math.id)).all())
    assert count == 5
    assert result.timetable_id > 0


def test_impossible_schedule_reports_capacity_conflict(db: Session) -> None:
    import_demo(db)
    section = db.scalar(select(Section).where(Section.display_name == "Class 5A"))
    subject = db.scalar(select(Subject).where(Subject.code == "MATH"))
    req = db.scalar(select(ClassSubjectRequirement).where(ClassSubjectRequirement.section_id == section.id, ClassSubjectRequirement.subject_id == subject.id))
    req.periods_per_week = 99
    db.commit()
    result = SchedulerService(db).generate(1, 1, "Impossible")
    assert any(conflict.code == "class_over_capacity" for conflict in result.conflicts)


def test_teacher_availability_conflict_detection(db: Session) -> None:
    import_demo(db)
    result = SchedulerService(db).generate(1, 1, "Availability")
    section = db.scalar(select(Section).where(Section.display_name == "Class 5A"))
    teacher = db.scalar(select(Teacher).where(Teacher.code == "T-RAVI"))
    subject = db.scalar(select(Subject).where(Subject.code == "MATH"))
    conflicts = SchedulerService(db).validate_assignment(1, result.timetable_id, section.id, "Wednesday", 4, subject.id, teacher.id)
    assert any(conflict.code == "teacher_unavailable" for conflict in conflicts)


@pytest.mark.asyncio
async def test_gemini_fallback_parser_returns_valid_schema(db: Session) -> None:
    result = await GeminiConstraintService(db).parse(1, "Teacher Ravi is unavailable on Wednesday period 4 and 5")
    assert result.provider == "fallback"
    assert result.constraints[0].rule_type == "teacher_unavailable"
    assert "Wednesday" in result.constraints[0].day_scope
    assert 4 in result.constraints[0].period_scope


def test_manual_edit_prevents_teacher_double_booking(db: Session) -> None:
    import_demo(db)
    result = SchedulerService(db).generate(1, 1, "Manual")
    section = db.scalar(select(Section).where(Section.display_name == "Class 5A"))
    other_section = db.scalar(select(Section).where(Section.display_name == "Class 5B"))
    teacher = db.scalar(select(Teacher).where(Teacher.code == "T-RAVI"))
    subject = db.scalar(select(Subject).where(Subject.code == "MATH"))
    busy_entry = db.scalar(select(TimetableEntry).where(TimetableEntry.timetable_id == result.timetable_id, TimetableEntry.section_id == other_section.id, TimetableEntry.day == "Monday", TimetableEntry.period_number == 1))
    busy_entry.subject_id = subject.id
    busy_entry.teacher_id = teacher.id
    db.commit()
    conflicts = SchedulerService(db).manual_edit(1, result.timetable_id, section.id, "Monday", 1, subject.id, teacher.id)
    assert any(conflict.code == "teacher_double_booked" for conflict in conflicts)
