from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Header
from pydantic import BaseModel

from app.config import settings
from app.db import DynamoDBClient
from app.queue import SQSClient
from app.models import (
    InboundCommunicationEvent,
    LoadSeedRequest,
    LoadUpdateEvent,
    SubmitTaskRequest,
    TrackingEvent,
)


app = FastAPI(title="Watchtower Mini", version="0.1.0")

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


class AcceptedResponse(BaseModel):
    event_id: str
    load_id: str
    status: str = "accepted"


async def enqueue_event(event_data: dict, load_id: str) -> None:
    get_queue().send_event(event_data, load_id)


@app.post("/loads", status_code=202, response_model=AcceptedResponse)
async def create_load(body: LoadSeedRequest, _token: AuthDep = "") -> AcceptedResponse:
    event_id = f"evt-seed-{uuid.uuid4().hex[:8]}"
    get_db().put_load({
        "load_id": body.load_id,
        "customer_id": body.customer_id,
        "state": body.initial_state or "on_route_to_delivery",
        "version": 1,
        "load_data": body.load_data.model_dump(),
        "session_state": {},
    })
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=event_id, load_id=body.load_id)


@app.post("/submit-task", status_code=202, response_model=AcceptedResponse)
async def submit_task(body: SubmitTaskRequest, _token: AuthDep = "") -> AcceptedResponse:
    event_id = f"evt-task-{uuid.uuid4().hex[:8]}"
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=event_id, load_id=body.load_id)


@app.post("/events/inbound-communication", status_code=202, response_model=AcceptedResponse)
async def inbound_communication(body: InboundCommunicationEvent, _token: AuthDep = "") -> AcceptedResponse:
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=body.event_id, load_id=body.load_id)


@app.post("/events/tracking", status_code=202, response_model=AcceptedResponse)
async def tracking(body: TrackingEvent, _token: AuthDep = "") -> AcceptedResponse:
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=body.event_id, load_id=body.load_id)


@app.post("/events/load-update", status_code=202, response_model=AcceptedResponse)
async def load_update(body: LoadUpdateEvent, _token: AuthDep = "") -> AcceptedResponse:
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=body.event_id, load_id=body.load_id)


@app.get("/health")
async def health():
    return {"status": "ok"}
