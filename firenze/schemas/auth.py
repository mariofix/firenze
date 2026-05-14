from pydantic import BaseModel, Field


class PasswordlessRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)


class PasswordlessVerify(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=4, max_length=16)


class PasswordlessRequestResponse(BaseModel):
    ok: bool = True
    detail: str
