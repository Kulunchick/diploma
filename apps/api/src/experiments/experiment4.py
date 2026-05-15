"""
Experiment 4: vary omega range — compare algorithm sensitivity to discount levels.

Structure: count × |omegaRangeVariants| × 2 algorithms
Task generation: once per count iteration with omega_min=0/omega_max=0;
  omega overridden per variant with a fresh random draw.

NOTE: TaskGenerator is re-instantiated every iteration in the legacy code
but this has no effect on randomness (np.random state is global).
"""
import numpy as np
from typing import List

from pydantic import BaseModel

from src.coursework_operations.utils.generator import TaskGenerator
from src.experiments.base import ExperimentStatsResult, Range, aggregate_to_stats
from src.worker.types import AntColonyParams, ProbabilisticParams, RunAlgorithmInput, RunResult


class Experiment4Input(BaseModel):
    count: int
    omegaRangeVariants: List[Range]
    p: float        # rho
    tau: float      # initial_pheromone
    alpha: float
    beta: float
    m: int
    n: int
    antKmax: int
    probKmax: int
    l: int          # num_ants
    cRange: Range
    bRange: Range


class Experiment4Spec:
    name = "experiment4"
    input_model = Experiment4Input
    result_model = ExperimentStatsResult

    @staticmethod
    def format_variant_key(variant: Range) -> str:
        return f"{variant.min}-{variant.max}"

    @staticmethod
    def generate_runs(input: Experiment4Input) -> list[RunAlgorithmInput]:
        runs: list[RunAlgorithmInput] = []
        for _ in range(input.count):
            # Re-create generator per iteration (mirrors legacy; omega unused here)
            generator = TaskGenerator(
                c_min=input.cRange.min, c_max=input.cRange.max,
                b_min=input.bRange.min, b_max=input.bRange.max,
                omega_min=0, omega_max=0,
            )
            task = generator.generate_task(m=input.m, n=input.n)
            c = task.c.tolist()
            b_ij = task.B_ij.tolist()
            b_total = int(task.B_total)

            for omega_range in input.omegaRangeVariants:
                # TODO(post-migration): omega shape (n, m) is wrong, should be (m, n).
                # Preserved intentionally for legacy parity — fix in separate commit
                # after migration is in prod (will break m≠n cases).
                omega = np.random.uniform(
                    omega_range.min, omega_range.max, size=(input.n, input.m)
                ).tolist()
                key = Experiment4Spec.format_variant_key(omega_range)
                base = dict(m=input.m, n=input.n, c=c, b_ij=b_ij,
                            b_total=b_total, omega=omega, variant_key=key)
                runs.append(RunAlgorithmInput(
                    **base,
                    algorithm="ant_colony",
                    ant_colony_params=AntColonyParams(
                        num_ants=input.l, kmax=input.antKmax,
                        alpha=input.alpha, beta=input.beta,
                        rho=input.p, initial_pheromone=input.tau,
                    ),
                ))
                runs.append(RunAlgorithmInput(
                    **base,
                    algorithm="probabilistic",
                    probabilistic_params=ProbabilisticParams(kmax=input.probKmax),
                ))
        return runs

    @staticmethod
    def aggregate(
        results: list[RunResult],
        runs: list[RunAlgorithmInput],
        input: Experiment4Input,
    ) -> ExperimentStatsResult:
        return aggregate_to_stats(results)
