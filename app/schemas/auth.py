from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Registration ──────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="At least 8 characters")
    full_name: Optional[str] = Field(None, max_length=256)


# ── Login ─────────────────────────────────────────────────────────────────────

class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ── Responses ─────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds until access_token expires


class RefreshRequest(BaseModel):
    refresh_token: str


# ── JWT Payload ───────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str                 # user email
    user_id: str             # user UUID as string
    type: str                # "access" | "refresh"
    exp: Optional[int] = None
