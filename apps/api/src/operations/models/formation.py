import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- request -------------------------------------------------------------

class FormationCreate(BaseModel):
    name: str = Field(min_length=1)
    b_total: float = Field(gt=0)
    algorithm: Literal["probabilistic", "ant_colony", "combined"]
    # Validated against AntColony/Probabilistic/CombinedParameters in the router
    # depending on `algorithm`; stored verbatim in JSONB.
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
    # The discount actually applied (negotiated for combined; = discount else).
    final_discount: float | None = None
    # Per-pair provider metrics — the summands of the scenario-level
    # provider_value / provider_profit (so the table columns sum to the cards).
    # provider_revenue_pair = (1 − r)·p_ij ; provider_profit_pair = p_ij − (1 − r)·price.
    # None when the snapshot lacks per-pair provider_revenue (legacy scenarios).
    provider_revenue_pair: float | None = None
    provider_profit_pair: float | None = None


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
    # Provider revenue (gross) and profit (net of what the provider pays the
    # IT-company) — populated for all algorithms. created_value = value +
    # provider_profit is the discount-invariant total value created.
    provider_value: float | None = None
    provider_profit: float | None = None
    created_value: float | None = None
    # Combined-method only: winning candidate + value + provider_value.
    combined_source: str | None = None
    combined_benefit: float | None = None
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
    provider_value: float | None = None
    provider_profit: float | None = None
    created_value: float | None = None
    combined_benefit: float | None = None
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
