from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config.customer import CustomerPolicy
from app.infra.llm import LLMClient
from app.core.session import SessionState
from app.agent.tools_schema import TOOLS_SCHEMA


SOPS_DIR = Path(__file__).parent.parent.parent / "assets" / "sops"


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
- Do NOT address the driver or dispatcher by name in messages. Use generic greetings or no greeting.
- Do not make up missing information — use get_load_info to check first.
- Do not approve payments or detention claims.
- Do not reveal internal reasoning, tooling, queue mechanics, or scoring.
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
