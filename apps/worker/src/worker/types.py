from typing import Optional
from pydantic import BaseModel

from shared.types import (  # noqa: F401 — re-exported for worker modules
    AntColonyParams,
    AlgorithmResult,
    ExperimentInput,
    ExperimentResult,
    ProbabilisticParams,
    SolveInput,
    SolveResult,
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


class GenerateRunsInput(BaseModel):
    experiment_type: str
    params: dict


class ExperimentVariantInput(BaseModel):
    """Reference to one variant stored in Redis by the generator activity."""
    index: int
