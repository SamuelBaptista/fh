import pytest
from app.worker import Worker


@pytest.fixture
def worker():
    return Worker(llm_mode="mock")


@pytest.mark.asyncio
async def test_worker_processes_broker_message(worker):
    event = {
        "event_id": "evt-broker",
        "event_type": "inbound_communication",
        "load_id": "load-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:55:00Z",
        "inbound_communication": {
            "channel": "email",
            "sender_type": "broker",
            "sender_name": "Blake",
            "content": "Take $200 less?",
            "attachments": [],
        },
    }
    load_row = {
        "load_id": "load-1",
        "customer_id": "customer_a",
        "state": "on_route_to_delivery",
        "version": 1,
        "load_data": {"stops": []},
        "session_state": {},
    }

    result = await worker.process_event(event, load_row)
    assert result["branch"] == "broker_ignored"
    assert result["tool_calls"] == []
    assert result["state"] == "on_route_to_delivery"


@pytest.mark.asyncio
async def test_worker_processes_tracking_arrival(worker):
    event = {
        "event_id": "evt-trk-3",
        "event_type": "tracking",
        "load_id": "load-1",
        "customer_id": "customer_b",
        "occurred_at": "2026-05-11T17:40:00Z",
        "tracking": {
            "tracking_id": "trk-3",
            "lat": 32.7768,
            "lng": -96.7972,
            "distance_to_delivery_miles": 0.1,
            "ping_sequence": 3,
            "provider": "mock",
        },
    }
    load_row = {
        "load_id": "load-1",
        "customer_id": "customer_b",
        "state": "on_route_to_delivery",
        "version": 3,
        "load_data": {"stops": []},
        "session_state": {"ping_streak": 2, "recent_events": []},
    }

    result = await worker.process_event(event, load_row)
    assert result["branch"] == "tracking_arrival_confirmed"
    assert result["state"] == "at_delivery"
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    assert "update_load_state" in tools_used
    assert "cancel_timers" in tools_used
