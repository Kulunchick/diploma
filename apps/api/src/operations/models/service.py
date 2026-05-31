import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class ServiceUpdate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    group_ids: list[uuid.UUID] = []
    created_at: datetime
    updated_at: datetime
