import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from temporalio.client import Client

from src.operations.models.task_request import TaskRequest
from src.operations.routers.deps import get_redis, get_temporal_client
from src.operations.temporal_types import (
    AntColonyParams,
    ProbabilisticParams,
    SOLVE_WORKFLOW_NAME,
    TASK_QUEUE,
    SolveInput,
)

router = APIRouter()


@router.post("/solve")
async def start_solve(
    body: TaskRequest,
    client: Client = Depends(get_temporal_client),
    redis: Redis = Depends(get_redis),
):
    workflow_id = f"solve-{uuid.uuid4()}"
    redis_channel = f"solve:{workflow_id}"

    solve_input = SolveInput(
        m=body.m,
        n=body.n,
        c=body.c,
        b_ij=body.B_ij,
        b_total=body.B_total,
        omega=body.omega,
        ant_colony=AntColonyParams(
            num_ants=body.algorithm_parameters.ant_colony.num_ants,
            kmax=body.algorithm_parameters.ant_colony.Kmax,
            alpha=body.algorithm_parameters.ant_colony.alpha,
            beta=body.algorithm_parameters.ant_colony.beta,
            rho=body.algorithm_parameters.ant_colony.p,
            initial_pheromone=body.algorithm_parameters.ant_colony.tau,
        ),
        probabilistic=ProbabilisticParams(
            kmax=body.algorithm_parameters.probabilistic.Kmax,
        ),
        redis_channel=redis_channel,
    )

    # Use the registered workflow name — avoids importing the worker package.
    await client.start_workflow(
        SOLVE_WORKFLOW_NAME,
        solve_input,
        id=workflow_id,
        task_queue=TASK_QUEUE,
        execution_timeout=timedelta(minutes=10),
    )

    await redis.set(f"workflow_type:{workflow_id}", "solve", ex=3600)

    return {"workflow_id": workflow_id}
