import pytest
from app.models import (
    LoadSeedRequest,
    SubmitTaskRequest,
    InboundCommunicationEvent,
    TrackingEvent,
    LoadUpdateEvent,
    Address,
    Stop,
    LoadData,
    ToolCallRecord,
)


def test_load_seed_request_valid():
    req = LoadSeedRequest(
        load_id="load-001",
        customer_id="customer_a",
        load_data=LoadData(
            external_load_id="FH-001",
            companies={
                "broker": {"name": "Broker Co"},
                "shipper": {"name": "Shipper Co"},
                "carrier": {"name": "Carrier Co"},
            },
            contacts={},
            stops=[
                Stop(
                    stop_id="pickup-1",
                    type="pickup",
                    address=Address(line_1="123 St", city="Chicago", state="IL", postal_code="60601", country="US"),
                    appointment={"type": "fixed", "start_utc": "2026-05-10T14:00:00Z", "timezone": "America/Chicago"},
                    coordinates={"lat": 41.8, "lng": -87.6},
                ),
                Stop(
                    stop_id="delivery-1",
                    type="delivery",
                    address=Address(line_1="456 St", city="Dallas", state="TX", postal_code="75201", country="US"),
                    appointment={"type": "fixed", "start_utc": "2026-05-11T20:00:00Z", "timezone": "America/Chicago"},
                    coordinates={"lat": 32.7, "lng": -96.8},
                ),
            ],
        ),
        initial_state="on_route_to_delivery",
    )
    assert req.load_id == "load-001"
    assert req.customer_id == "customer_a"


def test_load_seed_request_invalid_customer():
    with pytest.raises(Exception):
        LoadSeedRequest(
            load_id="load-001",
            customer_id="customer_z",
            load_data=LoadData(
                external_load_id="X",
                companies={"broker": {"name": "B"}, "shipper": {"name": "S"}, "carrier": {"name": "C"}},
                contacts={},
                stops=[],
            ),
        )


def test_inbound_communication_event():
    evt = InboundCommunicationEvent(
        event_id="evt-1",
        event_type="inbound_communication",
        load_id="load-001",
        customer_id="customer_a",
        occurred_at="2026-05-11T17:05:00Z",
        inbound_communication={
            "channel": "sms",
            "sender_type": "driver",
            "sender_name": "Sam",
            "content": "Hello",
            "attachments": [],
        },
    )
    assert evt.inbound_communication.channel == "sms"
    assert evt.inbound_communication.sender_type == "driver"


def test_tracking_event():
    evt = TrackingEvent(
        event_id="evt-2",
        event_type="tracking",
        load_id="load-001",
        customer_id="customer_b",
        occurred_at="2026-05-11T17:30:00Z",
        tracking={
            "tracking_id": "trk-1",
            "lat": 32.777,
            "lng": -96.797,
            "distance_to_delivery_miles": 0.2,
            "ping_sequence": 1,
            "provider": "mock",
        },
    )
    assert evt.tracking.distance_to_delivery_miles == 0.2


def test_tool_call_record():
    rec = ToolCallRecord(
        tool_call_id="tc-1",
        event_id="evt-1",
        load_id="load-001",
        tool="send_sms",
        arguments={"recipient": "driver", "message": "hi"},
        result={"ok": True, "channel": "sms", "message_id": "sms-uuid"},
        created_at="2026-05-11T17:05:01Z",
    )
    assert rec.tool == "send_sms"
