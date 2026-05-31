import os

from shared.types import (  # noqa: F401 — re-exported for routers
    AntColonyParams,
    ProbabilisticParams,
    SingleSolveInput,
)

TEMPORAL_HOST      = os.getenv("TEMPORAL_HOST",      "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE",  "default")
TASK_QUEUE         = os.getenv("TASK_QUEUE",           "operations")
REDIS_URL          = os.getenv("REDIS_URL",            "redis://localhost:6379")

SINGLE_ALGORITHM_WORKFLOW_NAME = "SingleAlgorithmWorkflow"
