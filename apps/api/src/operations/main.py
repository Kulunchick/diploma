import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from src.operations.routers import experiments, jobs, solve
from src.operations.temporal_types import REDIS_URL, TEMPORAL_HOST, TEMPORAL_NAMESPACE

logger = logging.getLogger(__name__)


async def _connect_temporal() -> Client:
    for attempt in range(1, 31):
        try:
            return await Client.connect(
                TEMPORAL_HOST,
                namespace=TEMPORAL_NAMESPACE,
                data_converter=pydantic_data_converter,
            )
        except Exception as exc:
            if attempt == 30:
                raise
            logger.warning("Temporal not ready (attempt %d/30): %s — retrying in 5s", attempt, exc)
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.temporal = await _connect_temporal()
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

app.include_router(solve.router, prefix="/api")
app.include_router(experiments.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
