import pytest
from app.llm import LLMClient, LLMResponse


@pytest.mark.asyncio
async def test_llm_client_mock_mode():
    client = LLMClient(mode="mock")
    response = await client.complete(
        system_prompt="You are a freight agent.",
        user_message="What should I do?",
        load_id="load-1",
        event_id="evt-1",
    )
    assert isinstance(response, LLMResponse)
    assert response.content != ""
    assert response.model == "mock"


@pytest.mark.asyncio
async def test_llm_client_records_metadata():
    client = LLMClient(mode="mock")
    response = await client.complete(
        system_prompt="test",
        user_message="test",
        load_id="load-1",
        event_id="evt-1",
    )
    assert response.duration_ms >= 0
    assert response.model == "mock"
