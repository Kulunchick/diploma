from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from worker.activities import (
        persist_combined_result_activity,
        run_combined_method_activity,
    )
    from worker.types import (
        CombinedResult,
        CombinedSolveInput,
        PersistCombinedInput,
    )


@workflow.defn
class CombinedFormationWorkflow:
    """Runs the combined method (article §4–5) for a formation scenario and
    persists F_IT, F_prov, the negotiated discounts and the expanded per-service
    assignments. Same shape as SingleAlgorithmWorkflow: run then persist."""

    def __init__(self) -> None:
        self._state: str = "running"

    @workflow.run
    async def run(self, input: CombinedSolveInput) -> CombinedResult:
        result: CombinedResult = await workflow.execute_activity(
            run_combined_method_activity,
            input,
            start_to_close_timeout=timedelta(minutes=10),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        await workflow.execute_activity(
            persist_combined_result_activity,
            PersistCombinedInput(
                scenario_id=input.scenario_id,
                v_final=result.v_final,
                r_final=result.r_final,
                f_it=result.f_it,
                f_prov=result.f_prov,
                source=result.source,
                redis_channel=input.redis_channel,
            ),
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        self._state = "done"
        return result

    @workflow.query
    def current_state(self) -> str:
        return self._state
