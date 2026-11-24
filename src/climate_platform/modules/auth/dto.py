"""Auth DTOs."""

from pydantic import BaseModel, ConfigDict, Field


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(max_length=64)
    # Public login is unauthenticated: bound the password so an oversized body cannot force
    # an unbounded PBKDF2 computation (the create/reset endpoints use the same 256 bound).
    password: str = Field(max_length=256)


class UserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    enabled: bool
