"""Thin wrappers: validate spec-specific input, start ExperimentWorkflow."""
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from temporalio.client import Client

from src.coursework_operations.routers.deps import get_redis, get_temporal_client
from experiments.experiment1 import Experiment1Input
from experiments.experiment2 import Experiment2Input
from experiments.experiment3 import Experiment3Input
from experiments.experiment4 import Experiment4Input
from worker.config import TASK_QUEUE
from worker.types import ExperimentInput
from worker.workflows.experiment import ExperimentWorkflow

router = APIRouter()


async def _start_experiment(
    experiment_type: str,
    params: dict,
    client: Client,
    redis: Redis,
) -> dict:
    workflow_id = f"{experiment_type}-{uuid.uuid4()}"
    await client.start_workflow(
        ExperimentWorkflow.run,
        ExperimentInput(experiment_type=experiment_type, params=params),
        id=workflow_id,
        task_queue=TASK_QUEUE,
        execution_timeout=timedelta(hours=1),
    )
    await redis.set(f"workflow_type:{workflow_id}", "experiment", ex=86400)
    return {"workflow_id": workflow_id}


@router.post("/experiment1")
async def start_experiment1(
    body: Experiment1Input,
    client: Client = Depends(get_temporal_client),
    redis: Redis = Depends(get_redis),
):
    return await _start_experiment("experiment1", body.model_dump(), client, redis)


@router.post("/experiment2")
async def start_experiment2(
    body: Experiment2Input,
    client: Client = Depends(get_temporal_client),
    redis: Redis = Depends(get_redis),
):
    return await _start_experiment("experiment2", body.model_dump(), client, redis)


@router.post("/experiment3")
async def start_experiment3(
    body: Experiment3Input,
    client: Client = Depends(get_temporal_client),
    redis: Redis = Depends(get_redis),
):
    return await _start_experiment("experiment3", body.model_dump(), client, redis)


@router.post("/experiment4")
async def start_experiment4(
    body: Experiment4Input,
    client: Client = Depends(get_temporal_client),
    redis: Redis = Depends(get_redis),
):
    return await _start_experiment("experiment4", body.model_dump(), client, redis)
