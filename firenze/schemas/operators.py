from pydantic import BaseModel


class ConnectedOperators(BaseModel):
    nombre: str
    opcion: int
    ingreso: bool
    disponible: bool
    descripcion: str | None
