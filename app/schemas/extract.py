from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


class ExtractedPerson(BaseModel):
    name: str
    occupation: str | None = None
    country: str | None = None
