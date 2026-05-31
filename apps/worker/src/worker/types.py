from typing import Optional
from pydantic import BaseModel

from shared.types import (  # noqa: F401 — re-exported for worker modules
    AntColonyParams,
    CombinedParams,
    CombinedResult,
    CombinedSolveInput,
    ProbabilisticParams,
    SingleSolveInput,
)


class RunAlgorithmInput(BaseModel):
    m: int
    n: int
    c: list[list[float]]
    b_ij: list[list[float]]
    b_total: int
    omega: list[list[float]]
    algorithm: str  # "ant_colony" | "probabilistic"
    ant_colony_params: Optional[AntColonyParams] = None
    probabilistic_params: Optional[ProbabilisticParams] = None
    variant_key: str
    redis_channel: Optional[str] = None


class RunResult(BaseModel):
    variant_key: str
    algorithm: str
    value: float
    time_seconds: float
    solution: list[list[int]]


class PersistFormationInput(BaseModel):
    """Workflow → activity payload for writing a formation result to Postgres.
    The solution matrix indexes into the scenario's frozen snapshot orders."""
    scenario_id: str
    solution: list[list[int]]
    value: float
    # Redis stream key holding the per-iteration convergence history (drained
    # into formation_iterations on persist). None → no history captured.
    redis_channel: str | None = None


class PersistCombinedInput(BaseModel):
    """Workflow → activity payload for writing a combined-method result.

    Expands the unit-level v_final into per-service assignments using r_final as
    the negotiated discount per pair. value = F_IT, provider_value = F_prov.
    """
    scenario_id: str
    v_final: list[list[int]]
    r_final: list[list[float]]
    f_it: float
    f_prov: float
    source: str
    redis_channel: str | None = None
