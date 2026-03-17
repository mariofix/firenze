import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    login: str
    email: str


class UserCreate(UserBase):
    password: str
    scopes: Optional[List[str]] = None
    allowed_ips: Optional[List[str]] = []


class User(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    modified_at: datetime.datetime
    allowed_ips: Optional[List[str]] = []
    enabled: bool
    scopes: Optional[List[str]] = None
