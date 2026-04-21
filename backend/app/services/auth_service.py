from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models import School, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, payload: RegisterRequest) -> TokenResponse:
        existing_user = self.db.scalar(select(User).where(User.email == payload.email.lower()))
        if existing_user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        school = self.db.scalar(select(School).where(School.name == payload.school_name.strip()))
        if not school:
            school = School(name=payload.school_name.strip())
            self.db.add(school)
            self.db.flush()

        user = User(
            school_id=school.id,
            email=payload.email.lower(),
            full_name=payload.full_name.strip(),
            password_hash=hash_password(payload.password),
        )
        self.db.add(user)
        self.db.flush()
        AuditService(self.db).record("school_registered", user=user, entity_type="school", entity_id=school.id, detail={"school_name": school.name})
        self.db.commit()
        self.db.refresh(user)
        return self._token(user, school)

    def login(self, payload: LoginRequest) -> TokenResponse:
        user = self.db.scalar(select(User).where(User.email == payload.email.lower()))
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        school = self.db.get(School, user.school_id)
        if not school:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="School not found")
        AuditService(self.db).record("user_logged_in", user=user, entity_type="user", entity_id=user.id)
        self.db.commit()
        return self._token(user, school)

    def _token(self, user: User, school: School) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            user_id=user.id,
            school_id=school.id,
            school_name=school.name,
            role=user.role,
        )
