import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    login: str
    email: str


class UserCreate(UserBase):
    password: str
    scopes: list[str] | None = None
    allowed_ips: list[str] | None = Field(
        default_factory=list,
        description="Deprecated. No longer enforced by authentication.",
    )


class User(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    modified_at: datetime.datetime
    allowed_ips: list[str] | None = Field(
        default_factory=list,
        description="Deprecated. No longer enforced by authentication.",
    )
    enabled: bool
    scopes: list[str] | None = None
