from temporalio import workflow

from src.worker.types import ExperimentInput, ExperimentResult, RunResult


@workflow.defn
class ExperimentWorkflow:
    """Universal workflow for all experiment types.
    The experiment_type field in ExperimentInput selects the spec from EXPERIMENT_REGISTRY.
    """

    def __init__(self) -> None:
        self._completed: int = 0
        self._total: int = 0
        self._partial_results: list[RunResult] = []

    @workflow.run
    async def run(self, input: ExperimentInput) -> ExperimentResult:
        """
        1. generate_experiment_runs_activity → list[RunAlgorithmInput]
        2. fan-out with asyncio.Semaphore(input.concurrency)
        3. collect RunResults
        4. spec.aggregate(results, runs, input) — pure, called directly in workflow
        5. return ExperimentResult
        Implemented in step 5.
        """
        raise NotImplementedError

    @workflow.query
    def progress(self) -> dict:
        return {"completed": self._completed, "total": self._total}

    @workflow.query
    def partial_results(self) -> list[dict]:
        return [r.model_dump() for r in self._partial_results]
