"""Portal DTOs."""

from pydantic import BaseModel, ConfigDict, Field


class SelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    week: str
    release_id: str
    mode: str = "current"
    version_id: str | None = None


class CreateUserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    role: str
    password: str = Field(min_length=8, max_length=256)


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=8, max_length=256)
