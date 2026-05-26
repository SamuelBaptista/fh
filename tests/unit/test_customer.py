import pytest
from app.config.customer import get_customer_policy


def test_customer_a_policy():
    policy = get_customer_policy("customer_a")
    assert policy.geofence_miles == 1.0
    assert policy.eta_followup_minutes == 30
    assert policy.escalation_channels == ["email"]
    assert policy.pod_validation == "automatic"
    assert policy.pod_received_visibility is True
    assert policy.delivered_no_pod_visibility is True
    assert policy.missing_info_visibility is False
    assert policy.lumper_strategy == "review_task"


def test_customer_b_policy():
    policy = get_customer_policy("customer_b")
    assert policy.geofence_miles == 2.0
    assert policy.eta_followup_minutes == 60
    assert policy.escalation_channels == ["slack"]
    assert policy.pod_validation == "human_review"
    assert policy.pod_received_visibility is False
    assert policy.delivered_no_pod_visibility is False
    assert policy.missing_info_visibility is True


def test_customer_c_policy():
    policy = get_customer_policy("customer_c")
    assert policy.geofence_miles == 3.0
    assert policy.eta_followup_minutes == 45
    assert policy.escalation_channels == ["email", "slack"]
    assert policy.pod_validation == "automatic"
    assert policy.pod_received_visibility is False
    assert policy.delivered_no_pod_visibility is True
    assert policy.lumper_strategy == "forward_email_for_email_attachments"


def test_unknown_customer_raises():
    with pytest.raises(KeyError):
        get_customer_policy("customer_z")
