from app.core.session import SessionState


def test_empty_session():
    s = SessionState()
    assert s.ping_streak == 0
    assert s.recent_events == []
    assert s.last_eta is None


def test_add_event_rolls():
    s = SessionState()
    for i in range(12):
        s.add_event({"event_id": f"evt-{i}", "type": "tracking"})
    assert len(s.recent_events) == 10
    assert s.recent_events[0]["event_id"] == "evt-2"


def test_ping_streak_increment():
    s = SessionState()
    s.increment_ping_streak()
    s.increment_ping_streak()
    assert s.ping_streak == 2


def test_ping_streak_reset():
    s = SessionState()
    s.increment_ping_streak()
    s.increment_ping_streak()
    s.reset_ping_streak()
    assert s.ping_streak == 0


def test_serialization_roundtrip():
    s = SessionState()
    s.increment_ping_streak()
    s.add_event({"event_id": "evt-1"})
    s.last_eta = "2026-05-11T19:00:00Z"

    data = s.to_dict()
    s2 = SessionState.from_dict(data)
    assert s2.ping_streak == 1
    assert s2.recent_events == [{"event_id": "evt-1"}]
    assert s2.last_eta == "2026-05-11T19:00:00Z"
