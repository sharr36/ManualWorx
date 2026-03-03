"""User and auth request/response models."""

from pydantic import BaseModel, EmailStr

from manualworx_shared.constants import SkillLevel, TenantType


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    tenant_name: str
    tenant_type: TenantType = TenantType.INDIVIDUAL


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
