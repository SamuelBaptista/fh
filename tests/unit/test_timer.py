import pytest
from unittest.mock import MagicMock, patch
from app.timer import TimerClient


def test_schedule_timer():
    with patch("app.timer.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        mock_client.create_schedule.return_value = {"ScheduleArn": "arn:test"}
        tc = TimerClient()
        tc._client = mock_client
        result = tc.schedule(timer_type="eta_followup", fire_at_utc="2026-05-11T20:00:00Z", load_id="load-1", event_id="evt-1", reason="follow up")
        assert result["ok"] is True
        assert "timer_id" in result
        mock_client.create_schedule.assert_called_once()


def test_cancel_timer():
    with patch("app.timer.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        tc = TimerClient()
        tc._client = mock_client
        result = tc.cancel(timer_id="timer-abc123")
        assert result["ok"] is True
        mock_client.delete_schedule.assert_called_once()
