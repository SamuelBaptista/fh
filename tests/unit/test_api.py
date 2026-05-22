import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from app.api import app


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer dev-token-local"}


@pytest.mark.asyncio
async def test_loads_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/loads", json={"load_id": "x", "customer_id": "customer_a", "load_data": {}})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_loads_endpoint_validates_body(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/loads", json={"bad": "data"}, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_loads_endpoint_success(auth_headers):
    body = {
        "load_id": "load-test-1",
        "customer_id": "customer_a",
        "load_data": {
            "external_load_id": "FH-T1",
            "companies": {"broker": {"name": "B"}, "shipper": {"name": "S"}, "carrier": {"name": "C"}},
            "contacts": {},
            "stops": [
                {"stop_id": "p1", "type": "pickup", "address": {"line_1": "1 St", "city": "C", "state": "IL", "postal_code": "60601", "country": "US"}, "appointment": {"type": "fixed", "timezone": "America/Chicago"}, "coordinates": {"lat": 41.8, "lng": -87.6}},
                {"stop_id": "d1", "type": "delivery", "address": {"line_1": "2 St", "city": "D", "state": "TX", "postal_code": "75201", "country": "US"}, "appointment": {"type": "fixed", "timezone": "America/Chicago"}, "coordinates": {"lat": 32.7, "lng": -96.8}},
            ],
        },
        "initial_state": "on_route_to_delivery",
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.api.enqueue_event") as mock_enqueue, patch("app.api.get_db") as mock_get_db:
            mock_enqueue.return_value = None
            mock_db = MagicMock()
            mock_db.put_load.return_value = None
            mock_get_db.return_value = mock_db
            resp = await client.post("/loads", json=body, headers=auth_headers)
    assert resp.status_code == 202
    data = resp.json()
    assert "event_id" in data or "load_id" in data


@pytest.mark.asyncio
async def test_events_inbound_communication(auth_headers):
    body = {
        "event_id": "evt-test-1",
        "event_type": "inbound_communication",
        "load_id": "load-test-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:05:00Z",
        "inbound_communication": {
            "channel": "sms",
            "sender_type": "driver",
            "sender_name": "Sam",
            "content": "hello",
            "attachments": [],
        },
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.api.enqueue_event") as mock_enqueue:
            mock_enqueue.return_value = None
            resp = await client.post("/events/inbound-communication", json=body, headers=auth_headers)
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_events_tracking(auth_headers):
    body = {
        "event_id": "evt-trk-1",
        "event_type": "tracking",
        "load_id": "load-test-1",
        "customer_id": "customer_b",
        "occurred_at": "2026-05-11T17:30:00Z",
        "tracking": {
            "tracking_id": "trk-1",
            "lat": 32.777,
            "lng": -96.797,
            "distance_to_delivery_miles": 0.2,
            "ping_sequence": 1,
            "provider": "mock",
        },
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.api.enqueue_event") as mock_enqueue:
            mock_enqueue.return_value = None
            resp = await client.post("/events/tracking", json=body, headers=auth_headers)
    assert resp.status_code == 202
