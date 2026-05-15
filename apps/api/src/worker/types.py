from typing import Optional
from pydantic import BaseModel


class AntColonyParams(BaseModel):
    num_ants: int = 20
    kmax: int = 100
    alpha: float = 1.0
    beta: float = 2.0
    rho: float = 0.1
    initial_pheromone: float = 1.0


class ProbabilisticParams(BaseModel):
    kmax: int = 100


class RunAlgorithmInput(BaseModel):
    # Task data (JSON-serializable)
    m: int
    n: int
    c: list[list[float]]
    b_ij: list[list[float]]
    b_total: int
    omega: list[list[float]]
    # Which algorithm to run
    algorithm: str  # "ant_colony" | "probabilistic"
    ant_colony_params: Optional[AntColonyParams] = None
    probabilistic_params: Optional[ProbabilisticParams] = None
    # Aggregation metadata — passed through to RunResult unchanged
    variant_key: str
    # Redis pub/sub channel for iteration streaming (solve only, None for experiments)
    redis_channel: Optional[str] = None


class RunResult(BaseModel):
    variant_key: str
    algorithm: str  # "ant_colony" | "probabilistic"
    value: float
    time_seconds: float
    solution: list[list[int]]


class GenerateRunsInput(BaseModel):
    experiment_type: str
    params: dict  # raw JSON, validated by the spec's input_model inside the activity


class AlgorithmResult(BaseModel):
    solution: list[list[int]]
    value: float


class SolveInput(BaseModel):
    m: int
    n: int
    c: list[list[int]]
    b_ij: list[list[int]]
    b_total: int
    omega: list[list[float]]
    ant_colony: AntColonyParams = AntColonyParams()
    probabilistic: ProbabilisticParams = ProbabilisticParams()
    redis_channel: str  # channel for publishing per-iteration events


class SolveResult(BaseModel):
    ant_colony: AlgorithmResult
    probabilistic: AlgorithmResult


class ExperimentInput(BaseModel):
    experiment_type: str
    params: dict  # spec-specific input, validated inside the workflow/activity
    concurrency: int = 1  # max parallel activities; default 1 (Rayon already uses all cores)


class ExperimentResult(BaseModel):
    data: dict  # spec-specific aggregated result; shape defined by each ExperimentSpec
