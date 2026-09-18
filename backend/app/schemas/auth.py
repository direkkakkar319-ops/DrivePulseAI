"""Authentication request and response contracts, mirrored in TypeScript."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class Registration(Credentials):
    password: str = Field(min_length=12, max_length=128)


class GoogleCredentials(BaseModel):
    id_token: str = Field(min_length=1, max_length=10000)


class AuthUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: int
    user: AuthUser
