from __future__ import annotations

import uuid

from fastapi import FastAPI
from pydantic import BaseModel

from app.api.deps import AuthDep, get_db, get_queue
from app.core.models import (
    InboundCommunicationEvent,
    LoadSeedRequest,
    LoadUpdateEvent,
    SubmitTaskRequest,
    TrackingEvent,
)


app = FastAPI(title="Watchtower Mini", version="0.1.0")


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
