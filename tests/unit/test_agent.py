import pytest
from app.agent.agent import Agent, AgentDecision
from app.config.customer import get_customer_policy
from app.core.session import SessionState


@pytest.fixture
def agent():
    return Agent(llm_mode="mock")


@pytest.mark.asyncio
async def test_agent_returns_decision(agent):
    policy = get_customer_policy("customer_a")
    session = SessionState()
    event = {
        "event_id": "evt-1",
        "event_type": "inbound_communication",
        "load_id": "load-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:05:00Z",
        "inbound_communication": {
            "channel": "sms",
            "sender_type": "driver",
            "sender_name": "Sam",
            "content": "What's the delivery address?",
            "attachments": [],
        },
    }
    load_data = {
        "stops": [
            {"type": "delivery", "address": {"line_1": "456 Delivery St", "city": "Dallas", "state": "TX", "postal_code": "75201"}}
        ]
    }

    decision = await agent.decide(event, session, policy, load_data)
    assert isinstance(decision, AgentDecision)
    assert decision.intent != ""
    assert decision.branch != ""


@pytest.mark.asyncio
async def test_agent_builds_system_prompt(agent):
    policy = get_customer_policy("customer_a")
    prompt = agent.build_system_prompt(policy, "on_route_to_delivery")
    assert "customer_a" in prompt
    assert "ETA" in prompt or "geofence" in prompt.lower() or "Geofence" in prompt
