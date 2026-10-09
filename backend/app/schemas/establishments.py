from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EstablishmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    ss_code: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class EstablishmentPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: Literal["OPEN", "CLOSED"] | None = None


class EstablishmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    ss_code: str
    status: str
    created_at: datetime
