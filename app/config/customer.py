from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class CustomerPolicy(BaseModel):
    customer_id: str
    geofence_miles: float
    eta_followup_minutes: int
    escalation_channels: list[Literal["email", "slack"]]
    pod_validation: Literal["automatic", "human_review"]
    pod_received_visibility: bool
    delivered_no_pod_visibility: bool
    missing_info_visibility: bool
    lumper_strategy: Literal["review_task", "forward_email_for_email_attachments"]
    first_arrival_message: str


_CUSTOMERS_DIR = Path(__file__).parent / "customers"
_cache: dict[str, CustomerPolicy] = {}


def load_customer_policy(customer_id: str) -> CustomerPolicy:
    path = _CUSTOMERS_DIR / f"{customer_id}.yaml"
    if not path.exists():
        raise KeyError(f"No policy file for {customer_id}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return CustomerPolicy(**data)


def get_customer_policy(customer_id: str) -> CustomerPolicy:
    if customer_id not in _cache:
        _cache[customer_id] = load_customer_policy(customer_id)
    return _cache[customer_id]
