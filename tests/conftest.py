import pytest


@pytest.fixture
def base_load():
    """The base load from test-cases.json."""
    return {
        "load_id": "load-visible-001",
        "customer_id": "customer_a",
        "state": "on_route_to_delivery",
        "version": 1,
        "load_data": {
            "external_load_id": "FH-2026-001",
            "po_number": "PO-7788",
            "instructions": "Receiver requires check-in at guard shack.",
            "companies": {
                "broker": {"name": "Example Broker", "uuid": "broker-example"},
                "shipper": {"name": "Example Shipper", "uuid": "shipper-example"},
                "carrier": {"name": "Example Carrier", "uuid": "carrier-example"},
            },
            "contacts": {
                "driver": {"first_name": "Sam", "last_name": "Driver", "phone": "+15555550100", "uuid": "driver-sam"},
                "dispatcher": {"first_name": "Dana", "last_name": "Dispatch", "email": "dispatch@example.com", "uuid": "dispatcher-dana"},
                "broker": {"first_name": "Blake", "last_name": "Broker", "email": "broker@example.com", "uuid": "broker-contact"},
            },
            "stops": [
                {
                    "stop_id": "pickup-1", "type": "pickup", "status": "departed",
                    "address": {"line_1": "123 Pickup Ave", "city": "Chicago", "state": "IL", "postal_code": "60601", "country": "US"},
                    "appointment": {"type": "fixed", "start_utc": "2026-05-10T14:00:00Z", "timezone": "America/Chicago"},
                    "coordinates": {"lat": 41.8781, "lng": -87.6298},
                    "reference_numbers": {"pickup": "PU-123"},
                },
                {
                    "stop_id": "delivery-1", "type": "delivery", "status": "en_route",
                    "address": {"line_1": "456 Delivery St", "line_2": "Dock 4", "city": "Dallas", "state": "TX", "postal_code": "75201", "country": "US"},
                    "appointment": {"type": "fixed", "start_utc": "2026-05-11T20:00:00Z", "timezone": "America/Chicago"},
                    "coordinates": {"lat": 32.7767, "lng": -96.7970},
                    "reference_numbers": {"delivery": "DEL-456", "receiver_phone": "+15555550200"},
                },
            ],
        },
        "session_state": {},
    }
