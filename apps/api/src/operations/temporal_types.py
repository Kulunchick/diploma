import os

from shared.types import (  # noqa: F401 — re-exported for routers
    AntColonyParams,
    AlgorithmResult,
    BetaVariant,
    Experiment1Input,
    Experiment2Input,
    Experiment3Input,
    Experiment4Input,
    ExperimentInput,
    ExperimentResult,
    KmaxVariant,
    MNVariant,
    ProbabilisticParams,
    Range,
    SingleSolveInput,
    SolveInput,
    SolveResult,
)

TEMPORAL_HOST      = os.getenv("TEMPORAL_HOST",      "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE",  "default")
TASK_QUEUE         = os.getenv("TASK_QUEUE",           "operations")
REDIS_URL          = os.getenv("REDIS_URL",            "redis://localhost:6379")

SOLVE_WORKFLOW_NAME            = "SolveWorkflow"
EXPERIMENT_WORKFLOW_NAME       = "ExperimentWorkflow"
SINGLE_ALGORITHM_WORKFLOW_NAME = "SingleAlgorithmWorkflow"
