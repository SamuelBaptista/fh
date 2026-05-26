from __future__ import annotations

from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key, Attr

from app.config.settings import settings


class DynamoDBClient:
    def __init__(self, endpoint_url: str | None = "USE_SETTINGS"):
        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if endpoint_url == "USE_SETTINGS":
            if settings.aws_endpoint_url:
                kwargs["endpoint_url"] = settings.aws_endpoint_url
        elif endpoint_url is not None:
            kwargs["endpoint_url"] = endpoint_url
        self._resource = boto3.resource("dynamodb", **kwargs)
        self._loads = self._resource.Table(settings.dynamodb_loads_table)
        self._events = self._resource.Table(settings.dynamodb_events_table)
        self._tool_calls = self._resource.Table(settings.dynamodb_tool_calls_table)

    def put_load(self, load: dict[str, Any]) -> None:
        item = self._serialize(load)
        self._loads.put_item(Item=item)

    def get_load(self, load_id: str) -> dict[str, Any] | None:
        resp = self._loads.get_item(Key={"load_id": load_id}, ConsistentRead=True)
        item = resp.get("Item")
        return self._deserialize(item) if item else None

    def update_load(self, load_id: str, new_state: str, session_state: dict, expected_version: int) -> None:
        self._loads.update_item(
            Key={"load_id": load_id},
            UpdateExpression="SET #state = :s, session_state = :ss, version = :nv",
            ConditionExpression=Attr("version").eq(expected_version),
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":s": new_state,
                ":ss": self._serialize(session_state),
                ":nv": expected_version + 1,
            },
        )

    def put_event(self, event_record: dict[str, Any]) -> None:
        item = self._serialize(event_record)
        self._events.put_item(Item=item)

    def put_tool_calls(self, records: list[dict[str, Any]]) -> None:
        with self._tool_calls.batch_writer() as batch:
            for rec in records:
                item = self._serialize(rec)
                item["sort_key"] = f"{rec['created_at']}#{rec['tool_call_id']}"
                batch.put_item(Item=item)

    def get_tool_calls(self, load_id: str, event_id: str | None = None) -> list[dict[str, Any]]:
        resp = self._tool_calls.query(KeyConditionExpression=Key("load_id").eq(load_id))
        items = [self._deserialize(i) for i in resp.get("Items", [])]
        if event_id:
            items = [i for i in items if i.get("event_id") == event_id]
        return items

    @staticmethod
    def _serialize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: DynamoDBClient._serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [DynamoDBClient._serialize(i) for i in obj]
        if isinstance(obj, float):
            return Decimal(str(obj))
        return obj

    @staticmethod
    def _deserialize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: DynamoDBClient._deserialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [DynamoDBClient._deserialize(i) for i in obj]
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return obj
