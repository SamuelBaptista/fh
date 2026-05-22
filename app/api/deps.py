from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Header

from app.config.settings import settings
from app.infra.db import DynamoDBClient
from app.infra.queue import SQSClient


_db: DynamoDBClient | None = None
_queue: SQSClient | None = None


def get_db() -> DynamoDBClient:
    global _db
    if _db is None:
        _db = DynamoDBClient()
    return _db


def get_queue() -> SQSClient:
    global _queue
    if _queue is None:
        _queue = SQSClient()
    return _queue


async def verify_token(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[7:]
    if token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


AuthDep = Annotated[str, Depends(verify_token)]
