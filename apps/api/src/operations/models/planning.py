import uuid

from pydantic import BaseModel, ConfigDict, Field


class PlanningCellUpsert(BaseModel):
    """One (service, provider) planning cell.

    price = preferential price d_ij, resource = IT-company resource β_ij,
    provider_revenue = provider expected revenue p_ij, discount = r_ij.
    """

    service_id: uuid.UUID
    provider_id: uuid.UUID
    price: float = Field(default=0, ge=0)
    resource: float = Field(default=0, ge=0)
    provider_revenue: float = Field(default=0, ge=0)
    discount: float = Field(default=0, ge=0, lt=1)


class PlanningBulkUpsert(BaseModel):
    cells: list[PlanningCellUpsert]


class PlanningCellRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    provider_id: uuid.UUID
    price: float
    resource: float
    provider_revenue: float
    discount: float
