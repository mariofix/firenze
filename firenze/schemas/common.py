from typing import Optional

from pydantic import BaseModel


class Message(BaseModel):
    detail: Optional[str] = None
    message: Optional[str] = None
