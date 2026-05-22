from app.agent.dispatcher import Dispatcher
from app.core.session import SessionState
from app.config.customer import get_customer_policy


def make_comm_event(sender_type="driver", channel="sms", content="hello", attachments=None):
    return {
        "event_id": "evt-1",
        "event_type": "inbound_communication",
        "load_id": "load-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:05:00Z",
        "inbound_communication": {
            "channel": channel,
            "sender_type": sender_type,
            "sender_name": "Test",
            "content": content,
            "attachments": attachments or [],
        },
    }


def make_tracking_event(distance=0.2, sequence=1):
    return {
        "event_id": f"evt-trk-{sequence}",
        "event_type": "tracking",
        "load_id": "load-1",
        "customer_id": "customer_b",
        "occurred_at": "2026-05-11T17:30:00Z",
        "tracking": {
            "tracking_id": f"trk-{sequence}",
            "lat": 32.777,
            "lng": -96.797,
            "distance_to_delivery_miles": distance,
            "ping_sequence": sequence,
            "provider": "mock",
        },
    }


def test_broker_message_ignored():
    d = Dispatcher()
    session = SessionState()
    policy = get_customer_policy("customer_a")
    event = make_comm_event(sender_type="broker", content="Can you take $200 less?")
    result = d.route(event, session, policy)
    assert result.branch == "broker_ignored"
    assert result.requires_agent is False
    assert result.tool_calls == []


def test_tracking_ping_outside_geofence():
    d = Dispatcher()
    session = SessionState()
    policy = get_customer_policy("customer_a")  # 1 mile geofence
    event = make_tracking_event(distance=5.0, sequence=1)
    result = d.route(event, session, policy)
    assert result.branch == "tracking_outside_geofence"
    assert result.requires_agent is False
    assert session.ping_streak == 0


def test_tracking_ping_inside_geofence_increments_streak():
    d = Dispatcher()
    session = SessionState()
    policy = get_customer_policy("customer_b")  # 2 mile geofence
    event = make_tracking_event(distance=0.5, sequence=1)
    result = d.route(event, session, policy)
    assert result.branch == "tracking_in_geofence"
    assert session.ping_streak == 1
    assert result.state_transition is None


def test_tracking_three_pings_triggers_arrival():
    d = Dispatcher()
    session = SessionState()
    session.ping_streak = 2  # already had 2 in-geofence pings
    policy = get_customer_policy("customer_b")
    event = make_tracking_event(distance=0.1, sequence=3)
    result = d.route(event, session, policy)
    assert result.branch == "tracking_arrival_confirmed"
    assert result.state_transition == "at_delivery"
    assert any(tc["tool"] == "update_load_state" for tc in result.tool_calls)
    assert any(tc["tool"] == "cancel_timers" for tc in result.tool_calls)


def test_inbound_comm_routes_to_agent():
    d = Dispatcher()
    session = SessionState()
    policy = get_customer_policy("customer_a")
    event = make_comm_event(content="What's the delivery address?")
    result = d.route(event, session, policy)
    assert result.requires_agent is True
    assert result.branch == "agent_required"
