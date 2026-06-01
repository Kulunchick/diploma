from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from worker.activities import persist_formation_result_activity, run_algorithm_activity
    from worker.types import (
        PersistFormationInput,
        RunAlgorithmInput,
        RunResult,
        SingleSolveInput,
    )


@workflow.defn
class SingleAlgorithmWorkflow:
    """Runs exactly one algorithm for a formation scenario and persists the
    result to Postgres. Reuses run_algorithm_activity (same as SolveWorkflow);
    differs only in running a single algorithm and writing the result back."""

    def __init__(self) -> None:
        self._state: str = "running"

    @workflow.run
    async def run(self, input: SingleSolveInput) -> RunResult:
        run_input = RunAlgorithmInput(
            m=input.m,
            n=input.n,
            c=input.c,
            b_ij=input.b_ij,
            b_total=input.b_total,
            omega=input.omega,
            algorithm=input.algorithm,
            ant_colony_params=input.ant_colony if input.algorithm == "ant_colony" else None,
            probabilistic_params=input.probabilistic
            if input.algorithm == "probabilistic"
            else None,
            variant_key="formation",
            redis_channel=input.redis_channel,
            p_ij=input.p_ij,
            s_ij=input.s_ij,
        )

        result: RunResult = await workflow.execute_activity(
            run_algorithm_activity,
            run_input,
            start_to_close_timeout=timedelta(minutes=5),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        await workflow.execute_activity(
            persist_formation_result_activity,
            PersistFormationInput(
                scenario_id=input.scenario_id,
                solution=result.solution,
                value=result.value,
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
