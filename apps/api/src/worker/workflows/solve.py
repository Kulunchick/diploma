from temporalio import workflow

from src.worker.types import SolveInput, SolveResult


@workflow.defn
class SolveWorkflow:
    def __init__(self) -> None:
        # Tracks per-algorithm state for the current_state() query.
        self._state: dict = {}

    @workflow.run
    async def run(self, input: SolveInput) -> SolveResult:
        """
        Runs ant_colony and probabilistic activities in parallel.
        Streams iterations via Redis (activity handles pub/sub).
        Implemented in step 4.
        """
        raise NotImplementedError

    @workflow.query
    def current_state(self) -> dict:
        return self._state
