from pydantic import BaseModel, Field


class AntColonyParameters(BaseModel):
    Kmax: int = 500
    num_ants: int = 20
    alpha: float = 1.0
    beta: float = 2.0
    p: float = 0.1
    tau: float = 1.0


class ProbabilisticParameters(BaseModel):
    Kmax: int = 1000


class CombinedParameters(BaseModel):
    """Parameters for the combined method (article §4–5)."""
    kmax_subproblem: int = Field(default=100, ge=1)
    discount_step: float = Field(default=0.05, gt=0, le=0.5)
    ignore_discounts: bool = False
    local_search_restarts: int = Field(default=0, ge=0)


class AlgorithmParameters(BaseModel):
    ant_colony: AntColonyParameters = AntColonyParameters()
    probabilistic: ProbabilisticParameters = ProbabilisticParameters()
    combined: CombinedParameters = CombinedParameters()