import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceGroupCreate(BaseModel):
    name: str = Field(min_length=1)
    member_ids: list[uuid.UUID] = []


class ServiceGroupUpdate(BaseModel):
    name: str = Field(min_length=1)
    # Full replacement of the membership set.
    member_ids: list[uuid.UUID] = []


class ServiceGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    members: list[uuid.UUID] = []
    created_at: datetime
    updated_at: datetime
