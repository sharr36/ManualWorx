"""User and auth request/response models."""

import re

from pydantic import BaseModel, EmailStr, field_validator

from manualworx_shared.constants import SkillLevel, TenantType


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    tenant_name: str
    tenant_type: TenantType = TenantType.INDIVIDUAL

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserInviteRequest(BaseModel):
    email: EmailStr
    name: str
    role: str = "technician"


class UserUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    skill_level: SkillLevel | None = None


class AuthResponse(BaseModel):
    token: str
    user: dict
    tenant: dict
