"""
API-local copies of Temporal workflow payload types and experiment input models.

These mirror the definitions in apps/worker/src/worker/types.py and
apps/worker/src/experiments/experiment*.py.  Both sides must stay structurally
identical for Temporal's pydantic_data_converter to serialise/deserialise
correctly.  Neither project imports from the other at runtime.
"""
import os
from typing import List, Optional
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Shared range (mirrors experiments.base.Range)
# ---------------------------------------------------------------------------

class Range(BaseModel):
    min: float
    max: float

# ---------------------------------------------------------------------------
# Algorithm parameter models (mirror worker.types)
# ---------------------------------------------------------------------------

class AntColonyParams(BaseModel):
    num_ants: int = 20
    kmax: int = 100
    alpha: float = 1.0
    beta: float = 2.0
    rho: float = 0.1
    initial_pheromone: float = 1.0


class ProbabilisticParams(BaseModel):
    kmax: int = 100

# ---------------------------------------------------------------------------
# Workflow payload models (mirror worker.types)
# ---------------------------------------------------------------------------

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
# Experiment POST-endpoint input models (mirror experiments/experiment*.py)
# Used for FastAPI request validation only; passed as params dict to workflow.
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

# ---------------------------------------------------------------------------
# Temporal / infra config (mirrors worker.config env vars)
# ---------------------------------------------------------------------------

TEMPORAL_HOST      = os.getenv("TEMPORAL_HOST",      "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE",  "default")
TASK_QUEUE         = os.getenv("TASK_QUEUE",           "coursework-operations")
REDIS_URL          = os.getenv("REDIS_URL",            "redis://localhost:6379")

# Workflow class names as registered with @workflow.defn in apps/worker.
# Using strings avoids importing the workflow classes into the api package.
SOLVE_WORKFLOW_NAME      = "SolveWorkflow"
EXPERIMENT_WORKFLOW_NAME = "ExperimentWorkflow"
