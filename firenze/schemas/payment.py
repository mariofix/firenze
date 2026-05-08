"""Schemas for the payment API consumed by nuevo-fonotarot.

Two flows: search for an existing client (returns ``client_id``) and apply a
completed purchase (creates the client when ``client_id`` is absent, otherwise
tops up).
"""

from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

PHONE_ERASE_SENTINEL = "::EMPTY::"


class ClientSearchResponse(BaseModel):
    """Result of ``GET /api/v1/clients/search``.

    ``found=False`` returns just that flag; the rest of the fields are only
    populated on a hit so the caller can verify it found the right person.
    """

    found: bool
    client_id: Optional[int] = None
    service: Optional[str] = None
    credits: Optional[int] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None


class PurchaseRequest(BaseModel):
    """Body of ``POST /api/v1/payments/complete``.

    ``client_id`` absent -> create a new ``Client`` row. ``email`` is required
    in that case so the new record is contactable. When ``client_id`` is set
    the other profile fields are ignored (the payment system is not authoritative
    on the customer profile - only on the credit balance).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    service: str = Field(
        ..., min_length=1, description="Service slug, e.g. fonotarot-cl"
    )
    credits: int = Field(
        ..., gt=0, description="Seconds of airtime to add to the balance"
    )
    client_id: Optional[int] = Field(
        default=None, description="Existing client_id; omit to create"
    )
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=128)
    phone_number: Optional[str] = Field(default=None, max_length=16)
    ani: Optional[str] = Field(
        default=None,
        max_length=16,
        description="Caller-ID to register against the client",
    )
    transaction_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Payment-system reference, logged for traceability",
    )

    @model_validator(mode="after")
    def _require_email_when_creating(self) -> "PurchaseRequest":
        if self.client_id is None and not self.email:
            raise ValueError(
                "email is required when client_id is omitted (creating a new client)"
            )
        return self


class PurchaseResponse(BaseModel):
    ok: bool
    client_id: int
    service: str
    created: bool
    credits_before: int
    credits_added: int
    credits_after: int


class ClientUpdateRequest(BaseModel):
    """Body of ``PATCH /api/v1/clients/{service}/{client_id}``.

    All fields optional. ``phone`` accepts either a normal phone string
    (added to ``ClientAni`` if not already on this client) or the literal
    sentinel ``::EMPTY::`` (deletes every ``ClientAni`` row for the client).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: Optional[str] = Field(default=None, max_length=128)
    email: Optional[EmailStr] = None
    pin: Optional[str] = Field(default=None, min_length=8, max_length=8)
    phone: Optional[str] = Field(default=None, max_length=16)

    @field_validator("pin")
    @classmethod
    def _pin_must_be_digits(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.isdigit():
            raise ValueError("pin must be 8 digits")
        return v

    @field_validator("phone")
    @classmethod
    def _phone_must_be_sentinel_or_digits(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == PHONE_ERASE_SENTINEL:
            return v
        if not v.isdigit() or not (8 <= len(v) <= 15):
            raise ValueError(
                "phone must be 8-15 digits or the literal sentinel '::EMPTY::'"
            )
        return v

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "ClientUpdateRequest":
        if all(v is None for v in (self.full_name, self.email, self.pin, self.phone)):
            raise ValueError("at least one of full_name, email, pin, phone is required")
        return self


class ClientUpdateResponse(BaseModel):
    ok: bool
    client_id: int
    service: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    pin: Optional[str] = None
    phones: list[str] = []
    phones_added: int = 0
    phones_removed: int = 0
    phone_skipped_reason: Optional[str] = None


class ClientAniWriteRequest(BaseModel):
    """Body for ClientAni create/add endpoints."""

    model_config = ConfigDict(str_strip_whitespace=True)

    service: str = Field(
        ..., min_length=1, description="Service slug, e.g. fonotarot-cl"
    )
    client_id: int = Field(..., gt=0, description="Existing client_id in the service")
    ani: str = Field(..., min_length=8, max_length=15)

    @field_validator("ani")
    @classmethod
    def _ani_must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("ani must be 8-15 digits")
        return v


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
