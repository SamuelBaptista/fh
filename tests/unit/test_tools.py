import pytest
from app.core.tools import ToolExecutor


@pytest.fixture
def executor():
    return ToolExecutor(load_id="load-1", event_id="evt-1")


def test_send_sms(executor):
    result = executor.send_sms(recipient="driver", message="ETA updated")
    assert result["ok"] is True
    assert result["channel"] == "sms"
    assert "message_id" in result


def test_send_email(executor):
    result = executor.send_email(recipient="dispatcher", subject="Update", body="ETA info")
    assert result["ok"] is True
    assert result["channel"] == "email"


def test_forward_email(executor):
    result = executor.forward_email()
    assert result["ok"] is True
    assert result["channel"] == "email"


def test_send_slack_message(executor):
    result = executor.send_slack_message(audience="broker", message="POD received")
    assert result["ok"] is True
    assert result["channel"] == "slack"


def test_check_attachment(executor):
    result = executor.check_attachment(
        attachment_id="att-1",
        mock_categories=["document_pod"],
        mock_description="Signed POD"
    )
    assert result["ok"] is True
    assert result["categories"] == ["document_pod"]


def test_update_load_state(executor):
    result = executor.update_load_state(target_state="at_delivery", reason="3 pings in geofence")
    assert result["ok"] is True
    assert result["new_state"] == "at_delivery"


def test_update_eta(executor):
    result = executor.update_eta(
        target_location="delivery",
        eta_utc="2026-05-11T19:00:00Z",
        source="driver"
    )
    assert result["ok"] is True


def test_create_timer(executor):
    result = executor.create_timer(
        timer_type="eta_followup",
        fire_at_utc="2026-05-11T20:00:00Z",
        reason="follow up on ETA"
    )
    assert result["ok"] is True
    assert "timer_id" in result


def test_cancel_timers(executor):
    result = executor.cancel_timers(timer_type="eta_followup")
    assert result["ok"] is True


def test_create_task(executor):
    result = executor.create_task(
        title="Missing receiver phone",
        description="Driver asked, not in load data",
        task_type="missing_load_info"
    )
    assert result["ok"] is True
    assert "task_id" in result


def test_create_issue(executor):
    result = executor.create_issue(
        title="Truck breakdown",
        description="Driver reports breakdown on I-35",
        issue_type="equipment_failure"
    )
    assert result["ok"] is True
    assert "issue_id" in result


def test_tool_calls_recorded(executor):
    executor.send_sms(recipient="driver", message="hi")
    executor.create_timer(timer_type="pod_followup", fire_at_utc="2026-05-11T21:00:00Z", reason="pod")
    records = executor.get_records()
    assert len(records) == 2
    assert records[0].tool == "send_sms"
    assert records[1].tool == "create_timer"
