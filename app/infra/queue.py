from __future__ import annotations

import json
import hashlib
from typing import Any

import boto3

from app.config.settings import settings


class SQSClient:
    def __init__(self, endpoint_url: str | None = "USE_SETTINGS"):
        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if endpoint_url == "USE_SETTINGS":
            if settings.aws_endpoint_url:
                kwargs["endpoint_url"] = settings.aws_endpoint_url
        elif endpoint_url is not None:
            kwargs["endpoint_url"] = endpoint_url
        self._client = boto3.client("sqs", **kwargs)
        self._queue_url = settings.sqs_queue_url

    def send_event(self, event: dict[str, Any], load_id: str) -> str:
        body = json.dumps(event, default=str)
        dedup_id = hashlib.sha256(body.encode()).hexdigest()[:128]
        resp = self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=body,
            MessageGroupId=load_id,
            MessageDeduplicationId=dedup_id,
        )
        return resp["MessageId"]
