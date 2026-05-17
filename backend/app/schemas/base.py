"""Shared schema base classes.

Use ``StrictRequestModel`` as the base for every input schema (request body,
query/path parameter group) so unknown fields are rejected at the boundary
with a 422 instead of silently ignored. This prevents typo bugs ("emial")
from passing validation and protects against mass-assignment if a request
DTO is ever passed straight into an ORM constructor.
"""

from pydantic import BaseModel, ConfigDict


class StrictRequestModel(BaseModel):
    """Base for request payloads — extra fields rejected with 422."""

    model_config = ConfigDict(extra="forbid")
