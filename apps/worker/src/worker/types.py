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
    redis_channel: str


class SolveResult(BaseModel):
    ant_colony: AlgorithmResult
    probabilistic: AlgorithmResult


class ExperimentInput(BaseModel):
    experiment_type: str
    params: dict
    concurrency: int = 1


class ExperimentResult(BaseModel):
    data: dict
