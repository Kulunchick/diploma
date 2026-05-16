import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.service import RPCError

from src.operations.routers.deps import get_redis, get_temporal_client
from src.operations.temporal_types import ExperimentResult, SolveResult

router = APIRouter(prefix="/jobs")


# ---------------------------------------------------------------------------
# WS /jobs/{workflow_id}/events
# ---------------------------------------------------------------------------

@router.websocket("/{workflow_id}/events")
async def jobs_events(
    websocket: WebSocket,
    workflow_id: str,
):
    # FastAPI does not inject Request-based Depends into WebSocket handlers;
    # access app.state directly instead.
    client: Client = websocket.app.state.temporal
    redis: Redis = websocket.app.state.redis

    await websocket.accept()
    try:
        workflow_type = await redis.get(f"workflow_type:{workflow_id}")

        if workflow_type == "solve":
            handle = client.get_workflow_handle(workflow_id, result_type=SolveResult)
            await _solve_adapter(websocket, handle, redis, workflow_id)
        else:
            handle = client.get_workflow_handle(workflow_id, result_type=ExperimentResult)
            await _experiment_adapter(websocket, handle, redis, workflow_id)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def _solve_adapter(websocket: WebSocket, handle, redis: Redis, workflow_id: str):
    """
    Maps Temporal/Redis events to the legacy /ws/solve format:
      {type:"start", algorithm}  — sent immediately on connect
      {type:"iteration", ...}    — forwarded from Redis Stream (XREAD)
      {type:"result", ...}       — from SolveResult when workflow completes
      {type:"complete"}          — after both results are sent

    Stream (not pub/sub) is used so late or reconnecting subscribers replay
    iterations from id "0" without losing anything published before connect.
    """
    stream_key = f"solve:{workflow_id}"

    # Frontend expects "start" for each algorithm immediately.
    await websocket.send_json({"type": "start", "algorithm": "ant_colony"})
    await websocket.send_json({"type": "start", "algorithm": "probabilistic"})

    # Shared cursor so the post-result flush can resume where the live task left off.
    state = {"last_id": "0", "stop": False}

    async def forward_stream() -> None:
        try:
            while not state["stop"]:
                msgs = await redis.xread({stream_key: state["last_id"]}, block=500, count=100)
                if not msgs:
                    continue
                for _, entries in msgs:
                    for entry_id, fields in entries:
                        await websocket.send_json(json.loads(fields["data"]))
                        state["last_id"] = entry_id
        except asyncio.CancelledError:
            pass

    stream_task = asyncio.create_task(forward_stream())
    try:
        result: SolveResult = await handle.result()

        # Stop the live reader and flush anything XADD'd just before completion.
        state["stop"] = True
        stream_task.cancel()
        await asyncio.gather(stream_task, return_exceptions=True)

        while True:
            tail = await redis.xread({stream_key: state["last_id"]}, count=100)
            if not tail:
                break
            for _, entries in tail:
                for entry_id, fields in entries:
                    await websocket.send_json(json.loads(fields["data"]))
                    state["last_id"] = entry_id

        await websocket.send_json({
            "type": "result",
            "algorithm": "ant_colony",
            "solution": result.ant_colony.solution,
            "value": result.ant_colony.value,
        })
        await websocket.send_json({
            "type": "result",
            "algorithm": "probabilistic",
            "solution": result.probabilistic.solution,
            "value": result.probabilistic.value,
        })
        await websocket.send_json({"type": "complete"})
    except Exception:
        state["stop"] = True
        stream_task.cancel()
        await asyncio.gather(stream_task, return_exceptions=True)
        raise
    finally:
        # Keep the stream around for ~1h so a reattach replays history.
        try:
            await redis.expire(stream_key, 3600)
        except Exception:
            pass


async def _experiment_adapter(websocket: WebSocket, handle, redis: Redis, workflow_id: str):
    """
    New unified experiment event format:
      {type:"started"}
      {type:"progress", completed:N, total:M}   — polled every 2 s
      {type:"complete", data:{...}}              — spec.aggregate() result
      {type:"error", message}
    """
    await websocket.send_json({"type": "started"})

    async def poll_progress() -> None:
        try:
            while True:
                await asyncio.sleep(2)
                try:
                    prog = await handle.query("progress")
                    await websocket.send_json({"type": "progress", **prog})
                except Exception:
                    pass
        except asyncio.CancelledError:
            pass

    progress_task = asyncio.create_task(poll_progress())
    try:
        result: ExperimentResult = await handle.result()

        progress_task.cancel()
        await asyncio.gather(progress_task, return_exceptions=True)

        # Send final progress so frontend sees 100 %.
        try:
            prog = await handle.query("progress")
            await websocket.send_json({"type": "progress", **prog})
        except Exception:
            pass

        await websocket.send_json({"type": "complete", "data": result.data})
    except Exception:
        progress_task.cancel()
        await asyncio.gather(progress_task, return_exceptions=True)
        raise


# ---------------------------------------------------------------------------
# GET /jobs/{workflow_id}
# ---------------------------------------------------------------------------

@router.get("/{workflow_id}")
async def get_job(
    workflow_id: str,
    client: Client = Depends(get_temporal_client),
):
    try:
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        status: WorkflowExecutionStatus = desc.status

        result_data = None
        error_msg = None

        if status == WorkflowExecutionStatus.COMPLETED:
            raw = await handle.result()
            result_data = raw.model_dump() if hasattr(raw, "model_dump") else raw
        elif status in (WorkflowExecutionStatus.FAILED, WorkflowExecutionStatus.TIMED_OUT):
            try:
                await handle.result()
            except Exception as e:
                error_msg = str(e)

        return {
            "workflow_id": workflow_id,
            "status": status.name if status else "UNKNOWN",
            "result": result_data,
            "error": error_msg,
        }
    except RPCError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# DELETE /jobs/{workflow_id}
# ---------------------------------------------------------------------------

@router.delete("/{workflow_id}")
async def cancel_job(
    workflow_id: str,
    client: Client = Depends(get_temporal_client),
):
    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.cancel()
        return {"workflow_id": workflow_id, "cancelled": True}
    except RPCError as e:
        raise HTTPException(status_code=404, detail=str(e))
