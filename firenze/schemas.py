import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, EmailStr, Json


class UserBase(BaseModel):
    login: str
    email: str


class UserCreate(UserBase):
    password: str
    scopes: List[str] = None
    allowed_ips: Optional[List[str]] = []


class User(UserBase):
    id: int
    created_at: datetime.datetime
    modified_at: datetime.datetime
    allowed_ips: Optional[List[str]] = []
    enabled: bool
    scopes: List[str] = None

    class Config:
        orm_mode = True


class Event(BaseModel):
    id: int
    name: str
    ip: str
    port: Optional[int] = 0
    verb: str
    url: str
    data: str
    created_at: datetime.datetime
    modified_at: datetime.datetime

    class Config:
        orm_mode = True


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
    pin_code: int
    client_id: int
    full_name: Optional[str]

    class Config:
        orm_mode = True
