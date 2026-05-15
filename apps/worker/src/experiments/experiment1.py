"""Experiment 1: vary kmax."""
from typing import List

from pydantic import BaseModel

from experiments.base import ExperimentStatsResult, Range, aggregate_to_stats
from experiments.task_generator import TaskGenerator
from worker.types import AntColonyParams, ProbabilisticParams, RunAlgorithmInput, RunResult


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


class Experiment1Spec:
    name = "experiment1"
    input_model = Experiment1Input
    result_model = ExperimentStatsResult

    @staticmethod
    def format_variant_key(variant: KmaxVariant) -> str:
        return str(variant.kmax)

    @staticmethod
    def generate_runs(input: Experiment1Input) -> list[RunAlgorithmInput]:
        generator = TaskGenerator(
            c_min=input.cRange.min, c_max=input.cRange.max,
            b_min=input.bRange.min, b_max=input.bRange.max,
            omega_min=input.omegaRange.min, omega_max=input.omegaRange.max,
        )
        runs: list[RunAlgorithmInput] = []
        for _ in range(input.count):
            task = generator.generate_task(m=input.m, n=input.n)
            c = task.c.tolist()
            b_ij = task.B_ij.tolist()
            b_total = int(task.B_total)
            omega = task.omega.tolist()
            for variant in input.kmaxVariants:
                key = Experiment1Spec.format_variant_key(variant)
                base = dict(m=input.m, n=input.n, c=c, b_ij=b_ij,
                            b_total=b_total, omega=omega, variant_key=key)
                runs.append(RunAlgorithmInput(
                    **base, algorithm="ant_colony",
                    ant_colony_params=AntColonyParams(
                        num_ants=input.l, kmax=variant.kmax,
                        alpha=input.alpha, beta=input.beta,
                        rho=input.p, initial_pheromone=input.tau,
                    ),
                ))
                runs.append(RunAlgorithmInput(
                    **base, algorithm="probabilistic",
                    probabilistic_params=ProbabilisticParams(kmax=variant.kmax),
                ))
        return runs

    @staticmethod
    def aggregate(results: list[RunResult], runs: list[RunAlgorithmInput],
                  input: Experiment1Input) -> ExperimentStatsResult:
        return aggregate_to_stats(results)
