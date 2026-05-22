from __future__ import annotations

from typing import Any

from app.agent import Agent, AgentDecision
from app.customer import get_customer_policy
from app.dispatcher import Dispatcher
from app.observability import Logger, JsonlWriter
from app.session import SessionState
from app.tools import ToolExecutor


class Worker:
    def __init__(self, llm_mode: str | None = None):
        self._dispatcher = Dispatcher()
        self._agent = Agent(llm_mode=llm_mode)
        self._jsonl = JsonlWriter()

    async def process_event(self, event: dict[str, Any], load_row: dict[str, Any]) -> dict[str, Any]:
        load_id = event["load_id"]
        event_id = event["event_id"]
        customer_id = event.get("customer_id") or load_row["customer_id"]

        log = Logger(load_id=load_id, event_id=event_id)
        log.info("event.received", event_type=event["event_type"], customer_id=customer_id)

        policy = get_customer_policy(customer_id)
        session = SessionState.from_dict(load_row.get("session_state") or {})
        load_data = load_row.get("load_data", {})
        current_state = load_row.get("state", "on_route_to_delivery")

        executor = ToolExecutor(load_id=load_id, event_id=event_id)

        dispatch_result = self._dispatcher.route(event, session, policy)
        log.info("event.dispatched", branch=dispatch_result.branch, requires_agent=dispatch_result.requires_agent)

        new_state = current_state
        all_tool_calls: list[dict[str, Any]] = []

        if not dispatch_result.requires_agent:
            # Execute deterministic tool calls from dispatcher
            for tc in dispatch_result.tool_calls:
                tool_name = tc["tool"]
                tool_args = tc.get("arguments", {})
                getattr(executor, tool_name)(**tool_args)

            if dispatch_result.state_transition:
                new_state = dispatch_result.state_transition

            all_tool_calls = [r.model_dump() for r in executor.get_records()]
        else:
            # Agent handles classification + tool decisions
            decision = await self._agent.decide(event, session, policy, load_data)
            log.info("agent.decision", intent=decision.intent, branch=decision.branch, reasoning=decision.reasoning, model=decision.model_used)

            # Execute agent-planned tool calls
            for tc in decision.tool_calls:
                tool_name = tc["tool"]
                tool_args = tc.get("arguments", {})
                # Handle special cases
                if tool_name == "check_attachment":
                    att_id = tool_args.get("attachment_id", "")
                    mock_class = self._find_attachment_classification(event, att_id)
                    executor.check_attachment(
                        attachment_id=att_id,
                        mock_categories=mock_class.get("categories", ["other"]),
                        mock_description=mock_class.get("description", ""),
                    )
                elif tool_name == "get_load_info":
                    executor.get_load_info(field=tool_args.get("field", ""), load_data=load_data)
                elif hasattr(executor, tool_name):
                    getattr(executor, tool_name)(**tool_args)

            # Check for state transitions in agent tool calls
            for rec in executor.get_records():
                if rec.tool == "update_load_state":
                    new_state = rec.arguments.get("target_state", new_state)

            all_tool_calls = [r.model_dump() for r in executor.get_records()]
            dispatch_result.branch = decision.branch

        # Update session
        session.add_event({"event_id": event_id, "type": event["event_type"], "branch": dispatch_result.branch})

        # Write JSONL trace
        for tc in all_tool_calls:
            self._jsonl.write(event_id, tc)

        log.info("event.processed", branch=dispatch_result.branch, new_state=new_state, tool_count=len(all_tool_calls))

        return {
            "branch": dispatch_result.branch,
            "state": new_state,
            "tool_calls": all_tool_calls,
            "session_state": session.to_dict(),
        }

    @staticmethod
    def _find_attachment_classification(event: dict[str, Any], attachment_id: str) -> dict[str, Any]:
        comm = event.get("inbound_communication", {})
        for att in comm.get("attachments", []):
            if att.get("attachment_id") == attachment_id:
                return att.get("mock_classification", {})
        return {}
