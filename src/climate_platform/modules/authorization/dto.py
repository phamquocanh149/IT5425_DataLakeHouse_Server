"""Authorization DTOs."""

from pydantic import BaseModel, ConfigDict


class GrantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actions: list[str]
