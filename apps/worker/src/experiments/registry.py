from pydantic import BaseModel

from experiments.base import ExperimentSpec
from experiments.experiment1 import Experiment1Spec
from experiments.experiment2 import Experiment2Spec
from experiments.experiment3 import Experiment3Spec
from experiments.experiment4 import Experiment4Spec
from worker.types import ProbabilisticParams, RunAlgorithmInput, RunResult


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


EXPERIMENT_REGISTRY: dict[str, type[ExperimentSpec]] = {
    "noop": NoopSpec,  # type: ignore[dict-item]
    "experiment1": Experiment1Spec,  # type: ignore[dict-item]
    "experiment2": Experiment2Spec,  # type: ignore[dict-item]
    "experiment3": Experiment3Spec,  # type: ignore[dict-item]
    "experiment4": Experiment4Spec,  # type: ignore[dict-item]
}
