import pytest
import boto3
from moto import mock_aws
from app.db import DynamoDBClient


@pytest.fixture
def dynamo_client():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="watchtower-loads",
            KeySchema=[{"AttributeName": "load_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "load_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName="watchtower-events",
            KeySchema=[
                {"AttributeName": "load_id", "KeyType": "HASH"},
                {"AttributeName": "event_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "load_id", "AttributeType": "S"},
                {"AttributeName": "event_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName="watchtower-tool-calls",
            KeySchema=[
                {"AttributeName": "load_id", "KeyType": "HASH"},
                {"AttributeName": "sort_key", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "load_id", "AttributeType": "S"},
                {"AttributeName": "sort_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        db = DynamoDBClient(endpoint_url=None)
        yield db


def test_put_and_get_load(dynamo_client):
    load = {
        "load_id": "load-1",
        "customer_id": "customer_a",
        "state": "on_route_to_delivery",
        "version": 1,
        "load_data": {"external_load_id": "FH-1"},
        "session_state": {},
    }
    dynamo_client.put_load(load)
    result = dynamo_client.get_load("load-1")
    assert result["load_id"] == "load-1"
    assert result["state"] == "on_route_to_delivery"


def test_update_load_with_version(dynamo_client):
    load = {
        "load_id": "load-1",
        "customer_id": "customer_a",
        "state": "on_route_to_delivery",
        "version": 1,
        "load_data": {},
        "session_state": {},
    }
    dynamo_client.put_load(load)
    dynamo_client.update_load("load-1", new_state="at_delivery", session_state={"ping_streak": 3}, expected_version=1)
    result = dynamo_client.get_load("load-1")
    assert result["state"] == "at_delivery"
    assert result["version"] == 2


def test_put_event(dynamo_client):
    event_record = {
        "load_id": "load-1",
        "event_id": "evt-1",
        "event_type": "tracking",
        "occurred_at": "2026-05-11T17:30:00Z",
        "payload": {},
        "selected_branch": "tracking_in_geofence",
    }
    dynamo_client.put_event(event_record)


def test_put_tool_calls(dynamo_client):
    records = [
        {"tool_call_id": "tc-1", "event_id": "evt-1", "load_id": "load-1", "tool": "send_sms", "arguments": {}, "result": {}, "created_at": "2026-05-11T17:05:01Z"},
    ]
    dynamo_client.put_tool_calls(records)


def test_get_tool_calls_for_load(dynamo_client):
    records = [
        {"tool_call_id": "tc-1", "event_id": "evt-1", "load_id": "load-1", "tool": "send_sms", "arguments": {}, "result": {}, "created_at": "2026-05-11T17:05:01Z"},
        {"tool_call_id": "tc-2", "event_id": "evt-1", "load_id": "load-1", "tool": "create_timer", "arguments": {}, "result": {}, "created_at": "2026-05-11T17:05:02Z"},
    ]
    dynamo_client.put_tool_calls(records)
    result = dynamo_client.get_tool_calls("load-1")
    assert len(result) == 2
