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


class SingleSolveInput(BaseModel):
    """Input for SingleAlgorithmWorkflow — runs exactly one algorithm and
    persists the result back to Postgres for a formation scenario.

    Mirrors SolveInput but selects a single algorithm and carries the
    scenario_id so the worker can write assignments/value back to the DB.
    """
    m: int
    n: int
    c: list[list[int]]
    b_ij: list[list[int]]
    b_total: int
    omega: list[list[float]]
    algorithm: str  # "ant_colony" | "probabilistic"
    ant_colony: AntColonyParams = AntColonyParams()
    probabilistic: ProbabilisticParams = ProbabilisticParams()
    scenario_id: str
    redis_channel: str | None = None


class CombinedParams(BaseModel):
    """Solver parameters for the combined method (article §4–5)."""
    kmax_subproblem: int = 100
    discount_step: float = 0.05
    local_search_restarts: int = 0


class CombinedSolveInput(BaseModel):
    """Input for CombinedFormationWorkflow — runs the combined method on the
    aggregated (unit × provider) matrices and persists F_IT, F_prov, the
    negotiated discounts and the expanded assignments for a scenario.

    omega_max is the per-pair upper discount bound (planning r, or all-0.95 when
    ignore_discounts was chosen on the API side); s_ij are constraint-(4)
    thresholds. p_ij is provider revenue.
    """
    m: int
    n: int
    c: list[list[int]]
    b_ij: list[list[int]]
    p_ij: list[list[int]]
    omega_max: list[list[float]]
    s_ij: list[list[float]]
    b_total: int
    params: CombinedParams = CombinedParams()
    scenario_id: str
    redis_channel: str | None = None


class CombinedResult(BaseModel):
    """Result of the combined method, returned by run_combined_method_activity."""
    v_final: list[list[int]]
    r_final: list[list[float]]
    f_it: float
    f_prov: float
    source: str  # "subtask_a_improved" | "subtask_b_improved"


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
