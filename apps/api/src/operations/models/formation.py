import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- request -------------------------------------------------------------

class FormationCreate(BaseModel):
    name: str = Field(min_length=1)
    b_total: float = Field(gt=0)
    algorithm: Literal["probabilistic", "ant_colony"]
    # Validated against AntColonyParameters / ProbabilisticParameters in the
    # router depending on `algorithm`; stored verbatim in JSONB.
    params: dict = {}


class CompareRequest(BaseModel):
    scenario_ids: list[uuid.UUID]


# --- read ----------------------------------------------------------------

class FormationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    algorithm: str
    status: str
    value: float | None = None
    created_at: datetime


class FormationAssignmentRead(BaseModel):
    service_id: uuid.UUID
    service_name: str
    provider_id: uuid.UUID
    provider_name: str
    price: float
    discount: float
    effective_revenue: float
    resource_used: float
    # Set when the service was assigned as part of a group (all-or-nothing unit).
    group_name: str | None = None


class FormationTotals(BaseModel):
    total_revenue: float
    total_resource_used: float
    provider_count: int
    service_count: int


class FormationDetail(BaseModel):
    id: uuid.UUID
    name: str
    algorithm: str
    status: str
    value: float | None = None
    b_total: float
    params: dict
    workflow_id: str | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    assignments: list[FormationAssignmentRead] = []
    totals: FormationTotals


class CompareProviderBreakdown(BaseModel):
    provider_id: uuid.UUID
    provider_name: str
    assignment_count: int
    services: list[str]


class CompareScenario(BaseModel):
    id: uuid.UUID
    name: str
    algorithm: str
    status: str
    value: float | None = None
    b_total: float
    params: dict
    total_revenue: float
    total_resource_used: float
    per_provider: list[CompareProviderBreakdown]


class CompareResponse(BaseModel):
    scenarios: list[CompareScenario]


class FormationIterationRead(BaseModel):
    iteration: int
    best_value: float
