from datetime import datetime

from pydantic import BaseModel, EmailStr


class AdminStats(BaseModel):
    schools: int
    users: int
    uploads: int
    timetables: int
    manual_edits: int


class AdminSchool(BaseModel):
    id: int
    name: str
    created_at: datetime
    users: int
    uploads: int
    timetables: int


class AdminUser(BaseModel):
    id: int
    school_id: int
    school_name: str
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime


class AdminActivity(BaseModel):
    id: int
    school_id: int | None
    school_name: str | None
    user_id: int | None
    user_email: str | None
    action: str
    entity_type: str
    entity_id: str
    detail: str
    created_at: datetime


class AdminOverview(BaseModel):
    stats: AdminStats
    schools: list[AdminSchool]
    users: list[AdminUser]
    activity: list[AdminActivity]
