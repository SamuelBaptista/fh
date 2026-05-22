from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.customer import CustomerPolicy
from app.llm import LLMClient
from app.session import SessionState


SOPS_DIR = Path(__file__).parent.parent / "assets" / "sops"

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "send_sms",
            "description": "Send an SMS message to the driver or dispatcher.",
            "parameters": {
                "type": "object",
                "required": ["recipient", "message"],
                "properties": {
                    "recipient": {"type": "string", "enum": ["driver", "dispatcher"]},
                    "message": {"type": "string", "description": "Short operational message text"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send or reply to an operational email.",
            "parameters": {
                "type": "object",
                "required": ["recipient", "subject", "body"],
                "properties": {
                    "recipient": {"type": "string", "enum": ["driver", "dispatcher", "carrier_team", "main_thread"]},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forward_email",
            "description": "Forward the current email and its attachments to the broker's special email address.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_slack_message",
            "description": "Send internal or broker-visible Slack-style notification.",
            "parameters": {
                "type": "object",
                "required": ["audience", "message"],
                "properties": {
                    "audience": {"type": "string", "enum": ["internal", "broker", "customer"]},
                    "message": {"type": "string"},
                    "escalation_type": {"type": "string", "description": "Optional escalation category"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_attachment",
            "description": "Classify one attachment by its ID.",
            "parameters": {
                "type": "object",
                "required": ["attachment_id"],
                "properties": {
                    "attachment_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_load_state",
            "description": "Update the load milestone state.",
            "parameters": {
                "type": "object",
                "required": ["target_state", "reason"],
                "properties": {
                    "target_state": {"type": "string", "enum": ["on_route_to_delivery", "at_delivery", "delivered", "pod_collected"]},
                    "reason": {"type": "string", "description": "Short reason for state change"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_eta",
            "description": "Store a driver-provided ETA.",
            "parameters": {
                "type": "object",
                "required": ["target_location", "eta_utc", "source"],
                "properties": {
                    "target_location": {"type": "string", "enum": ["delivery"]},
                    "eta_utc": {"type": "string", "description": "ISO 8601 UTC timestamp"},
                    "source": {"type": "string", "enum": ["driver", "dispatcher", "carrier", "system"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_timer",
            "description": "Schedule a follow-up timer.",
            "parameters": {
                "type": "object",
                "required": ["timer_type", "fire_at_utc", "reason"],
                "properties": {
                    "timer_type": {"type": "string", "enum": ["eta_followup", "pod_followup", "delivery_status_followup", "attachment_clarification"]},
                    "fire_at_utc": {"type": "string", "description": "ISO 8601 UTC timestamp when timer should fire"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_timers",
            "description": "Cancel timers for this load, optionally by type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timer_type": {"type": "string", "enum": ["eta_followup", "pod_followup", "delivery_status_followup", "attachment_clarification"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a non-urgent human follow-up task.",
            "parameters": {
                "type": "object",
                "required": ["title", "description", "task_type"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "task_type": {"type": "string", "enum": ["missing_load_info", "pod_review", "lumper_review", "manual_followup", "other"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_issue",
            "description": "Create an urgent operational issue.",
            "parameters": {
                "type": "object",
                "required": ["title", "description", "issue_type"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "issue_type": {"type": "string", "enum": ["equipment_failure", "delivery_delay", "facility_problem", "other"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_load_info",
            "description": "Look up a specific field from the persisted load data.",
            "parameters": {
                "type": "object",
                "required": ["field"],
                "properties": {
                    "field": {"type": "string", "enum": ["delivery_address", "receiver_phone", "delivery_reference", "driver_contact"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_eta",
            "description": "Validate and normalize a driver-provided ETA string.",
            "parameters": {
                "type": "object",
                "required": ["raw_eta", "delivery_timezone"],
                "properties": {
                    "raw_eta": {"type": "string", "description": "The raw ETA text from the driver"},
                    "delivery_timezone": {"type": "string", "description": "IANA timezone string for the delivery stop"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_appointment_time",
            "description": "Return the appointment time for a stop.",
            "parameters": {
                "type": "object",
                "required": ["stop_type"],
                "properties": {
                    "stop_type": {"type": "string", "enum": ["pickup", "delivery"]},
                },
            },
        },
    },
]


@dataclass
class AgentDecision:
    intent: str
    branch: str
    reasoning: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    draft_message: str = ""
    model_used: str = ""


class Agent:
    def __init__(self, llm_mode: str | None = None):
        self._llm = LLMClient(mode=llm_mode)

    async def decide(
        self,
        event: dict[str, Any],
        session: SessionState,
        policy: CustomerPolicy,
        load_data: dict[str, Any],
        tool_executor_fn: Any = None,
    ) -> AgentDecision:
        load_state = "on_route_to_delivery"
        system_prompt = self.build_system_prompt(policy, load_state)
        user_message = self._build_user_message(event, session, load_data)

        if tool_executor_fn and self._llm._mode != "mock":
            response = await self._llm.complete_with_tool_loop(
                system_prompt=system_prompt,
                user_message=user_message,
                tools=TOOLS_SCHEMA,
                tool_executor=tool_executor_fn,
                load_id=event.get("load_id", ""),
                event_id=event.get("event_id", ""),
            )
        else:
            response = await self._llm.complete(
                system_prompt=system_prompt,
                user_message=user_message,
                load_id=event.get("load_id", ""),
                event_id=event.get("event_id", ""),
                tools=TOOLS_SCHEMA,
            )

        decision = self._parse_response(response)
        decision.model_used = response.model
        return decision

    def build_system_prompt(self, policy: CustomerPolicy, load_state: str) -> str:
        sop_file = "on_route_to_delivery_eta_checkpoint.md" if load_state == "on_route_to_delivery" else "confirm_delivery.md"
        sop_path = SOPS_DIR / sop_file
        sop_content = sop_path.read_text() if sop_path.exists() else ""

        return f"""You are Robin, the FreightHero AI agent. Process the event and call the appropriate tools.

## Current Workflow SOP
{sop_content}

## Customer Policy ({policy.customer_id})
- Escalation channels: {', '.join(policy.escalation_channels)}
- POD validation: {policy.pod_validation}
- POD received visibility: {policy.pod_received_visibility}
- Delivered without POD visibility: {policy.delivered_no_pod_visibility}
- Missing info visibility: {policy.missing_info_visibility}
- ETA follow-up timer: {policy.eta_followup_minutes} minutes
- Lumper strategy: {policy.lumper_strategy}
- First arrival message: {policy.first_arrival_message}
- Geofence radius: {policy.geofence_miles} miles

## Communication Rules
- Match the inbound channel for driver-facing replies (SMS reply to SMS, email reply to email).
- Keep messages short and operational.
- Do not make up missing information — use get_load_info to check first.
- Do not approve payments or detention claims.
- Broker messages are already filtered before reaching you.

## Instructions
- Call the tools needed to handle this event per the SOP and customer policy.
- If the driver asks for information, use get_load_info first. If available, reply with the info. If missing, create a task and notify per customer policy.
- If the driver reports arrival, update state to at_delivery, cancel existing timers, and send the customer's first arrival message.
- If the driver sends an attachment, use check_attachment to classify it before acting.
- If the driver provides ETA, use update_eta and create an eta_followup timer per customer policy.
- If the driver reports an operational problem, create an issue and briefly acknowledge.
- If delivering without POD, update state and ask for POD.
- Always include a brief text explanation in your response content about your reasoning.
"""

    def _build_user_message(self, event: dict[str, Any], session: SessionState, load_data: dict[str, Any]) -> str:
        parts = [
            f"## Event\n```json\n{json.dumps(event, indent=2)}\n```",
            f"\n## Load Data\n```json\n{json.dumps(load_data, indent=2)}\n```",
        ]
        if session.recent_events:
            parts.append(f"\n## Recent Session Events (last {len(session.recent_events)})\n```json\n{json.dumps(session.recent_events, indent=2)}\n```")
        if session.last_eta:
            parts.append(f"\n## Last Known ETA: {session.last_eta}")
        return "\n".join(parts)

    def _parse_response(self, response: Any) -> AgentDecision:
        # Tool calls come structured from the API
        tool_calls = response.tool_calls

        # Parse intent/reasoning from content (if model provides it)
        content = response.content or ""
        intent = "unknown"
        branch = "unknown"
        reasoning = content[:200] if content else ""

        # Try to extract structured info from content if present
        try:
            if content.strip().startswith("{"):
                data = json.loads(content)
                intent = data.get("intent", intent)
                branch = data.get("branch", branch)
                reasoning = data.get("reasoning", reasoning)
        except (json.JSONDecodeError, KeyError):
            pass

        # Infer intent from tool calls if not in content
        if intent == "unknown" and tool_calls:
            first_tool = tool_calls[0]["tool"]
            intent_map = {
                "send_sms": "acknowledge",
                "send_email": "acknowledge",
                "get_load_info": "load_information_question",
                "update_eta": "driver_provides_eta",
                "update_load_state": "arrival_confirmation",
                "create_issue": "operational_issue",
                "create_task": "load_information_question",
                "check_attachment": "attachment_handling",
                "create_timer": "driver_provides_eta",
                "cancel_timers": "arrival_confirmation",
            }
            intent = intent_map.get(first_tool, "acknowledge")
            branch = first_tool

        return AgentDecision(
            intent=intent,
            branch=branch,
            reasoning=reasoning,
            tool_calls=tool_calls,
        )
