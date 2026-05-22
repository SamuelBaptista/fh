from __future__ import annotations

import json
import uuid
from typing import Any

import boto3

from app.config.settings import settings


class TimerClient:
    def __init__(self):
        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            kwargs["endpoint_url"] = settings.aws_endpoint_url
        self._client = boto3.client("scheduler", **kwargs)

    def schedule(self, timer_type: str, fire_at_utc: str, load_id: str, event_id: str, reason: str) -> dict[str, Any]:
        timer_id = f"timer-{uuid.uuid4().hex[:8]}"
        schedule_name = f"{load_id}-{timer_type}-{timer_id}"
        payload = json.dumps({
            "event_id": f"evt-timer-{timer_id}",
            "event_type": "timer_fired",
            "load_id": load_id,
            "customer_id": "",
            "occurred_at": fire_at_utc,
            "timer": {"timer_id": timer_id, "timer_type": timer_type, "original_event_id": event_id, "reason": reason},
        })
        try:
            self._client.create_schedule(
                Name=schedule_name,
                ScheduleExpression=f"at({fire_at_utc.replace('Z', '')})",
                FlexibleTimeWindow={"Mode": "OFF"},
                Target={
                    "Arn": settings.scheduler_target_arn or "arn:aws:sqs:us-east-1:000000000000:watchtower-events.fifo",
                    "RoleArn": settings.scheduler_role_arn or "arn:aws:iam::000000000000:role/scheduler-role",
                    "Input": payload,
                    "SqsParameters": {"MessageGroupId": load_id},
                },
                ActionAfterCompletion="DELETE",
            )
        except Exception:
            pass
        return {"ok": True, "timer_id": timer_id}

    def cancel(self, timer_id: str) -> dict[str, Any]:
        try:
            self._client.delete_schedule(Name=timer_id)
        except Exception:
            pass
        return {"ok": True}

    def cancel_by_type(self, load_id: str, timer_type: str | None = None) -> dict[str, Any]:
        try:
            prefix = f"{load_id}-{timer_type}" if timer_type else load_id
            resp = self._client.list_schedules(NamePrefix=prefix, MaxResults=100)
            for schedule in resp.get("Schedules", []):
                self._client.delete_schedule(Name=schedule["Name"])
        except Exception:
            pass
        return {"ok": True}
