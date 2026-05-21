"""Schemas for client CRUD endpoints."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictInt, field_validator


class ClientExtraConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tarotista_favorita: StrictInt | None = Field(default=None, gt=0)
    aviso_creditos: StrictInt | None = Field(default=None, ge=0)


class ClientCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    client_id: int | None = Field(default=None, gt=0)
    full_name: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None
    pin: str | None = Field(default=None, min_length=8, max_length=8)
    credits: int = Field(default=0, ge=0)
    extra_config: ClientExtraConfig | None = None

    @field_validator("pin")
    @classmethod
    def _pin_must_be_digits(cls, value: str | None) -> str | None:
        if value is not None and not value.isdigit():
            raise ValueError("pin must be 8 digits")
        return value


class ClientUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    full_name: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None
    pin: str | None = Field(default=None, min_length=8, max_length=8)
    credits: int | None = Field(default=None, ge=0)
    extra_config: ClientExtraConfig | None = None

    @field_validator("pin")
    @classmethod
    def _pin_must_be_digits(cls, value: str | None) -> str | None:
        if value is not None and not value.isdigit():
            raise ValueError("pin must be 8 digits")
        return value


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    client_id: int
    full_name: str | None = None
    email: EmailStr | None = None
    pin: str | None = None
    credits: int
    extra_config: ClientExtraConfig | None = None
    anis: list[str] = Field(default_factory=list)
    created_at: datetime.datetime
    modified_at: datetime.datetime


class ClientDeleteResponse(BaseModel):
    ok: bool
    service: str
    client_id: int
    deleted: bool


class ClientSearchResponse(BaseModel):
    found: bool
    client_id: int | None = None
    service: str | None = None
    credits: int | None = None
    email: str | None = None
    full_name: str | None = None
    phone_number: str | None = None


class ClientAniCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    ani: str = Field(..., min_length=8, max_length=15)

    @field_validator("ani")
    @classmethod
    def _ani_must_be_digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("ani must be 8-15 digits")
        return value


class ClientAniWriteResponse(BaseModel):
    ok: bool
    service: str
    client_id: int
    ani: str
    created: bool


class ClientAniListResponse(BaseModel):
    ok: bool
    service: str
    client_id: int
    anis: list[str]


class ClientAniDeleteResponse(BaseModel):
    ok: bool
    service: str
    client_id: int
    ani: str
    deleted: bool
