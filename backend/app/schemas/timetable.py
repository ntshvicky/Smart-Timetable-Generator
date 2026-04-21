from pydantic import BaseModel, Field


class ConstraintPayload(BaseModel):
    rule_type: str
    target_type: str
    target_values: list[str] = Field(default_factory=list)
    day_scope: list[str] = Field(default_factory=list)
    period_scope: list[int] = Field(default_factory=list)
    priority: str = "hard"
    parsed_description: str = ""
    confidence_score: float = 1.0


class ParseInstructionRequest(BaseModel):
    text: str


class ParseInstructionResponse(BaseModel):
    constraints: list[ConstraintPayload]
    provider: str


class GenerateRequest(BaseModel):
    name: str = "Generated Timetable"
    constraint_ids: list[int] = Field(default_factory=list)


class Conflict(BaseModel):
    code: str
    message: str
    context: dict = Field(default_factory=dict)


class TimetableCell(BaseModel):
    id: int | None = None
    day: str
    period_number: int
    section_id: int
    subject_id: int | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    teacher_id: int | None = None
    teacher_code: str | None = None
    teacher_name: str | None = None
    is_break: bool = False
    is_manual: bool = False
    notes: str = ""


class TimetableResponse(BaseModel):
    timetable_id: int
    name: str
    status: str
    days: list[str]
    periods: list[int]
    entries: list[TimetableCell]
    conflicts: list[Conflict] = Field(default_factory=list)


class ManualEditRequest(BaseModel):
    section_id: int
    day: str
    period_number: int
    subject_id: int | None
    teacher_id: int | None
    notes: str = ""


class MasterSummary(BaseModel):
    classes: int
    sections: int
    subjects: int
    teachers: int
    mappings: int
    requirements: int
    working_days: int
    periods: int
