"""Experiment 3: vary m×n size. alpha=1.0/beta=1.0 hardcoded."""
from typing import List

from pydantic import BaseModel

from experiments.base import ExperimentStatsResult, Range, aggregate_to_stats
from experiments.task_generator import TaskGenerator
from worker.types import AntColonyParams, ProbabilisticParams, RunAlgorithmInput, RunResult


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


class Experiment3Spec:
    name = "experiment3"
    input_model = Experiment3Input
    result_model = ExperimentStatsResult

    @staticmethod
    def format_variant_key(variant: MNVariant) -> str:
        return f"{variant.m}x{variant.n}"

    @staticmethod
    def generate_runs(input: Experiment3Input) -> list[RunAlgorithmInput]:
        generator = TaskGenerator(
            c_min=input.cRange.min, c_max=input.cRange.max,
            b_min=input.bRange.min, b_max=input.bRange.max,
            omega_min=input.omegaRange.min, omega_max=input.omegaRange.max,
        )
        runs: list[RunAlgorithmInput] = []
        for _ in range(input.count):
            for variant in input.mnVariants:
                task = generator.generate_task(m=variant.m, n=variant.n)
                key = Experiment3Spec.format_variant_key(variant)
                base = dict(
                    m=variant.m, n=variant.n,
                    c=task.c.tolist(), b_ij=task.B_ij.tolist(),
                    b_total=int(task.B_total), omega=task.omega.tolist(),
                    variant_key=key,
                )
                runs.append(RunAlgorithmInput(
                    **base, algorithm="ant_colony",
                    ant_colony_params=AntColonyParams(
                        num_ants=input.l, kmax=input.antKmax,
                        alpha=1.0, beta=1.0,
                        rho=input.p, initial_pheromone=input.tau,
                    ),
                ))
                runs.append(RunAlgorithmInput(
                    **base, algorithm="probabilistic",
                    probabilistic_params=ProbabilisticParams(kmax=input.probKmax),
                ))
        return runs

    @staticmethod
    def aggregate(results: list[RunResult], runs: list[RunAlgorithmInput],
                  input: Experiment3Input) -> ExperimentStatsResult:
        return aggregate_to_stats(results)
