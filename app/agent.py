from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.customer import CustomerPolicy
from app.llm import LLMClient
from app.session import SessionState


SOPS_DIR = Path(__file__).parent.parent / "assets" / "sops"


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
    ) -> AgentDecision:
        load_state = "on_route_to_delivery"
        system_prompt = self.build_system_prompt(policy, load_state)
        user_message = self._build_user_message(event, session, load_data)

        response = await self._llm.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            load_id=event.get("load_id", ""),
            event_id=event.get("event_id", ""),
        )

        decision = self._parse_response(response.content)
        decision.model_used = response.model
        return decision

    def build_system_prompt(self, policy: CustomerPolicy, load_state: str) -> str:
        sop_file = "on_route_to_delivery_eta_checkpoint.md" if load_state == "on_route_to_delivery" else "confirm_delivery.md"
        sop_path = SOPS_DIR / sop_file
        sop_content = sop_path.read_text() if sop_path.exists() else ""

        return f"""You are Robin, the FreightHero AI agent. Process this event and decide what action to take.

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
- Match the inbound channel for driver-facing replies.
- Keep messages short and operational.
- Do not make up missing information.
- Do not approve payments or detention claims.
- Broker messages are already filtered out before reaching you.

## Response Format
Respond with a JSON object:
{{
    "intent": "<classification: load_information_question|driver_provides_eta|arrival_confirmation|operational_issue|delivery_confirmed_without_pod|unloading_started|unloading_not_started|attachment_handling|first_arrival_contact|no_action|acknowledge>",
    "branch": "<sop_branch_name>",
    "reasoning": "<one sentence explaining why>",
    "tool_calls": [
        {{"tool": "<tool_name>", "arguments": {{...}}}}
    ],
    "draft_message": "<message text if sending a reply to driver/dispatcher>"
}}

Available tools: send_sms, send_email, forward_email, send_slack_message, check_attachment, update_load_state, update_eta, create_timer, cancel_timers, create_task, create_issue, get_load_info, validate_eta, get_appointment_time
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

    def _parse_response(self, content: str) -> AgentDecision:
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(content)
            return AgentDecision(
                intent=data.get("intent", "unknown"),
                branch=data.get("branch", "unknown"),
                reasoning=data.get("reasoning", ""),
                tool_calls=data.get("tool_calls", []),
                draft_message=data.get("draft_message", ""),
            )
        except (json.JSONDecodeError, KeyError, IndexError):
            return AgentDecision(
                intent="parse_error",
                branch="error",
                reasoning=f"Failed to parse LLM response: {content[:200]}",
            )
