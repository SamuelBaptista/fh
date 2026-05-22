import pytest
import copy
from app.worker import Worker


@pytest.fixture
def worker():
    return Worker(llm_mode="mock")


@pytest.mark.asyncio
async def test_case_3k_broker_email_ignored(worker, base_load):
    event = {
        "event_id": "evt-3k",
        "event_type": "inbound_communication",
        "load_id": "load-visible-001",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:55:00Z",
        "inbound_communication": {
            "channel": "email", "sender_type": "broker", "sender_name": "Blake Broker",
            "content": "Can carrier take $200 less on this one?", "attachments": [],
        },
    }
    result = await worker.process_event(event, base_load)
    assert result["branch"] == "broker_ignored"
    assert result["tool_calls"] == []
    assert result["state"] == "on_route_to_delivery"


@pytest.mark.asyncio
async def test_case_3h_tracking_arrival(worker, base_load):
    load = copy.deepcopy(base_load)
    load["customer_id"] = "customer_b"

    for seq in [1, 2]:
        event = {
            "event_id": f"evt-3h-{seq}", "event_type": "tracking",
            "load_id": "load-visible-001", "customer_id": "customer_b",
            "occurred_at": f"2026-05-11T17:{30 + seq * 5}:00Z",
            "tracking": {"tracking_id": f"trk-{seq}", "lat": 32.777, "lng": -96.797, "distance_to_delivery_miles": 0.2, "ping_sequence": seq, "provider": "mock"},
        }
        result = await worker.process_event(event, load)
        load["session_state"] = result["session_state"]

    event = {
        "event_id": "evt-3h-3", "event_type": "tracking",
        "load_id": "load-visible-001", "customer_id": "customer_b",
        "occurred_at": "2026-05-11T17:40:00Z",
        "tracking": {"tracking_id": "trk-3", "lat": 32.7768, "lng": -96.7972, "distance_to_delivery_miles": 0.1, "ping_sequence": 3, "provider": "mock"},
    }
    result = await worker.process_event(event, load)
    assert result["state"] == "at_delivery"
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    assert "update_load_state" in tools_used
    assert "cancel_timers" in tools_used
    assert "create_issue" not in tools_used
    assert "create_task" not in tools_used
    assert "update_eta" not in tools_used
