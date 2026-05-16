"""Experiment 4: vary omega range.
TODO(post-migration): omega shape (n, m) is wrong, should be (m, n).
"""
import numpy as np

from experiments.base import ExperimentStatsResult, aggregate_to_stats
from experiments.task_generator import TaskGenerator
from shared.types import AntColonyParams, Experiment4Input, ProbabilisticParams, Range
from worker.types import RunAlgorithmInput, RunResult


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
                # TODO(post-migration): shape (n, m) preserved from legacy
                omega = np.random.uniform(
                    omega_range.min, omega_range.max, size=(input.n, input.m)
                ).tolist()
                key = Experiment4Spec.format_variant_key(omega_range)
                base = dict(m=input.m, n=input.n, c=c, b_ij=b_ij,
                            b_total=b_total, omega=omega, variant_key=key)
                runs.append(RunAlgorithmInput(
                    **base, algorithm="ant_colony",
                    ant_colony_params=AntColonyParams(
                        num_ants=input.l, kmax=input.antKmax,
                        alpha=input.alpha, beta=input.beta,
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
                  input: Experiment4Input) -> ExperimentStatsResult:
        return aggregate_to_stats(results)
