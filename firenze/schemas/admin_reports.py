"""Schemas for admin report actions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SystemStatusClientCreditRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    service_slug: str = Field(..., min_length=1)
    client_id: int = Field(..., gt=0)
    credits_to_add: int = Field(..., gt=0)


class SystemStatusClientCreditResponse(BaseModel):
    ok: bool
    saved: bool
    service_slug: str
    client_id: int
    email: str | None = None
    current_credits: int
    credits_to_add: int
    new_credits: int
