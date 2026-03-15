from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PhoneModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clientid: int
    ani: int


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


class ConnectedOperators(BaseModel):
    nombre: str
    opcion: int
    ingreso: bool
    disponible: bool
    descripcion: str
