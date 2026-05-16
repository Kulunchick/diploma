import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from experiments.registry import EXPERIMENT_REGISTRY
    from worker.activities import (
        generate_experiment_runs_activity,
        run_experiment_variant_activity,
    )
    from worker.types import (
        ExperimentInput,
        ExperimentResult,
        ExperimentVariantInput,
        GenerateRunsInput,
        RunResult,
    )


@workflow.defn
class ExperimentWorkflow:
    def __init__(self) -> None:
        self._completed: int = 0
        self._total: int = 0
        self._partial_results: list[RunResult] = []

    @workflow.run
    async def run(self, input: ExperimentInput) -> ExperimentResult:
        # The generator activity stores the full variant list in Redis and
        # returns only the count, so we never pull the bulky list into the
        # workflow history.
        count: int = await workflow.execute_activity(
            generate_experiment_runs_activity,
            GenerateRunsInput(
                experiment_type=input.experiment_type,
                params=input.params,
            ),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        self._total = count

        semaphore = asyncio.Semaphore(input.concurrency)

        async def run_one(index: int) -> RunResult:
            async with semaphore:
                result: RunResult = await workflow.execute_activity(
                    run_experiment_variant_activity,
                    ExperimentVariantInput(index=index),
                    start_to_close_timeout=timedelta(minutes=30),
                    heartbeat_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            self._completed += 1
            self._partial_results.append(result)
            return result

        try:
            results: list[RunResult] = list(
                await asyncio.gather(*[run_one(i) for i in range(count)])
            )
        except asyncio.CancelledError:
            raise

        spec = EXPERIMENT_REGISTRY[input.experiment_type]
        validated_input = spec.input_model.model_validate(input.params)
        # aggregate() takes `runs` for protocol compatibility but no
        # experiment implementation uses it — pass an empty list.
        aggregated = spec.aggregate(results, [], validated_input)

        return ExperimentResult(data=aggregated.model_dump())

    @workflow.query
    def progress(self) -> dict:
        return {"completed": self._completed, "total": self._total}

    @workflow.query
    def partial_results(self) -> list[dict]:
        return [r.model_dump() for r in self._partial_results]
