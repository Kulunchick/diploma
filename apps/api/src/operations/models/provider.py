import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class ProviderUpdate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class ProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
