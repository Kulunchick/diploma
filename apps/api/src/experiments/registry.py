from pydantic import BaseModel

from src.experiments.base import ExperimentSpec
from src.worker.types import ProbabilisticParams, RunAlgorithmInput, RunResult


# ---------------------------------------------------------------------------
# "noop" spec — used for integration testing in step 5.
# Returns count stub runs (probabilistic, tiny task), aggregate counts runs.
# Remove or keep alongside real specs after step 6 validation.
# ---------------------------------------------------------------------------

class _NoopInput(BaseModel):
    count: int = 3


class _NoopResult(BaseModel):
    total_runs: int


class NoopSpec:
    name = "noop"
    input_model = _NoopInput
    result_model = _NoopResult

    @staticmethod
    def format_variant_key(variant) -> str:
        return str(variant)

    @staticmethod
    def generate_runs(input: _NoopInput) -> list[RunAlgorithmInput]:
        return [
            RunAlgorithmInput(
                m=2, n=2,
                c=[[10, 20], [5, 25]],
                b_ij=[[3, 4], [1, 5]],
                b_total=6,
                omega=[[0.1, 0.2], [0.0, 0.1]],
                algorithm="probabilistic",
                probabilistic_params=ProbabilisticParams(kmax=5),
                variant_key=str(i),
            )
            for i in range(input.count)
        ]

    @staticmethod
    def aggregate(
        results: list[RunResult],
        runs: list[RunAlgorithmInput],
        input: _NoopInput,
    ) -> _NoopResult:
        return _NoopResult(total_runs=len(results))


# ---------------------------------------------------------------------------
# Registry — populated here; step 6 adds Experiment1..4 specs.
# ---------------------------------------------------------------------------

EXPERIMENT_REGISTRY: dict[str, type[ExperimentSpec]] = {
    "noop": NoopSpec,  # type: ignore[dict-item]
}
