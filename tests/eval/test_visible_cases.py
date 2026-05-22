import os
import copy

import pytest

from app.worker import Worker


def apply_patch(load_data: dict, patch: dict) -> dict:
    data = copy.deepcopy(load_data)
    for key, value in patch.items():
        parts = key.split(".")
        obj = data
        for i, part in enumerate(parts[:-1]):
            if "[" in part:
                name, idx = part.split("[")
                idx = int(idx.rstrip("]"))
                obj = obj[name][idx]
            else:
                obj = obj[part]
        final = parts[-1]
        if "[" in final:
            name, idx = final.split("[")
            idx = int(idx.rstrip("]"))
            obj[name][idx] = value
        else:
            obj[final] = value
    return data


def make_load_row(base_load: dict, case: dict) -> dict:
    load_data = copy.deepcopy(base_load["load_data"])
    if "load_data_patch" in case:
        load_data = apply_patch(load_data, case["load_data_patch"])
    return {
        "load_id": base_load["load_id"],
        "customer_id": case.get("customer_id", base_load.get("customer_id", "customer_a")),
        "state": case.get("initial_state", base_load.get("initial_state", "on_route_to_delivery")),
        "version": 1,
        "load_data": load_data,
        "session_state": {},
    }


@pytest.fixture
def worker():
    return Worker(llm_mode="mock")


@pytest.mark.asyncio
async def test_3k_broker_email_ignore(worker, test_cases, base_load_data):
    case = next(c for c in test_cases["cases"] if c["id"] == "3k_broker_email_ignore")
    load_row = make_load_row(base_load_data, case)
    result = None
    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]
    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"
    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
async def test_3h_tracking_three_pings(worker, test_cases, base_load_data):
    case = next(c for c in test_cases["cases"] if c["id"] == "3h_fresh_tracking_three_pings_in_geofence")
    load_row = make_load_row(base_load_data, case)
    result = None
    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]
    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
        if "arguments" in req:
            matching = [tc for tc in result["tool_calls"] if tc["tool"] == req["tool"]]
            for key, val in req["arguments"].items():
                assert any(tc["arguments"].get(key) == val for tc in matching), f"Tool {req['tool']} missing arg {key}={val}"
    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"
    assert result["state"] == expected["expected_state"]


MOCK_MODE = os.environ.get("LLM_MODE", "mock") == "mock"


@pytest.mark.asyncio
@pytest.mark.xfail(condition=MOCK_MODE, reason="Requires live LLM for agent classification")
async def test_3b_load_question_found(worker, test_cases, base_load_data):
    case = next(c for c in test_cases["cases"] if c["id"] == "3b_load_question_found")
    load_row = make_load_row(base_load_data, case)
    result = None
    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]
    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
        if "contains" in req:
            matching = [tc for tc in result["tool_calls"] if tc["tool"] == req["tool"]]
            assert any(req["contains"] in str(tc["arguments"]) for tc in matching), f"Tool {req['tool']} missing text '{req['contains']}'"
    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"
    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
@pytest.mark.xfail(condition=MOCK_MODE, reason="Requires live LLM for agent classification")
async def test_3c_load_question_missing(worker, test_cases, base_load_data):
    case = next(c for c in test_cases["cases"] if c["id"] == "3c_load_question_missing")
    load_row = make_load_row(base_load_data, case)
    result = None
    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]
    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"
    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
@pytest.mark.xfail(condition=MOCK_MODE, reason="Requires live LLM for agent classification")
async def test_3d_truck_broken(worker, test_cases, base_load_data):
    case = next(c for c in test_cases["cases"] if c["id"] == "3d_truck_broken")
    load_row = make_load_row(base_load_data, case)
    result = None
    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]
    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"
    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
@pytest.mark.xfail(condition=MOCK_MODE, reason="Requires live LLM for agent classification")
async def test_3f_driver_provides_eta(worker, test_cases, base_load_data):
    case = next(c for c in test_cases["cases"] if c["id"] == "3f_driver_provides_eta")
    load_row = make_load_row(base_load_data, case)
    result = None
    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]
    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"
    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
@pytest.mark.xfail(condition=MOCK_MODE, reason="Requires live LLM for agent classification")
async def test_3i_driver_says_arrived(worker, test_cases, base_load_data):
    case = next(c for c in test_cases["cases"] if c["id"] == "3i_not_tracking_driver_says_arrived")
    load_row = make_load_row(base_load_data, case)
    result = None
    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]
    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
        if "contains" in req:
            matching = [tc for tc in result["tool_calls"] if tc["tool"] == req["tool"]]
            assert any(req["contains"].lower() in str(tc["arguments"]).lower() for tc in matching), f"Tool {req['tool']} missing text '{req['contains']}'"
    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"
    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
@pytest.mark.xfail(condition=MOCK_MODE, reason="Requires live LLM for agent classification")
async def test_3j_driver_sends_pod(worker, test_cases, base_load_data):
    case = next(c for c in test_cases["cases"] if c["id"] == "3j_not_tracking_driver_sends_pod")
    load_row = make_load_row(base_load_data, case)
    result = None
    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]
    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"
    assert result["state"] == expected["expected_state"]
