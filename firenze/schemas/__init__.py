"""Re-export all schemas so existing imports continue to work unchanged."""

from firenze.schemas.common import Message
from firenze.schemas.auth import (
    PasswordlessRequest,
    PasswordlessRequestResponse,
)
from firenze.schemas.client import (
    ClientCreateRequest,
    ClientDeleteResponse,
    ClientResponse,
    ClientUpdateRequest,
)
from firenze.schemas.user import User, UserBase, UserCreate

__all__ = [
    "Message",
    "PasswordlessRequest",
    "PasswordlessRequestResponse",
    "ClientCreateRequest",
    "ClientUpdateRequest",
    "ClientResponse",
    "ClientDeleteResponse",
    "UserBase",
    "UserCreate",
    "User",
]
