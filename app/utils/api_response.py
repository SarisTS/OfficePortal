from typing import Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    status  : int
    message : str
    data    : T

class PaginatedResponse(BaseModel, Generic[T]):
    skip  : int
    limit : int
    total : int
    items : List[T]

class ErrorResponse(BaseModel):
    status  : str = "error"
    code    : int
    message : str
