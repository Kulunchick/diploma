from collections import defaultdict
from typing import Protocol

from pydantic import BaseModel, RootModel

from src.worker.types import RunAlgorithmInput, RunResult


# ---------------------------------------------------------------------------
# Shared domain types used by all 4 experiment specs
# ---------------------------------------------------------------------------

class Range(BaseModel):
    min: float
    max: float


class AlgoStats(BaseModel):
    avg_value: float
    avg_time: float


class VariantStats(BaseModel):
    ant: AlgoStats
    prob: AlgoStats
    relative_difference: float


class ExperimentStatsResult(RootModel[dict[str, VariantStats]]):
    """
    Root model so that .model_dump() returns the flat {variant_key: stats} dict
    that matches the legacy {"type":"results","data":{...}} format.
    """


# ---------------------------------------------------------------------------
# Shared aggregation helper (pure — no I/O, no random)
# ---------------------------------------------------------------------------

def aggregate_to_stats(results: list[RunResult]) -> ExperimentStatsResult:
    """Groups RunResults by variant_key, computes per-algorithm averages."""
    buckets: dict[str, dict] = defaultdict(
        lambda: {
            "ant_colony": {"values": [], "times": []},
            "probabilistic": {"values": [], "times": []},
        }
    )
    for r in results:
        buckets[r.variant_key][r.algorithm]["values"].append(r.value)
        buckets[r.variant_key][r.algorithm]["times"].append(r.time_seconds)

    final: dict[str, VariantStats] = {}
    for key, data in buckets.items():
        ant_vals = data["ant_colony"]["values"]
        ant_times = data["ant_colony"]["times"]
        prob_vals = data["probabilistic"]["values"]
        prob_times = data["probabilistic"]["times"]

        ant_avg_v = sum(ant_vals) / len(ant_vals) if ant_vals else 0.0
        ant_avg_t = sum(ant_times) / len(ant_times) if ant_times else 0.0
        prob_avg_v = sum(prob_vals) / len(prob_vals) if prob_vals else 0.0
        prob_avg_t = sum(prob_times) / len(prob_times) if prob_times else 0.0

        rel_diff = (
            (ant_avg_v - prob_avg_v) / ant_avg_v * 100
            if ant_avg_v != 0 else 0.0
        )

        final[key] = VariantStats(
            ant=AlgoStats(avg_value=ant_avg_v, avg_time=ant_avg_t),
            prob=AlgoStats(avg_value=prob_avg_v, avg_time=prob_avg_t),
            relative_difference=rel_diff,
        )

    return ExperimentStatsResult(final)


# ---------------------------------------------------------------------------
# ExperimentSpec Protocol
# ---------------------------------------------------------------------------

class ExperimentSpec(Protocol):
    name: str
    input_model: type[BaseModel]
    result_model: type[BaseModel]

    @staticmethod
    def format_variant_key(variant) -> str:
        """Single source of truth for variant → string key in results dict."""
        ...

    @staticmethod
    def generate_runs(input: BaseModel) -> list[RunAlgorithmInput]:
        """Pure: no I/O, no time.time(). Random is OK (called from activity)."""
        ...

    @staticmethod
    def aggregate(
        results: list[RunResult],
        runs: list[RunAlgorithmInput],
        input: BaseModel,
    ) -> BaseModel:
        """Pure: no I/O, no random, no time.time()."""
        ...
