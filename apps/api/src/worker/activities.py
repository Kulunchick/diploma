from temporalio import activity

from src.worker.types import GenerateRunsInput, RunAlgorithmInput, RunResult


@activity.defn
async def run_algorithm_activity(input: RunAlgorithmInput) -> RunResult:
    """
    Atomic unit: one run of one algorithm on one task.
    Calls the Rust solver, optionally streams iterations to Redis.
    Implemented in step 3.
    """
    raise NotImplementedError


@activity.defn
async def generate_experiment_runs_activity(
    input: GenerateRunsInput,
) -> list[RunAlgorithmInput]:
    """
    Generates the full list of RunAlgorithmInput for an experiment.
    Uses the spec from EXPERIMENT_REGISTRY to call generate_runs.
    Runs as an activity (not in workflow) because TaskGenerator uses random.
    Implemented in step 5.
    """
    raise NotImplementedError
