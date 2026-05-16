"""
Thin wrappers: validate spec-specific input, start ExperimentWorkflow.
No imports from apps/worker — workflow started by name string.
"""
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from temporalio.client import Client

from src.operations.routers.deps import get_redis, get_temporal_client
from src.operations.temporal_types import (
    EXPERIMENT_WORKFLOW_NAME,
    Experiment1Input,
    Experiment2Input,
    Experiment3Input,
    Experiment4Input,
    ExperimentInput,
    TASK_QUEUE,
)

router = APIRouter()


async def _start_experiment(
    experiment_type: str,
    params: dict,
    client: Client,
    redis: Redis,
) -> dict:
    workflow_id = f"{experiment_type}-{uuid.uuid4()}"
    await client.start_workflow(
        EXPERIMENT_WORKFLOW_NAME,
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
