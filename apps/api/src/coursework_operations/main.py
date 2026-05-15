import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from src.coursework_operations.routers import jobs, solve
from src.coursework_operations.routers import experiments
from src.worker.config import REDIS_URL, TEMPORAL_HOST, TEMPORAL_NAMESPACE

# ---------------------------------------------------------------------------
# Legacy handlers (original WS endpoints, kept for rollback)
# ---------------------------------------------------------------------------
from src.coursework_operations.handlers.solve_handler import (
    solve_handler as _solve_legacy,
)
from src.coursework_operations.handlers.experiment1_handler import (
    experiment1_handler as _experiment1_legacy,
)
from src.coursework_operations.handlers.experiment2_handler import (
    experiment2_handler as _experiment2_legacy,
)
from src.coursework_operations.handlers.experiment3_handler import (
    experiment3_handler as _experiment3_legacy,
)
from src.coursework_operations.handlers.experiment4_handler import (
    experiment4_handler as _experiment4_legacy,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.temporal = await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
        data_converter=pydantic_data_converter,
    )
    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
    yield
    await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)

_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# New Temporal-backed routes
# ---------------------------------------------------------------------------
app.include_router(solve.router)
app.include_router(experiments.router)
app.include_router(jobs.router)

# ---------------------------------------------------------------------------
# Legacy WebSocket routes — kept for rollback (switch URL on frontend)
# ---------------------------------------------------------------------------
app.add_api_websocket_route("/ws/solve_legacy", _solve_legacy)
app.add_api_websocket_route("/ws/experiment1_legacy", _experiment1_legacy)
app.add_api_websocket_route("/ws/experiment2_legacy", _experiment2_legacy)
app.add_api_websocket_route("/ws/experiment3_legacy", _experiment3_legacy)
app.add_api_websocket_route("/ws/experiment4_legacy", _experiment4_legacy)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
