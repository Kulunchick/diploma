from fastapi import Request
from redis.asyncio import Redis
from temporalio.client import Client


async def get_temporal_client(request: Request) -> Client:
    return request.app.state.temporal


async def get_redis(request: Request) -> Redis:
    return request.app.state.redis
