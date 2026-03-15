import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    login: str
    email: str


class UserCreate(UserBase):
    password: str
    scopes: List[str] = None
    allowed_ips: Optional[List[str]] = []


class User(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    modified_at: datetime.datetime
    allowed_ips: Optional[List[str]] = []
    enabled: bool
    scopes: List[str] = None


class Event(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ip: str
    port: Optional[int] = 0
    verb: str
    url: str
    data: str
    created_at: datetime.datetime
    modified_at: datetime.datetime


class Message(BaseModel):
    detail: Optional[str]
    message: Optional[str]


class NewFonotarotLatam(BaseModel):
    email: EmailStr
    phone_number: Optional[str] = None
    credits: Optional[int] = 0


class UpdateFonotarotLatam(BaseModel):
    credits: int


class FonoTarotLatam(NewFonotarotLatam):
    model_config = ConfigDict(from_attributes=True)

    pin_code: int
    client_id: int
    full_name: Optional[str]
