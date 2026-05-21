from pydantic import BaseModel


class Message(BaseModel):
    detail: str | None = None
    message: str | None = None
