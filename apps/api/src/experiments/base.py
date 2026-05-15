from typing import Protocol
from pydantic import BaseModel

from src.worker.types import RunAlgorithmInput, RunResult


class ExperimentSpec(Protocol):
    name: str
    input_model: type[BaseModel]
    result_model: type[BaseModel]

    @staticmethod
    def format_variant_key(variant) -> str:
        """Single source of truth for variant → string key used in results dict."""
        ...

    @staticmethod
    def generate_runs(input: BaseModel) -> list[RunAlgorithmInput]:
        """Pure: no I/O, no time.time(), random is OK (called from activity)."""
        ...

    @staticmethod
    def aggregate(
        results: list[RunResult],
        runs: list[RunAlgorithmInput],
        input: BaseModel,
    ) -> BaseModel:
        """Pure: no I/O, no random, no time.time()."""
        ...
