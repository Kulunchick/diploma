import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.experiments.registry import EXPERIMENT_REGISTRY
    from src.worker.activities import (
        generate_experiment_runs_activity,
        run_algorithm_activity,
    )
    from src.worker.types import (
        ExperimentInput,
        ExperimentResult,
        GenerateRunsInput,
        RunAlgorithmInput,
        RunResult,
    )


@workflow.defn
class ExperimentWorkflow:
    """Universal workflow for all experiment types.
    The experiment_type field selects the spec from EXPERIMENT_REGISTRY.
    """

    def __init__(self) -> None:
        self._completed: int = 0
        self._total: int = 0
        self._partial_results: list[RunResult] = []

    @workflow.run
    async def run(self, input: ExperimentInput) -> ExperimentResult:
        # 1. Generate all runs (uses random → must be an activity, not workflow code)
        runs: list[RunAlgorithmInput] = await workflow.execute_activity(
            generate_experiment_runs_activity,
            GenerateRunsInput(
                experiment_type=input.experiment_type,
                params=input.params,
            ),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        self._total = len(runs)

        # 2. Fan-out with Semaphore to cap concurrent activities.
        #    default concurrency=1: Rust+Rayon already saturates all cores.
        semaphore = asyncio.Semaphore(input.concurrency)

        async def run_one(run_input: RunAlgorithmInput) -> RunResult:
            async with semaphore:
                result: RunResult = await workflow.execute_activity(
                    run_algorithm_activity,
                    run_input,
                    start_to_close_timeout=timedelta(minutes=30),
                    heartbeat_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            self._completed += 1
            self._partial_results.append(result)
            return result

        try:
            results: list[RunResult] = list(
                await asyncio.gather(*[run_one(r) for r in runs])
            )
        except asyncio.CancelledError:
            # Partial progress is visible via the progress() and partial_results() queries.
            raise

        # 3. Aggregate — pure function, safe to call in workflow code.
        spec = EXPERIMENT_REGISTRY[input.experiment_type]
        validated_input = spec.input_model.model_validate(input.params)
        aggregated = spec.aggregate(results, runs, validated_input)

        return ExperimentResult(data=aggregated.model_dump())

    @workflow.query
    def progress(self) -> dict:
        return {"completed": self._completed, "total": self._total}

    @workflow.query
    def partial_results(self) -> list[dict]:
        return [r.model_dump() for r in self._partial_results]
