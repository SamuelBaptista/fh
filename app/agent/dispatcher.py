from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config.customer import CustomerPolicy
from app.core.session import SessionState


@dataclass
class DispatchResult:
    branch: str
    requires_agent: bool = False
    state_transition: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""


class Dispatcher:
    def route(self, event: dict[str, Any], session: SessionState, policy: CustomerPolicy) -> DispatchResult:
        event_type = event.get("event_type")

        if event_type == "tracking":
            return self._handle_tracking(event, session, policy)

        if event_type == "inbound_communication":
            comm = event.get("inbound_communication", {})
            sender_type = comm.get("sender_type", "")

            if sender_type == "broker":
                return DispatchResult(
                    branch="broker_ignored",
                    reason="Broker messages are ignored per SOP",
                )

            return DispatchResult(
                branch="agent_required",
                requires_agent=True,
                reason=f"Inbound {comm.get('channel')} from {sender_type} requires agent classification",
            )

        if event_type == "load_update":
            return DispatchResult(
                branch="agent_required",
                requires_agent=True,
                reason="Load update requires agent evaluation",
            )

        if event_type == "submit_task":
            return DispatchResult(
                branch="agent_required",
                requires_agent=True,
                reason=f"Task instruction: {event.get('task_instruction_type')}",
            )

        return DispatchResult(branch="unknown_event_type", reason=f"Unrecognized event type: {event_type}")

    def _handle_tracking(self, event: dict[str, Any], session: SessionState, policy: CustomerPolicy) -> DispatchResult:
        tracking = event.get("tracking", {})
        distance = tracking.get("distance_to_delivery_miles", float("inf"))

        if distance > policy.geofence_miles:
            session.reset_ping_streak()
            return DispatchResult(
                branch="tracking_outside_geofence",
                reason=f"Distance {distance}mi > geofence {policy.geofence_miles}mi",
            )

        session.increment_ping_streak()

        if session.ping_streak >= 3:
            tool_calls = [
                {"tool": "update_load_state", "arguments": {"target_state": "at_delivery", "reason": f"{session.ping_streak} consecutive pings inside {policy.geofence_miles}mi geofence"}},
                {"tool": "cancel_timers", "arguments": {}},
            ]
            return DispatchResult(
                branch="tracking_arrival_confirmed",
                state_transition="at_delivery",
                tool_calls=tool_calls,
                reason=f"{session.ping_streak} pings inside geofence confirms arrival",
            )

        return DispatchResult(
            branch="tracking_in_geofence",
            reason=f"Ping {session.ping_streak}/3 inside geofence ({distance}mi <= {policy.geofence_miles}mi)",
        )
