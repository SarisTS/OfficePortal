from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Envelope every successful endpoint returns.

    ``status`` is the HTTP status code as an integer (e.g. 200, 201).
    Failure responses are produced by main.py's exception handlers and
    follow a similar shape but with status=str-flag — see those handlers
    for the wire format.
    """
    status  : int
    message : str
    data    : Optional[T] = None


class PaginatedResponse(BaseModel, Generic[T]):
    skip  : int
    limit : int
    total : int
    items : List[T]
