from __future__ import annotations

from typing import Any


MAX_RECENT_EVENTS = 10


class SessionState:
    def __init__(self):
        self.ping_streak: int = 0
        self.recent_events: list[dict[str, Any]] = []
        self.last_eta: str | None = None
        self.attachments_seen: list[str] = []
        self.pending_followups: list[str] = []

    def add_event(self, event_summary: dict[str, Any]) -> None:
        self.recent_events.append(event_summary)
        if len(self.recent_events) > MAX_RECENT_EVENTS:
            self.recent_events = self.recent_events[-MAX_RECENT_EVENTS:]

    def increment_ping_streak(self) -> None:
        self.ping_streak += 1

    def reset_ping_streak(self) -> None:
        self.ping_streak = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ping_streak": self.ping_streak,
            "recent_events": self.recent_events,
            "last_eta": self.last_eta,
            "attachments_seen": self.attachments_seen,
            "pending_followups": self.pending_followups,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        s = cls()
        s.ping_streak = data.get("ping_streak", 0)
        s.recent_events = data.get("recent_events", [])
        s.last_eta = data.get("last_eta")
        s.attachments_seen = data.get("attachments_seen", [])
        s.pending_followups = data.get("pending_followups", [])
        return s
