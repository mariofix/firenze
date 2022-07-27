from pydantic import BaseModel
from typing import Optional, Union, List

import datetime


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
