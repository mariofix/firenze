from firenze.database import Base
from pydantic import BaseModel
from pydantic.utils import GetterDict
import peewee
from typing import List, Any, Optional


class PeeweeGetterDict(GetterDict):
    def get(self, key: Any, default: Any = None):
        res = getattr(self._obj, key, default)
        if isinstance(res, peewee.ModelSelect):
            return list(res)
        return res


class PhoneModel(BaseModel):
    clientid: int
    ani: int

    class Config:
        orm_mode = True
        getter_dict = PeeweeGetterDict


class ClientId(BaseModel):
    clientid: Optional[int] = 0
    creditos: int = 0
    telefonos: List[str] = []
    correo: str = None


class Credits(BaseModel):
    clientid: Optional[int] = 0
    creditos: int = 0


class ClientIdLatam(BaseModel):
    clientid: int = 0
    pin: Optional[int] = None
    creditos: int = 0
    correo: str = None
    telefonos: Optional[List[str]] = []
