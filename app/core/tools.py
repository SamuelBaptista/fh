from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.models import ToolCallRecord


class ToolExecutor:
    def __init__(self, load_id: str, event_id: str):
        self._load_id = load_id
        self._event_id = event_id
        self._records: list[ToolCallRecord] = []

    def _record(self, tool: str, arguments: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        rec = ToolCallRecord(
            tool_call_id=str(uuid.uuid4()),
            event_id=self._event_id,
            load_id=self._load_id,
            tool=tool,
            arguments=arguments,
            result=result,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._records.append(rec)
        return result

    def get_records(self) -> list[ToolCallRecord]:
        return self._records

    def send_sms(self, recipient: str, message: str, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "channel": "sms", "message_id": f"sms-{uuid.uuid4().hex[:8]}"}
        return self._record("send_sms", {"recipient": recipient, "message": message}, result)

    def send_email(self, recipient: str, subject: str, body: str, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "channel": "email", "message_id": f"email-{uuid.uuid4().hex[:8]}"}
        return self._record("send_email", {"recipient": recipient, "subject": subject, "body": body}, result)

    def forward_email(self, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "channel": "email", "message_id": f"fwd-{uuid.uuid4().hex[:8]}"}
        return self._record("forward_email", {}, result)

    def send_slack_message(self, audience: str, message: str, escalation_type: str | None = None, **kwargs: Any) -> dict[str, Any]:
        args: dict[str, Any] = {"audience": audience, "message": message}
        if escalation_type:
            args["escalation_type"] = escalation_type
        result = {"ok": True, "channel": "slack", "message_id": f"slack-{uuid.uuid4().hex[:8]}"}
        return self._record("send_slack_message", args, result)

    def check_attachment(self, attachment_id: str, mock_categories: list[str] | None = None, mock_description: str = "", **kwargs: Any) -> dict[str, Any]:
        categories = mock_categories or ["other"]
        result = {"ok": True, "attachment_id": attachment_id, "categories": categories, "description": mock_description}
        return self._record("check_attachment", {"attachment_id": attachment_id}, result)

    def update_load_state(self, target_state: str, reason: str, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "previous_state": "", "new_state": target_state}
        return self._record("update_load_state", {"target_state": target_state, "reason": reason}, result)

    def update_eta(self, target_location: str, eta_utc: str, source: str, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "target_location": target_location, "eta_utc": eta_utc}
        return self._record("update_eta", {"target_location": target_location, "eta_utc": eta_utc, "source": source}, result)

    def create_timer(self, timer_type: str, fire_at_utc: str, reason: str, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "timer_id": f"timer-{uuid.uuid4().hex[:8]}"}
        return self._record("create_timer", {"timer_type": timer_type, "fire_at_utc": fire_at_utc, "reason": reason}, result)

    def cancel_timers(self, timer_type: str | None = None, **kwargs: Any) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if timer_type:
            args["timer_type"] = timer_type
        result = {"ok": True}
        return self._record("cancel_timers", args, result)

    def create_task(self, title: str, description: str, task_type: str, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "task_id": f"task-{uuid.uuid4().hex[:8]}"}
        return self._record("create_task", {"title": title, "description": description, "task_type": task_type}, result)

    def create_issue(self, title: str, description: str, issue_type: str, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "issue_id": f"issue-{uuid.uuid4().hex[:8]}"}
        return self._record("create_issue", {"title": title, "description": description, "issue_type": issue_type}, result)

    def get_load_info(self, field: str, load_data: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        value = self._resolve_field(field, load_data or {})
        if value is None:
            result = {"ok": False, "field": field, "error": "missing"}
        else:
            result = {"ok": True, "field": field, "value": value}
        return self._record("get_load_info", {"field": field}, result)

    def validate_eta(self, raw_eta: str, delivery_timezone: str, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "eta_utc": "2026-05-11T19:30:00Z", "is_plausible": True}
        return self._record("validate_eta", {"raw_eta": raw_eta, "delivery_timezone": delivery_timezone}, result)

    def get_appointment_time(self, stop_type: str, **kwargs: Any) -> dict[str, Any]:
        result = {"ok": True, "stop_type": stop_type, "appointment": {"type": "fixed", "start_utc": "2026-05-11T20:00:00Z", "timezone": "America/Chicago"}}
        return self._record("get_appointment_time", {"stop_type": stop_type}, result)

    @staticmethod
    def _resolve_field(field: str, load_data: dict[str, Any]) -> str | None:
        if field == "delivery_address":
            stops = load_data.get("stops", [])
            for stop in stops:
                if stop.get("type") == "delivery":
                    addr = stop.get("address", {})
                    parts = [addr.get("line_1", ""), addr.get("line_2", ""), addr.get("city", ""), addr.get("state", ""), addr.get("postal_code", "")]
                    return ", ".join(p for p in parts if p)
            return None
        if field == "receiver_phone":
            stops = load_data.get("stops", [])
            for stop in stops:
                if stop.get("type") == "delivery":
                    refs = stop.get("reference_numbers", {})
                    return refs.get("receiver_phone")
            return None
        return None
