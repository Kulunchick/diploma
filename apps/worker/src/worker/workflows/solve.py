import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from worker.activities import run_algorithm_activity
    from worker.types import (
        AlgorithmResult,
        RunAlgorithmInput,
        RunResult,
        SolveInput,
        SolveResult,
    )


@workflow.defn
class SolveWorkflow:
    def __init__(self) -> None:
        self._state: dict = {}

    @workflow.run
    async def run(self, input: SolveInput) -> SolveResult:
        self._state = {"ant_colony": "running", "probabilistic": "running"}

        _activity_opts = dict(
            start_to_close_timeout=timedelta(minutes=5),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        ant_input = RunAlgorithmInput(
            m=input.m, n=input.n, c=input.c, b_ij=input.b_ij,
            b_total=input.b_total, omega=input.omega,
            algorithm="ant_colony",
            ant_colony_params=input.ant_colony,
            variant_key="solve",
            redis_channel=input.redis_channel,
        )
        prob_input = RunAlgorithmInput(
            m=input.m, n=input.n, c=input.c, b_ij=input.b_ij,
            b_total=input.b_total, omega=input.omega,
            algorithm="probabilistic",
            probabilistic_params=input.probabilistic,
            variant_key="solve",
            redis_channel=input.redis_channel,
        )

        async def run_ant() -> RunResult:
            result: RunResult = await workflow.execute_activity(
                run_algorithm_activity, ant_input, **_activity_opts
            )
            self._state["ant_colony"] = "done"
            return result

        async def run_prob() -> RunResult:
            result: RunResult = await workflow.execute_activity(
                run_algorithm_activity, prob_input, **_activity_opts
            )
            self._state["probabilistic"] = "done"
            return result

        try:
            ant_result, prob_result = await asyncio.gather(run_ant(), run_prob())
        except asyncio.CancelledError:
            for key in ("ant_colony", "probabilistic"):
                if self._state.get(key) == "running":
                    self._state[key] = "cancelled"
            raise

        return SolveResult(
            ant_colony=AlgorithmResult(
                solution=ant_result.solution, value=ant_result.value
            ),
            probabilistic=AlgorithmResult(
                solution=prob_result.solution, value=prob_result.value
            ),
        )

    @workflow.query
    def current_state(self) -> dict:
        return self._state
