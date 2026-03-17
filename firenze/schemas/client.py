from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


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
    full_name: Optional[str] = None
