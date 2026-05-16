"""Experiment 2: vary beta."""
from experiments.base import ExperimentStatsResult, aggregate_to_stats
from experiments.task_generator import TaskGenerator
from shared.types import AntColonyParams, BetaVariant, Experiment2Input, ProbabilisticParams
from worker.types import RunAlgorithmInput, RunResult


class Experiment2Spec:
    name = "experiment2"
    input_model = Experiment2Input
    result_model = ExperimentStatsResult

    @staticmethod
    def format_variant_key(variant: BetaVariant) -> str:
        return str(variant.beta)

    @staticmethod
    def generate_runs(input: Experiment2Input) -> list[RunAlgorithmInput]:
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
            for variant in input.betaVariants:
                key = Experiment2Spec.format_variant_key(variant)
                base = dict(m=input.m, n=input.n, c=c, b_ij=b_ij,
                            b_total=b_total, omega=omega, variant_key=key)
                runs.append(RunAlgorithmInput(
                    **base, algorithm="ant_colony",
                    ant_colony_params=AntColonyParams(
                        num_ants=input.l, kmax=input.antKmax,
                        alpha=input.alpha, beta=variant.beta,
                        rho=input.p, initial_pheromone=input.tau,
                    ),
                ))
                runs.append(RunAlgorithmInput(
                    **base, algorithm="probabilistic",
                    probabilistic_params=ProbabilisticParams(kmax=input.antKmax),
                ))
        return runs

    @staticmethod
    def aggregate(results: list[RunResult], runs: list[RunAlgorithmInput],
                  input: Experiment2Input) -> ExperimentStatsResult:
        return aggregate_to_stats(results)
