from typing import List
from pydantic import BaseModel


class Range(BaseModel):
    min: float
    max: float


class AntColonyParams(BaseModel):
    num_ants: int = 20
    kmax: int = 100
    alpha: float = 1.0
    beta: float = 2.0
    rho: float = 0.1
    initial_pheromone: float = 1.0


class ProbabilisticParams(BaseModel):
    kmax: int = 100


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


# ---------------------------------------------------------------------------
# Experiment input models (used by both API validation and worker specs)
# ---------------------------------------------------------------------------

class KmaxVariant(BaseModel):
    kmax: int


class Experiment1Input(BaseModel):
    count: int
    n: int
    m: int
    kmaxVariants: List[KmaxVariant]
    l: int
    p: float
    tau: float
    alpha: float
    beta: float
    cRange: Range
    bRange: Range
    omegaRange: Range


class BetaVariant(BaseModel):
    beta: float


class Experiment2Input(BaseModel):
    count: int
    betaVariants: List[BetaVariant]
    p: float
    tau: float
    alpha: float
    antKmax: int
    m: int
    n: int
    l: int
    cRange: Range
    bRange: Range
    omegaRange: Range


class MNVariant(BaseModel):
    m: int
    n: int


class Experiment3Input(BaseModel):
    count: int
    mnVariants: List[MNVariant]
    p: float
    tau: float
    antKmax: int
    probKmax: int
    l: int
    cRange: Range
    bRange: Range
    omegaRange: Range


class Experiment4Input(BaseModel):
    count: int
    omegaRangeVariants: List[Range]
    p: float
    tau: float
    alpha: float
    beta: float
    m: int
    n: int
    antKmax: int
    probKmax: int
    l: int
    cRange: Range
    bRange: Range
