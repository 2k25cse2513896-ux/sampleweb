"""Shared response wrappers."""

from typing import Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class LoginIn(BaseModel):
    email: str
    password: str


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


class MessageOut(BaseModel):
    message: str


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
