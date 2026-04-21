from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    AcademicYear,
    ClassSubjectRequirement,
    PeriodDefinition,
    SchoolWorkingDay,
    SchedulingConstraint,
    Section,
    Subject,
    Teacher,
    TeacherAvailability,
    TeacherSubjectClassMap,
    Timetable,
    TimetableEntry,
)
from app.schemas.timetable import Conflict, TimetableCell, TimetableResponse


@dataclass
class Assignment:
    section_id: int
    subject_id: int
    teacher_id: int


class SchedulerService:
    def __init__(self, db: Session):
        self.db = db

    def generate(self, school_id: int, user_id: int | None, name: str) -> TimetableResponse:
        days = self._days(school_id)
        periods = self._periods(school_id)
        break_periods = {p.period_number for p in periods if p.is_break}
        sections = self.db.scalars(select(Section).where(Section.school_id == school_id)).all()
        conflicts = self._preflight(school_id, sections, days, periods)
        timetable = Timetable(school_id=school_id, academic_year_id=self._active_year_id(school_id), name=name, status="generated", generated_by_user_id=user_id)
        self.db.add(timetable)
        self.db.flush()

        teacher_busy: set[tuple[int, str, int]] = set()
        teacher_day_load: dict[tuple[int, str], int] = {}
        constraints = self._active_constraints(school_id)

        for section in sections:
            required = self._expanded_requirements(school_id, section.id)
            for day in days:
                previous_subject_id: int | None = None
                for period in periods:
                    if period.period_number in break_periods:
                        self._entry(timetable, section.id, day, period.period_number, None, None, notes="Break")
                        continue
                    if not required:
                        self._entry(timetable, section.id, day, period.period_number, None, None, notes="Free")
                        continue
                    assignment = self._pick_assignment(
                        school_id,
                        section.id,
                        required,
                        day,
                        period.period_number,
                        previous_subject_id,
                        teacher_busy,
                        teacher_day_load,
                        constraints,
                    )
                    if not assignment:
                        conflicts.append(Conflict(code="unfilled_slot", message=f"No valid assignment for section {section.display_name} on {day} period {period.period_number}", context={"section_id": section.id, "day": day, "period": period.period_number}))
                        self._entry(timetable, section.id, day, period.period_number, None, None, notes="Unfilled")
                        continue
                    self._entry(timetable, section.id, day, period.period_number, assignment.subject_id, assignment.teacher_id)
                    teacher_busy.add((assignment.teacher_id, day, period.period_number))
                    teacher_day_load[(assignment.teacher_id, day)] = teacher_day_load.get((assignment.teacher_id, day), 0) + 1
                    previous_subject_id = assignment.subject_id
                    required.remove(assignment.subject_id)
            for subject_id in required:
                subject = self.db.get(Subject, subject_id)
                conflicts.append(Conflict(code="frequency_unmet", message=f"{subject.name if subject else subject_id} could not be fully allocated for {section.display_name}", context={"section_id": section.id, "subject_id": subject_id}))

        timetable.conflict_summary = json.dumps([c.model_dump() for c in conflicts])
        timetable.status = "conflicts" if conflicts else "generated"
        self.db.commit()
        return self.get_timetable(school_id, timetable.id)

    def get_timetable(self, school_id: int, timetable_id: int, section_id: int | None = None, teacher_id: int | None = None) -> TimetableResponse:
        timetable = self.db.get(Timetable, timetable_id)
        if not timetable or timetable.school_id != school_id:
            raise ValueError("Timetable not found")
        stmt = select(TimetableEntry).where(TimetableEntry.school_id == school_id, TimetableEntry.timetable_id == timetable_id)
        if section_id:
            stmt = stmt.where(TimetableEntry.section_id == section_id)
        if teacher_id:
            stmt = stmt.where(TimetableEntry.teacher_id == teacher_id)
        entries = self.db.scalars(stmt).all()
        subjects = {s.id: s for s in self.db.scalars(select(Subject).where(Subject.school_id == school_id)).all()}
        teachers = {t.id: t for t in self.db.scalars(select(Teacher).where(Teacher.school_id == school_id)).all()}
        cells = [
            TimetableCell(
                id=e.id,
                day=e.day,
                period_number=e.period_number,
                section_id=e.section_id,
                subject_id=e.subject_id,
                subject_code=subjects[e.subject_id].code if e.subject_id and e.subject_id in subjects else None,
                subject_name=subjects[e.subject_id].name if e.subject_id and e.subject_id in subjects else None,
                teacher_id=e.teacher_id,
                teacher_code=teachers[e.teacher_id].code if e.teacher_id and e.teacher_id in teachers else None,
                teacher_name=teachers[e.teacher_id].name if e.teacher_id and e.teacher_id in teachers else None,
                is_break=e.subject_id is None and e.notes == "Break",
                is_manual=e.is_manual,
                notes=e.notes,
            )
            for e in entries
        ]
        conflicts = [Conflict(**item) for item in json.loads(timetable.conflict_summary or "[]")]
        return TimetableResponse(timetable_id=timetable.id, name=timetable.name, status=timetable.status, days=self._days(school_id), periods=[p.period_number for p in self._periods(school_id)], entries=cells, conflicts=conflicts)

    def manual_edit(self, school_id: int, timetable_id: int, section_id: int, day: str, period_number: int, subject_id: int | None, teacher_id: int | None, notes: str = "") -> list[Conflict]:
        conflicts = self.validate_assignment(school_id, timetable_id, section_id, day, period_number, subject_id, teacher_id)
        if conflicts:
            return conflicts
        entry = self.db.scalar(select(TimetableEntry).where(TimetableEntry.school_id == school_id, TimetableEntry.timetable_id == timetable_id, TimetableEntry.section_id == section_id, TimetableEntry.day == day, TimetableEntry.period_number == period_number))
        if not entry:
            entry = TimetableEntry(school_id=school_id, timetable_id=timetable_id, section_id=section_id, day=day, period_number=period_number)
            self.db.add(entry)
        entry.subject_id = subject_id
        entry.teacher_id = teacher_id
        entry.notes = notes
        entry.is_manual = True
        self.db.commit()
        return []

    def validate_assignment(self, school_id: int, timetable_id: int, section_id: int, day: str, period_number: int, subject_id: int | None, teacher_id: int | None) -> list[Conflict]:
        conflicts: list[Conflict] = []
        period = self.db.scalar(select(PeriodDefinition).where(PeriodDefinition.school_id == school_id, PeriodDefinition.period_number == period_number))
        if period and period.is_break and subject_id:
            conflicts.append(Conflict(code="break_period", message="Cannot assign a subject during a break period"))
        if teacher_id and subject_id:
            mapping = self.db.scalar(select(TeacherSubjectClassMap).where(TeacherSubjectClassMap.school_id == school_id, TeacherSubjectClassMap.section_id == section_id, TeacherSubjectClassMap.subject_id == subject_id, TeacherSubjectClassMap.teacher_id == teacher_id))
            if not mapping:
                conflicts.append(Conflict(code="invalid_mapping", message="Teacher is not eligible for this class/subject"))
            if not self._teacher_available(school_id, teacher_id, day, period_number):
                conflicts.append(Conflict(code="teacher_unavailable", message="Teacher is unavailable in this slot"))
            busy = self.db.scalar(select(TimetableEntry).where(TimetableEntry.school_id == school_id, TimetableEntry.timetable_id == timetable_id, TimetableEntry.teacher_id == teacher_id, TimetableEntry.day == day, TimetableEntry.period_number == period_number, TimetableEntry.section_id != section_id))
            if busy:
                conflicts.append(Conflict(code="teacher_double_booked", message="Teacher is already assigned in this slot"))
        return conflicts

    def _preflight(self, school_id: int, sections: list[Section], days: list[str], periods: list[PeriodDefinition]) -> list[Conflict]:
        conflicts: list[Conflict] = []
        teachable_periods = len([p for p in periods if not p.is_break]) * len(days)
        for section in sections:
            required_total = sum(r.periods_per_week for r in self.db.scalars(select(ClassSubjectRequirement).where(ClassSubjectRequirement.school_id == school_id, ClassSubjectRequirement.section_id == section.id)).all())
            if required_total > teachable_periods:
                conflicts.append(Conflict(code="class_over_capacity", message=f"{section.display_name} needs {required_total} periods but only {teachable_periods} are available", context={"section_id": section.id}))
        return conflicts

    def _pick_assignment(self, school_id: int, section_id: int, required: list[int], day: str, period_number: int, previous_subject_id: int | None, teacher_busy: set[tuple[int, str, int]], teacher_day_load: dict[tuple[int, str], int], constraints: list[SchedulingConstraint]) -> Assignment | None:
        candidates = self._candidate_assignments(school_id, section_id, required, day, period_number, previous_subject_id, teacher_busy, teacher_day_load, constraints, enforce_consecutive=True)
        if not candidates:
            candidates = self._candidate_assignments(school_id, section_id, required, day, period_number, previous_subject_id, teacher_busy, teacher_day_load, constraints, enforce_consecutive=False)
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1] if candidates else None

    def _candidate_assignments(self, school_id: int, section_id: int, required: list[int], day: str, period_number: int, previous_subject_id: int | None, teacher_busy: set[tuple[int, str, int]], teacher_day_load: dict[tuple[int, str], int], constraints: list[SchedulingConstraint], enforce_consecutive: bool) -> list[tuple[int, Assignment]]:
        candidates: list[tuple[int, Assignment]] = []
        for subject_id in sorted(set(required), key=lambda sid: required.count(sid), reverse=True):
            req = self.db.scalar(select(ClassSubjectRequirement).where(ClassSubjectRequirement.section_id == section_id, ClassSubjectRequirement.subject_id == subject_id))
            if enforce_consecutive and req and req.avoid_consecutive and previous_subject_id == subject_id:
                continue
            mappings = self.db.scalars(select(TeacherSubjectClassMap).where(TeacherSubjectClassMap.school_id == school_id, TeacherSubjectClassMap.section_id == section_id, TeacherSubjectClassMap.subject_id == subject_id)).all()
            for mapping in mappings:
                if (mapping.teacher_id, day, period_number) in teacher_busy:
                    continue
                teacher = self.db.get(Teacher, mapping.teacher_id)
                if teacher_day_load.get((mapping.teacher_id, day), 0) >= teacher.max_periods_per_day:
                    continue
                if not self._teacher_available(school_id, mapping.teacher_id, day, period_number):
                    continue
                score = self._score(req, subject_id, period_number, teacher_day_load.get((mapping.teacher_id, day), 0), constraints)
                if not enforce_consecutive and previous_subject_id == subject_id:
                    score -= 30
                candidates.append((score, Assignment(section_id, subject_id, mapping.teacher_id)))
        return candidates

    def _score(self, req: ClassSubjectRequirement | None, subject_id: int, period_number: int, teacher_load: int, constraints: list[SchedulingConstraint]) -> int:
        score = 100 - teacher_load * 5
        if req and req.preferred_first_half and period_number <= 4:
            score += 25
        if req and req.preferred_last_period and period_number >= 7:
            score += 20
        for constraint in constraints:
            values = json.loads(constraint.target_values or "[]")
            if str(subject_id) in values and constraint.rule_type == "subject_first_half" and period_number <= 4:
                score += 20
        return score

    def _expanded_requirements(self, school_id: int, section_id: int) -> list[int]:
        result: list[int] = []
        for req in self.db.scalars(select(ClassSubjectRequirement).where(ClassSubjectRequirement.school_id == school_id, ClassSubjectRequirement.section_id == section_id)).all():
            result.extend([req.subject_id] * req.periods_per_week)
        return result

    def _teacher_available(self, school_id: int, teacher_id: int, day: str, period_number: int) -> bool:
        availability = self.db.scalar(select(TeacherAvailability).where(TeacherAvailability.school_id == school_id, TeacherAvailability.teacher_id == teacher_id, TeacherAvailability.day == day, TeacherAvailability.period_number == period_number))
        return True if availability is None else availability.is_available

    def _entry(self, timetable: Timetable, section_id: int, day: str, period: int, subject_id: int | None, teacher_id: int | None, notes: str = "") -> None:
        self.db.add(TimetableEntry(school_id=timetable.school_id, timetable_id=timetable.id, section_id=section_id, day=day, period_number=period, subject_id=subject_id, teacher_id=teacher_id, notes=notes))

    def _days(self, school_id: int) -> list[str]:
        return [d.day for d in self.db.scalars(select(SchoolWorkingDay).where(SchoolWorkingDay.school_id == school_id).order_by(SchoolWorkingDay.sort_order)).all()]

    def _periods(self, school_id: int) -> list[PeriodDefinition]:
        return self.db.scalars(select(PeriodDefinition).where(PeriodDefinition.school_id == school_id).order_by(PeriodDefinition.period_number)).all()

    def _active_year_id(self, school_id: int) -> int | None:
        year = self.db.scalar(select(AcademicYear).where(AcademicYear.school_id == school_id, AcademicYear.is_active.is_(True)))
        return year.id if year else None

    def _active_constraints(self, school_id: int) -> list[SchedulingConstraint]:
        return self.db.scalars(select(SchedulingConstraint).where(SchedulingConstraint.school_id == school_id, SchedulingConstraint.is_active.is_(True))).all()
