from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    school_name: str
    full_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    school_id: int
    user_id: int
    school_name: str


class UserProfile(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    school_id: int
    school_name: str
