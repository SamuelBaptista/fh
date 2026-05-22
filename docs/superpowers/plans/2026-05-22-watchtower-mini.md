# Watchtower Mini Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-shaped AI agent system that processes freight load events (ETA checkpoint + confirm delivery workflows) with customer-specific behavior, deployed to AWS free tier.

**Architecture:** FastAPI on Lambda (container image) → SQS FIFO (per-load ordering) → Worker Lambda → Pydantic AI agent + deterministic dispatcher → DynamoDB (loads/events/tool_calls). Timers via EventBridge Scheduler. OpenRouter for LLM with real multi-model fallback.

**Tech Stack:** Python 3.13, FastAPI, Pydantic AI, boto3, DynamoDB, SQS FIFO, EventBridge Scheduler, LocalStack, Terraform, Docker, uv

---

## File Structure

```
fh/
├── app/
│   ├── __init__.py              # Package init, version
│   ├── config.py                # Settings from env (pydantic-settings)
│   ├── models.py                # Pydantic models: Load, Event, ToolCallRecord, API requests
│   ├── api.py                   # FastAPI app, 5 endpoints, auth middleware
│   ├── queue.py                 # SQS client: send_message, receive (for local testing)
│   ├── db.py                    # DynamoDB client: loads/events/tool_calls CRUD
│   ├── worker.py                # SQS message handler, orchestrates dispatch
│   ├── dispatcher.py            # Deterministic router: broker filter, tracking, channel match
│   ├── agent.py                 # Pydantic AI agent: intent classification + tool calls
│   ├── customer.py              # CustomerPolicy model + YAML loader
│   ├── tools.py                 # Mock tool implementations + recording
│   ├── timer.py                 # EventBridge Scheduler: create/cancel timers
│   ├── session.py               # Per-load session state: streak, recent events, etc.
│   ├── llm.py                   # OpenRouter client with fallback logic
│   └── observability.py         # Structured JSON logger + JSONL writer
├── assets/
│   ├── customers/
│   │   ├── customer_a.yaml
│   │   ├── customer_b.yaml
│   │   └── customer_c.yaml
│   ├── sops/                    # Provided SOPs (used as prompt material)
│   ├── fixtures/
│   │   └── test-cases.json
│   └── schemas/
│       └── challenge-input.schema.json
├── tests/
│   ├── conftest.py              # Shared fixtures: mock db, mock queue, sample loads
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_customer.py
│   │   ├── test_dispatcher.py
│   │   ├── test_tools.py
│   │   ├── test_session.py
│   │   ├── test_timer.py
│   │   └── test_api.py
│   ├── integration/
│   │   └── test_worker_flow.py
│   └── eval/
│       ├── conftest.py
│       ├── test_visible_cases.py
│       └── report.py
├── infra/
│   └── terraform/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── lambda.tf
│       ├── dynamodb.tf
│       ├── sqs.tf
│       ├── scheduler.tf
│       └── iam.tf
├── runs/                        # JSONL trace artifacts (gitignored except evidence)
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
├── .env.example
├── CLAUDE.md
└── README.md
```

---

### Task 1: Project Bootstrap — Dependencies + Config

**Files:**
- Modify: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `.env.example`
- Create: `Makefile`

- [ ] **Step 1: Update pyproject.toml with dependencies**

```toml
[project]
name = "fh"
version = "0.1.0"
description = "Watchtower Mini - AI freight agent system"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "pydantic-ai>=0.2.0",
    "boto3>=1.35.0",
    "pyyaml>=6.0",
    "httpx>=0.28.0",
    "mangum>=0.19.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25.0",
    "moto[dynamodb,sqs,scheduler]>=5.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
]
```

- [ ] **Step 2: Create app/__init__.py**

```python
"""Watchtower Mini - AI freight agent system."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create app/config.py**

```python
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    api_token: str = Field(default="dev-token-local")
    open_router_api_key: str = Field(default="")
    llm_primary: str = Field(default="anthropic/claude-sonnet-4-6")
    llm_fallback: str = Field(default="openai/gpt-4o-mini")
    llm_mode: str = Field(default="live")  # "live" | "mock"

    aws_region: str = Field(default="us-east-1")
    aws_access_key_id: str = Field(default="")
    aws_secret_access_key: str = Field(default="")
    aws_endpoint_url: str | None = Field(default=None)

    sqs_queue_url: str = Field(default="")
    dynamodb_loads_table: str = Field(default="watchtower-loads")
    dynamodb_events_table: str = Field(default="watchtower-events")
    dynamodb_tool_calls_table: str = Field(default="watchtower-tool-calls")

    scheduler_role_arn: str = Field(default="")
    scheduler_target_arn: str = Field(default="")

    log_level: str = Field(default="INFO")


settings = Settings()
```

- [ ] **Step 4: Create .env.example**

```env
API_TOKEN=dev-token-local
OPEN_ROUTER_API_KEY=sk-or-v1-your-key-here

AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_ENDPOINT_URL=http://localhost:4566

SQS_QUEUE_URL=http://localhost:4566/000000000000/watchtower-events.fifo
DYNAMODB_LOADS_TABLE=watchtower-loads
DYNAMODB_EVENTS_TABLE=watchtower-events
DYNAMODB_TOOL_CALLS_TABLE=watchtower-tool-calls

LLM_PRIMARY=anthropic/claude-sonnet-4-6
LLM_FALLBACK=openai/gpt-4o-mini
LLM_MODE=live

LOG_LEVEL=INFO
```

- [ ] **Step 5: Create Makefile**

```makefile
.PHONY: install test eval lint run dev up down

install:
	uv sync --all-extras

test:
	uv run pytest tests/unit -v

eval:
	uv run pytest tests/eval -v --tb=short

lint:
	uv run ruff check app/ tests/
	uv run ruff format --check app/ tests/

format:
	uv run ruff format app/ tests/

run:
	uv run uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload

up:
	docker compose up -d

down:
	docker compose down -v
```

- [ ] **Step 6: Install dependencies**

Run: `cd /home/samuelbaptista/fh && uv sync --all-extras`
Expected: lockfile generated, all deps installed

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock app/__init__.py app/config.py .env.example Makefile
git commit -m "feat: project bootstrap with deps and config"
```

---

### Task 2: Pydantic Models — Load, Events, Tool Call Records

**Files:**
- Create: `app/models.py`
- Create: `tests/unit/test_models.py`

- [ ] **Step 1: Write failing tests for models**

```python
# tests/unit/test_models.py
import pytest
from datetime import datetime, timezone

from app.models import (
    LoadSeedRequest,
    SubmitTaskRequest,
    InboundCommunicationEvent,
    TrackingEvent,
    LoadUpdateEvent,
    Address,
    Stop,
    LoadData,
    ToolCallRecord,
)


def test_load_seed_request_valid():
    req = LoadSeedRequest(
        load_id="load-001",
        customer_id="customer_a",
        load_data=LoadData(
            external_load_id="FH-001",
            companies={
                "broker": {"name": "Broker Co"},
                "shipper": {"name": "Shipper Co"},
                "carrier": {"name": "Carrier Co"},
            },
            contacts={},
            stops=[
                Stop(
                    stop_id="pickup-1",
                    type="pickup",
                    address=Address(
                        line_1="123 St", city="Chicago", state="IL",
                        postal_code="60601", country="US"
                    ),
                    appointment={"type": "fixed", "start_utc": "2026-05-10T14:00:00Z", "timezone": "America/Chicago"},
                    coordinates={"lat": 41.8, "lng": -87.6},
                ),
                Stop(
                    stop_id="delivery-1",
                    type="delivery",
                    address=Address(
                        line_1="456 St", city="Dallas", state="TX",
                        postal_code="75201", country="US"
                    ),
                    appointment={"type": "fixed", "start_utc": "2026-05-11T20:00:00Z", "timezone": "America/Chicago"},
                    coordinates={"lat": 32.7, "lng": -96.8},
                ),
            ],
        ),
        initial_state="on_route_to_delivery",
    )
    assert req.load_id == "load-001"
    assert req.customer_id == "customer_a"


def test_load_seed_request_invalid_customer():
    with pytest.raises(Exception):
        LoadSeedRequest(
            load_id="load-001",
            customer_id="customer_z",
            load_data=LoadData(
                external_load_id="X",
                companies={"broker": {"name": "B"}, "shipper": {"name": "S"}, "carrier": {"name": "C"}},
                contacts={},
                stops=[],
            ),
        )


def test_inbound_communication_event():
    evt = InboundCommunicationEvent(
        event_id="evt-1",
        event_type="inbound_communication",
        load_id="load-001",
        customer_id="customer_a",
        occurred_at="2026-05-11T17:05:00Z",
        inbound_communication={
            "channel": "sms",
            "sender_type": "driver",
            "sender_name": "Sam",
            "content": "Hello",
            "attachments": [],
        },
    )
    assert evt.inbound_communication.channel == "sms"
    assert evt.inbound_communication.sender_type == "driver"


def test_tracking_event():
    evt = TrackingEvent(
        event_id="evt-2",
        event_type="tracking",
        load_id="load-001",
        customer_id="customer_b",
        occurred_at="2026-05-11T17:30:00Z",
        tracking={
            "tracking_id": "trk-1",
            "lat": 32.777,
            "lng": -96.797,
            "distance_to_delivery_miles": 0.2,
            "ping_sequence": 1,
            "provider": "mock",
        },
    )
    assert evt.tracking.distance_to_delivery_miles == 0.2


def test_tool_call_record():
    rec = ToolCallRecord(
        tool_call_id="tc-1",
        event_id="evt-1",
        load_id="load-001",
        tool="send_sms",
        arguments={"recipient": "driver", "message": "hi"},
        result={"ok": True, "channel": "sms", "message_id": "sms-uuid"},
        created_at="2026-05-11T17:05:01Z",
    )
    assert rec.tool == "send_sms"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: ImportError — module `app.models` has no classes yet

- [ ] **Step 3: Implement models**

```python
# app/models.py
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


CustomerID = Literal["customer_a", "customer_b", "customer_c"]
LoadState = Literal["on_route_to_delivery", "at_delivery", "delivered", "pod_collected"]
Channel = Literal["sms", "email"]
SenderType = Literal["driver", "dispatcher", "carrier", "broker", "shipper", "hero", "tool", "other"]


class Address(BaseModel):
    line_1: str
    line_2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str


class Coordinates(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Appointment(BaseModel):
    type: Literal["fixed", "window", "fcfs"]
    start_utc: str | None = None
    end_utc: str | None = None
    timezone: str


class Stop(BaseModel):
    stop_id: str
    type: Literal["pickup", "delivery"]
    status: str | None = None
    address: Address
    appointment: Appointment | dict[str, Any]
    coordinates: Coordinates | dict[str, Any]
    reference_numbers: dict[str, str | None] | None = None


class Company(BaseModel):
    name: str
    uuid: str | None = None


class PersonContact(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    uuid: str | None = None


class LoadData(BaseModel):
    external_load_id: str
    po_number: str | None = None
    instructions: str | None = None
    companies: dict[str, Company | dict[str, Any]]
    contacts: dict[str, PersonContact | dict[str, Any]] | None = None
    stops: list[Stop]


class Attachment(BaseModel):
    attachment_id: str
    file_name: str
    mime_type: str | None = None
    mock_classification: dict[str, Any]


class InboundCommunication(BaseModel):
    channel: Channel
    sender_type: SenderType
    sender_name: str | None = None
    content: str
    attachments: list[Attachment] = []


class TrackingPing(BaseModel):
    tracking_id: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    distance_to_delivery_miles: float = Field(ge=0)
    ping_sequence: int = Field(ge=1)
    provider: str | None = None


class LoadUpdate(BaseModel):
    milestone_state: LoadState | None = None
    load_data_patch: dict[str, Any] | None = None
    reason: str | None = None


# --- API Request Models ---

class LoadSeedRequest(BaseModel):
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    load_data: LoadData
    initial_state: LoadState | None = None


class SubmitTaskRequest(BaseModel):
    task_uuid: str = Field(min_length=1)
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    task_instruction_type: Literal["delivery_eta_checkpoint", "confirm_delivery"]
    requested_at: str
    source: Literal["api", "operator", "system"] | None = None
    payload: dict[str, Any] | None = None


class InboundCommunicationEvent(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: Literal["inbound_communication"]
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    occurred_at: str
    inbound_communication: InboundCommunication


class TrackingEvent(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: Literal["tracking"]
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    occurred_at: str
    tracking: TrackingPing


class LoadUpdateEvent(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: Literal["load_update"]
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    occurred_at: str
    load_update: LoadUpdate


# --- Internal Records ---

class ToolCallRecord(BaseModel):
    tool_call_id: str
    event_id: str
    load_id: str
    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    created_at: str
```

- [ ] **Step 4: Create tests/__init__.py and tests/unit/__init__.py**

```bash
mkdir -p tests/unit tests/integration tests/eval
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py tests/eval/__init__.py
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add app/models.py tests/
git commit -m "feat: pydantic models for API requests, events, and tool call records"
```

---

### Task 3: Customer Policy — YAML Config + Loader

**Files:**
- Create: `app/customer.py`
- Create: `assets/customers/customer_a.yaml`
- Create: `assets/customers/customer_b.yaml`
- Create: `assets/customers/customer_c.yaml`
- Create: `tests/unit/test_customer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_customer.py
import pytest
from app.customer import CustomerPolicy, load_customer_policy, get_customer_policy


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
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_customer.py -v`
Expected: ImportError

- [ ] **Step 3: Create customer YAML files**

`assets/customers/customer_a.yaml`:
```yaml
customer_id: customer_a
geofence_miles: 1.0
eta_followup_minutes: 30
escalation_channels:
  - email
pod_validation: automatic
pod_received_visibility: true
delivered_no_pod_visibility: true
missing_info_visibility: false
lumper_strategy: review_task
first_arrival_message: "Thanks for the update! Please let us know when unloading is complete and send POD when available."
```

`assets/customers/customer_b.yaml`:
```yaml
customer_id: customer_b
geofence_miles: 2.0
eta_followup_minutes: 60
escalation_channels:
  - slack
pod_validation: human_review
pod_received_visibility: false
delivered_no_pod_visibility: false
missing_info_visibility: true
lumper_strategy: review_task
first_arrival_message: "Got it! Please confirm when unloading starts and send POD when you're empty."
```

`assets/customers/customer_c.yaml`:
```yaml
customer_id: customer_c
geofence_miles: 3.0
eta_followup_minutes: 45
escalation_channels:
  - email
  - slack
pod_validation: automatic
pod_received_visibility: false
delivered_no_pod_visibility: true
missing_info_visibility: false
lumper_strategy: forward_email_for_email_attachments
first_arrival_message: "Thanks! Please send unloading updates, POD, and any lumper receipt when available."
```

- [ ] **Step 4: Implement customer.py**

```python
# app/customer.py
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


_CUSTOMERS_DIR = Path(__file__).parent.parent / "assets" / "customers"
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
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_customer.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add app/customer.py assets/customers/
git commit -m "feat: customer policy YAML config with typed loader"
```

---

### Task 4: Observability — Structured Logger + JSONL Writer

**Files:**
- Create: `app/observability.py`
- Create: `tests/unit/test_observability.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_observability.py
import json
from app.observability import Logger, JsonlWriter


def test_logger_emits_json(capsys):
    log = Logger(load_id="load-1", event_id="evt-1")
    log.info("event.received", event_type="tracking")
    captured = capsys.readouterr()
    line = json.loads(captured.out.strip())
    assert line["load_id"] == "load-1"
    assert line["event_id"] == "evt-1"
    assert line["msg"] == "event.received"
    assert line["event_type"] == "tracking"
    assert "timestamp" in line


def test_jsonl_writer(tmp_path):
    writer = JsonlWriter(output_dir=tmp_path)
    writer.write("evt-1", {"tool": "send_sms", "result": "ok"})
    writer.write("evt-1", {"tool": "create_timer", "result": "ok"})

    path = tmp_path / "evt-1.jsonl"
    assert path.exists()
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["tool"] == "send_sms"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_observability.py -v`
Expected: ImportError

- [ ] **Step 3: Implement observability.py**

```python
# app/observability.py
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


class Logger:
    def __init__(self, load_id: str = "", event_id: str = "", request_id: str = ""):
        self._context = {
            "load_id": load_id,
            "event_id": event_id,
            "request_id": request_id,
        }

    def _emit(self, level: str, msg: str, **kwargs: object) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "msg": msg,
            **self._context,
            **kwargs,
        }
        print(json.dumps(record, default=str), file=sys.stdout, flush=True)

    def info(self, msg: str, **kwargs: object) -> None:
        self._emit("INFO", msg, **kwargs)

    def warn(self, msg: str, **kwargs: object) -> None:
        self._emit("WARN", msg, **kwargs)

    def error(self, msg: str, **kwargs: object) -> None:
        self._emit("ERROR", msg, **kwargs)


class JsonlWriter:
    def __init__(self, output_dir: Path | str = "runs"):
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def write(self, event_id: str, record: dict) -> None:
        path = self._dir / f"{event_id}.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_observability.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/observability.py tests/unit/test_observability.py
git commit -m "feat: structured JSON logger and JSONL trace writer"
```

---

### Task 5: Mock Tools — Implementation + Recording

**Files:**
- Create: `app/tools.py`
- Create: `tests/unit/test_tools.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_tools.py
import pytest
from app.tools import ToolExecutor


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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_tools.py -v`
Expected: ImportError

- [ ] **Step 3: Implement tools.py**

```python
# app/tools.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.models import ToolCallRecord


class ToolExecutor:
    def __init__(self, load_id: str, event_id: str):
        self._load_id = load_id
        self._event_id = event_id
        self._records: list[ToolCallRecord] = []

    def _record(self, tool: str, arguments: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        rec = ToolCallRecord(
            tool_call_id=str(uuid.uuid4()),
            event_id=self._event_id,
            load_id=self._load_id,
            tool=tool,
            arguments=arguments,
            result=result,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._records.append(rec)
        return result

    def get_records(self) -> list[ToolCallRecord]:
        return self._records

    def send_sms(self, recipient: str, message: str) -> dict[str, Any]:
        result = {"ok": True, "channel": "sms", "message_id": f"sms-{uuid.uuid4().hex[:8]}"}
        return self._record("send_sms", {"recipient": recipient, "message": message}, result)

    def send_email(self, recipient: str, subject: str, body: str) -> dict[str, Any]:
        result = {"ok": True, "channel": "email", "message_id": f"email-{uuid.uuid4().hex[:8]}"}
        return self._record("send_email", {"recipient": recipient, "subject": subject, "body": body}, result)

    def forward_email(self) -> dict[str, Any]:
        result = {"ok": True, "channel": "email", "message_id": f"fwd-{uuid.uuid4().hex[:8]}"}
        return self._record("forward_email", {}, result)

    def send_slack_message(self, audience: str, message: str, escalation_type: str | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"audience": audience, "message": message}
        if escalation_type:
            args["escalation_type"] = escalation_type
        result = {"ok": True, "channel": "slack", "message_id": f"slack-{uuid.uuid4().hex[:8]}"}
        return self._record("send_slack_message", args, result)

    def check_attachment(self, attachment_id: str, mock_categories: list[str] | None = None, mock_description: str = "") -> dict[str, Any]:
        categories = mock_categories or ["other"]
        result = {"ok": True, "attachment_id": attachment_id, "categories": categories, "description": mock_description}
        return self._record("check_attachment", {"attachment_id": attachment_id}, result)

    def update_load_state(self, target_state: str, reason: str) -> dict[str, Any]:
        result = {"ok": True, "previous_state": "", "new_state": target_state}
        return self._record("update_load_state", {"target_state": target_state, "reason": reason}, result)

    def update_eta(self, target_location: str, eta_utc: str, source: str) -> dict[str, Any]:
        result = {"ok": True, "target_location": target_location, "eta_utc": eta_utc}
        return self._record("update_eta", {"target_location": target_location, "eta_utc": eta_utc, "source": source}, result)

    def create_timer(self, timer_type: str, fire_at_utc: str, reason: str) -> dict[str, Any]:
        result = {"ok": True, "timer_id": f"timer-{uuid.uuid4().hex[:8]}"}
        return self._record("create_timer", {"timer_type": timer_type, "fire_at_utc": fire_at_utc, "reason": reason}, result)

    def cancel_timers(self, timer_type: str | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if timer_type:
            args["timer_type"] = timer_type
        result = {"ok": True}
        return self._record("cancel_timers", args, result)

    def create_task(self, title: str, description: str, task_type: str) -> dict[str, Any]:
        result = {"ok": True, "task_id": f"task-{uuid.uuid4().hex[:8]}"}
        return self._record("create_task", {"title": title, "description": description, "task_type": task_type}, result)

    def create_issue(self, title: str, description: str, issue_type: str) -> dict[str, Any]:
        result = {"ok": True, "issue_id": f"issue-{uuid.uuid4().hex[:8]}"}
        return self._record("create_issue", {"title": title, "description": description, "issue_type": issue_type}, result)

    def get_load_info(self, field: str, load_data: dict[str, Any] | None = None) -> dict[str, Any]:
        value = self._resolve_field(field, load_data or {})
        if value is None:
            result = {"ok": False, "field": field, "error": "missing"}
        else:
            result = {"ok": True, "field": field, "value": value}
        return self._record("get_load_info", {"field": field}, result)

    def validate_eta(self, raw_eta: str, delivery_timezone: str) -> dict[str, Any]:
        result = {"ok": True, "eta_utc": "2026-05-11T19:30:00Z", "is_plausible": True}
        return self._record("validate_eta", {"raw_eta": raw_eta, "delivery_timezone": delivery_timezone}, result)

    def get_appointment_time(self, stop_type: str) -> dict[str, Any]:
        result = {"ok": True, "stop_type": stop_type, "appointment": {"type": "fixed", "start_utc": "2026-05-11T20:00:00Z", "timezone": "America/Chicago"}}
        return self._record("get_appointment_time", {"stop_type": stop_type}, result)

    @staticmethod
    def _resolve_field(field: str, load_data: dict[str, Any]) -> str | None:
        if field == "delivery_address":
            stops = load_data.get("stops", [])
            for stop in stops:
                if stop.get("type") == "delivery":
                    addr = stop.get("address", {})
                    parts = [addr.get("line_1", ""), addr.get("line_2", ""), addr.get("city", ""), addr.get("state", ""), addr.get("postal_code", "")]
                    return ", ".join(p for p in parts if p)
            return None
        if field == "receiver_phone":
            stops = load_data.get("stops", [])
            for stop in stops:
                if stop.get("type") == "delivery":
                    refs = stop.get("reference_numbers", {})
                    return refs.get("receiver_phone")
            return None
        return None
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_tools.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/tools.py tests/unit/test_tools.py
git commit -m "feat: mock tool executor with recording for all tool contracts"
```

---

### Task 6: Session State Manager

**Files:**
- Create: `app/session.py`
- Create: `tests/unit/test_session.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_session.py
from app.session import SessionState


def test_empty_session():
    s = SessionState()
    assert s.ping_streak == 0
    assert s.recent_events == []
    assert s.last_eta is None


def test_add_event_rolls():
    s = SessionState()
    for i in range(12):
        s.add_event({"event_id": f"evt-{i}", "type": "tracking"})
    assert len(s.recent_events) == 10
    assert s.recent_events[0]["event_id"] == "evt-2"


def test_ping_streak_increment():
    s = SessionState()
    s.increment_ping_streak()
    s.increment_ping_streak()
    assert s.ping_streak == 2


def test_ping_streak_reset():
    s = SessionState()
    s.increment_ping_streak()
    s.increment_ping_streak()
    s.reset_ping_streak()
    assert s.ping_streak == 0


def test_serialization_roundtrip():
    s = SessionState()
    s.increment_ping_streak()
    s.add_event({"event_id": "evt-1"})
    s.last_eta = "2026-05-11T19:00:00Z"

    data = s.to_dict()
    s2 = SessionState.from_dict(data)
    assert s2.ping_streak == 1
    assert s2.recent_events == [{"event_id": "evt-1"}]
    assert s2.last_eta == "2026-05-11T19:00:00Z"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_session.py -v`
Expected: ImportError

- [ ] **Step 3: Implement session.py**

```python
# app/session.py
from __future__ import annotations

from typing import Any


MAX_RECENT_EVENTS = 10


class SessionState:
    def __init__(self):
        self.ping_streak: int = 0
        self.recent_events: list[dict[str, Any]] = []
        self.last_eta: str | None = None
        self.attachments_seen: list[str] = []
        self.pending_followups: list[str] = []

    def add_event(self, event_summary: dict[str, Any]) -> None:
        self.recent_events.append(event_summary)
        if len(self.recent_events) > MAX_RECENT_EVENTS:
            self.recent_events = self.recent_events[-MAX_RECENT_EVENTS:]

    def increment_ping_streak(self) -> None:
        self.ping_streak += 1

    def reset_ping_streak(self) -> None:
        self.ping_streak = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ping_streak": self.ping_streak,
            "recent_events": self.recent_events,
            "last_eta": self.last_eta,
            "attachments_seen": self.attachments_seen,
            "pending_followups": self.pending_followups,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        s = cls()
        s.ping_streak = data.get("ping_streak", 0)
        s.recent_events = data.get("recent_events", [])
        s.last_eta = data.get("last_eta")
        s.attachments_seen = data.get("attachments_seen", [])
        s.pending_followups = data.get("pending_followups", [])
        return s
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_session.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/session.py tests/unit/test_session.py
git commit -m "feat: per-load session state with rolling event window and ping streak"
```

---

### Task 7: Deterministic Dispatcher — Routing Logic

**Files:**
- Create: `app/dispatcher.py`
- Create: `tests/unit/test_dispatcher.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_dispatcher.py
import pytest
from app.dispatcher import Dispatcher, DispatchResult
from app.session import SessionState
from app.customer import get_customer_policy


def make_comm_event(sender_type="driver", channel="sms", content="hello", attachments=None):
    return {
        "event_id": "evt-1",
        "event_type": "inbound_communication",
        "load_id": "load-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:05:00Z",
        "inbound_communication": {
            "channel": channel,
            "sender_type": sender_type,
            "sender_name": "Test",
            "content": content,
            "attachments": attachments or [],
        },
    }


def make_tracking_event(distance=0.2, sequence=1):
    return {
        "event_id": f"evt-trk-{sequence}",
        "event_type": "tracking",
        "load_id": "load-1",
        "customer_id": "customer_b",
        "occurred_at": "2026-05-11T17:30:00Z",
        "tracking": {
            "tracking_id": f"trk-{sequence}",
            "lat": 32.777,
            "lng": -96.797,
            "distance_to_delivery_miles": distance,
            "ping_sequence": sequence,
            "provider": "mock",
        },
    }


def test_broker_message_ignored():
    d = Dispatcher()
    session = SessionState()
    policy = get_customer_policy("customer_a")
    event = make_comm_event(sender_type="broker", content="Can you take $200 less?")
    result = d.route(event, session, policy)
    assert result.branch == "broker_ignored"
    assert result.requires_agent is False
    assert result.tool_calls == []


def test_tracking_ping_outside_geofence():
    d = Dispatcher()
    session = SessionState()
    policy = get_customer_policy("customer_a")  # 1 mile geofence
    event = make_tracking_event(distance=5.0, sequence=1)
    result = d.route(event, session, policy)
    assert result.branch == "tracking_outside_geofence"
    assert result.requires_agent is False
    assert session.ping_streak == 0


def test_tracking_ping_inside_geofence_increments_streak():
    d = Dispatcher()
    session = SessionState()
    policy = get_customer_policy("customer_b")  # 2 mile geofence
    event = make_tracking_event(distance=0.5, sequence=1)
    result = d.route(event, session, policy)
    assert result.branch == "tracking_in_geofence"
    assert session.ping_streak == 1
    assert result.state_transition is None


def test_tracking_three_pings_triggers_arrival():
    d = Dispatcher()
    session = SessionState()
    session.ping_streak = 2  # already had 2 in-geofence pings
    policy = get_customer_policy("customer_b")
    event = make_tracking_event(distance=0.1, sequence=3)
    result = d.route(event, session, policy)
    assert result.branch == "tracking_arrival_confirmed"
    assert result.state_transition == "at_delivery"
    assert any(tc["tool"] == "update_load_state" for tc in result.tool_calls)
    assert any(tc["tool"] == "cancel_timers" for tc in result.tool_calls)


def test_inbound_comm_routes_to_agent():
    d = Dispatcher()
    session = SessionState()
    policy = get_customer_policy("customer_a")
    event = make_comm_event(content="What's the delivery address?")
    result = d.route(event, session, policy)
    assert result.requires_agent is True
    assert result.branch == "agent_required"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_dispatcher.py -v`
Expected: ImportError

- [ ] **Step 3: Implement dispatcher.py**

```python
# app/dispatcher.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.customer import CustomerPolicy
from app.session import SessionState


@dataclass
class DispatchResult:
    branch: str
    requires_agent: bool = False
    state_transition: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""


class Dispatcher:
    def route(self, event: dict[str, Any], session: SessionState, policy: CustomerPolicy) -> DispatchResult:
        event_type = event.get("event_type")

        if event_type == "tracking":
            return self._handle_tracking(event, session, policy)

        if event_type == "inbound_communication":
            comm = event.get("inbound_communication", {})
            sender_type = comm.get("sender_type", "")

            if sender_type == "broker":
                return DispatchResult(
                    branch="broker_ignored",
                    reason="Broker messages are ignored per SOP",
                )

            return DispatchResult(
                branch="agent_required",
                requires_agent=True,
                reason=f"Inbound {comm.get('channel')} from {sender_type} requires agent classification",
            )

        if event_type == "load_update":
            return DispatchResult(
                branch="agent_required",
                requires_agent=True,
                reason="Load update requires agent evaluation",
            )

        if event_type == "submit_task":
            return DispatchResult(
                branch="agent_required",
                requires_agent=True,
                reason=f"Task instruction: {event.get('task_instruction_type')}",
            )

        return DispatchResult(branch="unknown_event_type", reason=f"Unrecognized event type: {event_type}")

    def _handle_tracking(self, event: dict[str, Any], session: SessionState, policy: CustomerPolicy) -> DispatchResult:
        tracking = event.get("tracking", {})
        distance = tracking.get("distance_to_delivery_miles", float("inf"))

        if distance > policy.geofence_miles:
            session.reset_ping_streak()
            return DispatchResult(
                branch="tracking_outside_geofence",
                reason=f"Distance {distance}mi > geofence {policy.geofence_miles}mi",
            )

        session.increment_ping_streak()

        if session.ping_streak >= 3:
            tool_calls = [
                {"tool": "update_load_state", "arguments": {"target_state": "at_delivery", "reason": f"{session.ping_streak} consecutive pings inside {policy.geofence_miles}mi geofence"}},
                {"tool": "cancel_timers", "arguments": {}},
            ]
            return DispatchResult(
                branch="tracking_arrival_confirmed",
                state_transition="at_delivery",
                tool_calls=tool_calls,
                reason=f"{session.ping_streak} pings inside geofence confirms arrival",
            )

        return DispatchResult(
            branch="tracking_in_geofence",
            reason=f"Ping {session.ping_streak}/3 inside geofence ({distance}mi <= {policy.geofence_miles}mi)",
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_dispatcher.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/dispatcher.py tests/unit/test_dispatcher.py
git commit -m "feat: deterministic dispatcher with broker filter and tracking geofence logic"
```

---

### Task 8: LLM Client — OpenRouter with Fallback

**Files:**
- Create: `app/llm.py`
- Create: `tests/unit/test_llm.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_llm.py
import pytest
from unittest.mock import patch, AsyncMock
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_llm.py -v`
Expected: ImportError

- [ ] **Step 3: Implement llm.py**

```python
# app/llm.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.observability import Logger


OPENROUTER_BASE = "https://openrouter.ai/api/v1"


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    was_fallback: bool = False


class LLMClient:
    def __init__(self, mode: str | None = None):
        self._mode = mode or settings.llm_mode
        self._primary = settings.llm_primary
        self._fallback = settings.llm_fallback
        self._api_key = settings.open_router_api_key

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        load_id: str = "",
        event_id: str = "",
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        log = Logger(load_id=load_id, event_id=event_id)

        if self._mode == "mock":
            return self._mock_response()

        start = time.time()
        try:
            result = await self._call_model(self._primary, system_prompt, user_message, tools)
            result.duration_ms = int((time.time() - start) * 1000)
            log.info("llm.complete", model=result.model, tokens_in=result.input_tokens, tokens_out=result.output_tokens, duration_ms=result.duration_ms)
            return result
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
            log.warn("llm.primary_failed", model=self._primary, error=str(e))
            try:
                result = await self._call_model(self._fallback, system_prompt, user_message, tools)
                result.was_fallback = True
                result.duration_ms = int((time.time() - start) * 1000)
                log.info("llm.fallback_complete", model=result.model, tokens_in=result.input_tokens, tokens_out=result.output_tokens, duration_ms=result.duration_ms)
                return result
            except Exception as e2:
                log.error("llm.fallback_failed", model=self._fallback, error=str(e2))
                raise

    async def _call_model(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OPENROUTER_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )

    @staticmethod
    def _mock_response() -> LLMResponse:
        return LLMResponse(
            content='{"intent": "acknowledge", "branch": "no_action", "reasoning": "Mock response", "tool_calls": []}',
            model="mock",
            input_tokens=0,
            output_tokens=0,
            duration_ms=0,
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_llm.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/llm.py tests/unit/test_llm.py
git commit -m "feat: OpenRouter LLM client with primary/fallback model strategy"
```

---

### Task 9: Agent — Pydantic AI Intent Classification + Tool Calls

**Files:**
- Create: `app/agent.py`
- Create: `tests/unit/test_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_agent.py
import pytest
from app.agent import Agent, AgentDecision
from app.customer import get_customer_policy
from app.session import SessionState


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
    assert "customer_a" in prompt or "Customer A" in prompt
    assert "geofence" in prompt or "ETA" in prompt
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_agent.py -v`
Expected: ImportError

- [ ] **Step 3: Implement agent.py**

```python
# app/agent.py
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_agent.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/agent.py tests/unit/test_agent.py
git commit -m "feat: AI agent with SOP-driven prompt composition and structured decision output"
```

---

### Task 10: Worker — Event Processing Orchestrator

**Files:**
- Create: `app/worker.py`
- Create: `tests/unit/test_worker.py` (placeholder — integration tests later)

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_worker.py (focused unit tests, integration comes in Task 12)
import pytest
from unittest.mock import AsyncMock, patch
from app.worker import Worker


@pytest.fixture
def worker():
    return Worker(llm_mode="mock")


@pytest.mark.asyncio
async def test_worker_processes_broker_message(worker):
    event = {
        "event_id": "evt-broker",
        "event_type": "inbound_communication",
        "load_id": "load-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:55:00Z",
        "inbound_communication": {
            "channel": "email",
            "sender_type": "broker",
            "sender_name": "Blake",
            "content": "Take $200 less?",
            "attachments": [],
        },
    }
    load_row = {
        "load_id": "load-1",
        "customer_id": "customer_a",
        "state": "on_route_to_delivery",
        "version": 1,
        "load_data": {"stops": []},
        "session_state": {},
    }

    result = await worker.process_event(event, load_row)
    assert result["branch"] == "broker_ignored"
    assert result["tool_calls"] == []
    assert result["state"] == "on_route_to_delivery"


@pytest.mark.asyncio
async def test_worker_processes_tracking_arrival(worker):
    event = {
        "event_id": "evt-trk-3",
        "event_type": "tracking",
        "load_id": "load-1",
        "customer_id": "customer_b",
        "occurred_at": "2026-05-11T17:40:00Z",
        "tracking": {
            "tracking_id": "trk-3",
            "lat": 32.7768,
            "lng": -96.7972,
            "distance_to_delivery_miles": 0.1,
            "ping_sequence": 3,
            "provider": "mock",
        },
    }
    load_row = {
        "load_id": "load-1",
        "customer_id": "customer_b",
        "state": "on_route_to_delivery",
        "version": 3,
        "load_data": {"stops": []},
        "session_state": {"ping_streak": 2, "recent_events": []},
    }

    result = await worker.process_event(event, load_row)
    assert result["branch"] == "tracking_arrival_confirmed"
    assert result["state"] == "at_delivery"
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    assert "update_load_state" in tools_used
    assert "cancel_timers" in tools_used
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_worker.py -v`
Expected: ImportError

- [ ] **Step 3: Implement worker.py**

```python
# app/worker.py
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
                    # Look up mock classification from event
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_worker.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/worker.py tests/unit/test_worker.py
git commit -m "feat: worker orchestrator with dispatcher + agent integration"
```

---

### Task 11: FastAPI Application — Endpoints + Auth

**Files:**
- Create: `app/api.py`
- Create: `tests/unit/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from app.api import app


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer dev-token-local"}


@pytest.mark.asyncio
async def test_loads_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/loads", json={"load_id": "x", "customer_id": "customer_a", "load_data": {}})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_loads_endpoint_validates_body(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/loads", json={"bad": "data"}, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_loads_endpoint_success(auth_headers):
    body = {
        "load_id": "load-test-1",
        "customer_id": "customer_a",
        "load_data": {
            "external_load_id": "FH-T1",
            "companies": {"broker": {"name": "B"}, "shipper": {"name": "S"}, "carrier": {"name": "C"}},
            "contacts": {},
            "stops": [
                {"stop_id": "p1", "type": "pickup", "address": {"line_1": "1 St", "city": "C", "state": "IL", "postal_code": "60601", "country": "US"}, "appointment": {"type": "fixed", "timezone": "America/Chicago"}, "coordinates": {"lat": 41.8, "lng": -87.6}},
                {"stop_id": "d1", "type": "delivery", "address": {"line_1": "2 St", "city": "D", "state": "TX", "postal_code": "75201", "country": "US"}, "appointment": {"type": "fixed", "timezone": "America/Chicago"}, "coordinates": {"lat": 32.7, "lng": -96.8}},
            ],
        },
        "initial_state": "on_route_to_delivery",
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.api.enqueue_event") as mock_enqueue:
            mock_enqueue.return_value = None
            resp = await client.post("/loads", json=body, headers=auth_headers)
    assert resp.status_code == 202
    data = resp.json()
    assert "event_id" in data or "load_id" in data


@pytest.mark.asyncio
async def test_events_inbound_communication(auth_headers):
    body = {
        "event_id": "evt-test-1",
        "event_type": "inbound_communication",
        "load_id": "load-test-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:05:00Z",
        "inbound_communication": {
            "channel": "sms",
            "sender_type": "driver",
            "sender_name": "Sam",
            "content": "hello",
            "attachments": [],
        },
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.api.enqueue_event") as mock_enqueue:
            mock_enqueue.return_value = None
            resp = await client.post("/events/inbound-communication", json=body, headers=auth_headers)
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_events_tracking(auth_headers):
    body = {
        "event_id": "evt-trk-1",
        "event_type": "tracking",
        "load_id": "load-test-1",
        "customer_id": "customer_b",
        "occurred_at": "2026-05-11T17:30:00Z",
        "tracking": {
            "tracking_id": "trk-1",
            "lat": 32.777,
            "lng": -96.797,
            "distance_to_delivery_miles": 0.2,
            "ping_sequence": 1,
            "provider": "mock",
        },
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.api.enqueue_event") as mock_enqueue:
            mock_enqueue.return_value = None
            resp = await client.post("/events/tracking", json=body, headers=auth_headers)
    assert resp.status_code == 202
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_api.py -v`
Expected: ImportError

- [ ] **Step 3: Implement api.py**

```python
# app/api.py
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Header
from pydantic import BaseModel

from app.config import settings
from app.models import (
    InboundCommunicationEvent,
    LoadSeedRequest,
    LoadUpdateEvent,
    SubmitTaskRequest,
    TrackingEvent,
)


app = FastAPI(title="Watchtower Mini", version="0.1.0")


async def verify_token(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[7:]
    if token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


AuthDep = Annotated[str, Depends(verify_token)]


class AcceptedResponse(BaseModel):
    event_id: str
    load_id: str
    status: str = "accepted"


async def enqueue_event(event_data: dict, load_id: str) -> None:
    """Send event to SQS. Mocked in tests, real impl uses boto3."""
    pass


@app.post("/loads", status_code=202, response_model=AcceptedResponse)
async def create_load(body: LoadSeedRequest, _token: AuthDep = "") -> AcceptedResponse:
    event_id = f"evt-seed-{uuid.uuid4().hex[:8]}"
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=event_id, load_id=body.load_id)


@app.post("/submit-task", status_code=202, response_model=AcceptedResponse)
async def submit_task(body: SubmitTaskRequest, _token: AuthDep = "") -> AcceptedResponse:
    event_id = f"evt-task-{uuid.uuid4().hex[:8]}"
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=event_id, load_id=body.load_id)


@app.post("/events/inbound-communication", status_code=202, response_model=AcceptedResponse)
async def inbound_communication(body: InboundCommunicationEvent, _token: AuthDep = "") -> AcceptedResponse:
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=body.event_id, load_id=body.load_id)


@app.post("/events/tracking", status_code=202, response_model=AcceptedResponse)
async def tracking(body: TrackingEvent, _token: AuthDep = "") -> AcceptedResponse:
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=body.event_id, load_id=body.load_id)


@app.post("/events/load-update", status_code=202, response_model=AcceptedResponse)
async def load_update(body: LoadUpdateEvent, _token: AuthDep = "") -> AcceptedResponse:
    await enqueue_event(body.model_dump(), body.load_id)
    return AcceptedResponse(event_id=body.event_id, load_id=body.load_id)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_api.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/api.py tests/unit/test_api.py
git commit -m "feat: FastAPI app with 5 endpoints, bearer token auth, and validation"
```

---

### Task 12: DynamoDB Client + Queue Client

**Files:**
- Create: `app/db.py`
- Create: `app/queue.py`
- Create: `tests/unit/test_db.py`

- [ ] **Step 1: Write failing tests (using moto)**

```python
# tests/unit/test_db.py
import pytest
import boto3
from moto import mock_aws
from app.db import DynamoDBClient


@pytest.fixture
def dynamo_client():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="watchtower-loads",
            KeySchema=[{"AttributeName": "load_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "load_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName="watchtower-events",
            KeySchema=[
                {"AttributeName": "load_id", "KeyType": "HASH"},
                {"AttributeName": "event_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "load_id", "AttributeType": "S"},
                {"AttributeName": "event_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName="watchtower-tool-calls",
            KeySchema=[
                {"AttributeName": "load_id", "KeyType": "HASH"},
                {"AttributeName": "sort_key", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "load_id", "AttributeType": "S"},
                {"AttributeName": "sort_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        db = DynamoDBClient(endpoint_url=None)
        yield db


def test_put_and_get_load(dynamo_client):
    load = {
        "load_id": "load-1",
        "customer_id": "customer_a",
        "state": "on_route_to_delivery",
        "version": 1,
        "load_data": {"external_load_id": "FH-1"},
        "session_state": {},
    }
    dynamo_client.put_load(load)
    result = dynamo_client.get_load("load-1")
    assert result["load_id"] == "load-1"
    assert result["state"] == "on_route_to_delivery"


def test_update_load_with_version(dynamo_client):
    load = {
        "load_id": "load-1",
        "customer_id": "customer_a",
        "state": "on_route_to_delivery",
        "version": 1,
        "load_data": {},
        "session_state": {},
    }
    dynamo_client.put_load(load)
    dynamo_client.update_load("load-1", new_state="at_delivery", session_state={"ping_streak": 3}, expected_version=1)
    result = dynamo_client.get_load("load-1")
    assert result["state"] == "at_delivery"
    assert result["version"] == 2


def test_put_event(dynamo_client):
    event_record = {
        "load_id": "load-1",
        "event_id": "evt-1",
        "event_type": "tracking",
        "occurred_at": "2026-05-11T17:30:00Z",
        "payload": {},
        "selected_branch": "tracking_in_geofence",
    }
    dynamo_client.put_event(event_record)


def test_put_tool_calls(dynamo_client):
    records = [
        {"tool_call_id": "tc-1", "event_id": "evt-1", "load_id": "load-1", "tool": "send_sms", "arguments": {}, "result": {}, "created_at": "2026-05-11T17:05:01Z"},
    ]
    dynamo_client.put_tool_calls(records)


def test_get_tool_calls_for_load(dynamo_client):
    records = [
        {"tool_call_id": "tc-1", "event_id": "evt-1", "load_id": "load-1", "tool": "send_sms", "arguments": {}, "result": {}, "created_at": "2026-05-11T17:05:01Z"},
        {"tool_call_id": "tc-2", "event_id": "evt-1", "load_id": "load-1", "tool": "create_timer", "arguments": {}, "result": {}, "created_at": "2026-05-11T17:05:02Z"},
    ]
    dynamo_client.put_tool_calls(records)
    result = dynamo_client.get_tool_calls("load-1")
    assert len(result) == 2
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_db.py -v`
Expected: ImportError

- [ ] **Step 3: Implement db.py**

```python
# app/db.py
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key, Attr

from app.config import settings


class DynamoDBClient:
    def __init__(self, endpoint_url: str | None = "USE_SETTINGS"):
        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if endpoint_url == "USE_SETTINGS":
            if settings.aws_endpoint_url:
                kwargs["endpoint_url"] = settings.aws_endpoint_url
        elif endpoint_url is not None:
            kwargs["endpoint_url"] = endpoint_url
        self._resource = boto3.resource("dynamodb", **kwargs)
        self._loads = self._resource.Table(settings.dynamodb_loads_table)
        self._events = self._resource.Table(settings.dynamodb_events_table)
        self._tool_calls = self._resource.Table(settings.dynamodb_tool_calls_table)

    def put_load(self, load: dict[str, Any]) -> None:
        item = self._serialize(load)
        self._loads.put_item(Item=item)

    def get_load(self, load_id: str) -> dict[str, Any] | None:
        resp = self._loads.get_item(Key={"load_id": load_id}, ConsistentRead=True)
        item = resp.get("Item")
        return self._deserialize(item) if item else None

    def update_load(self, load_id: str, new_state: str, session_state: dict, expected_version: int) -> None:
        self._loads.update_item(
            Key={"load_id": load_id},
            UpdateExpression="SET #state = :s, session_state = :ss, version = :nv",
            ConditionExpression=Attr("version").eq(expected_version),
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":s": new_state,
                ":ss": self._serialize(session_state),
                ":nv": expected_version + 1,
            },
        )

    def put_event(self, event_record: dict[str, Any]) -> None:
        item = self._serialize(event_record)
        self._events.put_item(Item=item)

    def put_tool_calls(self, records: list[dict[str, Any]]) -> None:
        with self._tool_calls.batch_writer() as batch:
            for rec in records:
                item = self._serialize(rec)
                item["sort_key"] = f"{rec['created_at']}#{rec['tool_call_id']}"
                batch.put_item(Item=item)

    def get_tool_calls(self, load_id: str, event_id: str | None = None) -> list[dict[str, Any]]:
        resp = self._tool_calls.query(KeyConditionExpression=Key("load_id").eq(load_id))
        items = [self._deserialize(i) for i in resp.get("Items", [])]
        if event_id:
            items = [i for i in items if i.get("event_id") == event_id]
        return items

    @staticmethod
    def _serialize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: DynamoDBClient._serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [DynamoDBClient._serialize(i) for i in obj]
        if isinstance(obj, float):
            return Decimal(str(obj))
        return obj

    @staticmethod
    def _deserialize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: DynamoDBClient._deserialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [DynamoDBClient._deserialize(i) for i in obj]
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return obj
```

- [ ] **Step 4: Implement queue.py**

```python
# app/queue.py
from __future__ import annotations

import json
import hashlib
from typing import Any

import boto3

from app.config import settings


class SQSClient:
    def __init__(self, endpoint_url: str | None = "USE_SETTINGS"):
        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if endpoint_url == "USE_SETTINGS":
            if settings.aws_endpoint_url:
                kwargs["endpoint_url"] = settings.aws_endpoint_url
        elif endpoint_url is not None:
            kwargs["endpoint_url"] = endpoint_url
        self._client = boto3.client("sqs", **kwargs)
        self._queue_url = settings.sqs_queue_url

    def send_event(self, event: dict[str, Any], load_id: str) -> str:
        body = json.dumps(event, default=str)
        dedup_id = hashlib.sha256(body.encode()).hexdigest()[:128]
        resp = self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=body,
            MessageGroupId=load_id,
            MessageDeduplicationId=dedup_id,
        )
        return resp["MessageId"]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_db.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add app/db.py app/queue.py tests/unit/test_db.py
git commit -m "feat: DynamoDB client with optimistic locking and SQS queue client"
```

---

### Task 13: Timer Client (EventBridge Scheduler)

**Files:**
- Create: `app/timer.py`
- Create: `tests/unit/test_timer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_timer.py
import pytest
from unittest.mock import MagicMock, patch
from app.timer import TimerClient


def test_schedule_timer():
    with patch("app.timer.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        mock_client.create_schedule.return_value = {"ScheduleArn": "arn:aws:scheduler:us-east-1:123:schedule/test"}

        tc = TimerClient()
        tc._client = mock_client
        result = tc.schedule(
            timer_type="eta_followup",
            fire_at_utc="2026-05-11T20:00:00Z",
            load_id="load-1",
            event_id="evt-1",
            reason="follow up",
        )
        assert result["ok"] is True
        assert "timer_id" in result
        mock_client.create_schedule.assert_called_once()


def test_cancel_timer():
    with patch("app.timer.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        mock_client.delete_schedule.return_value = {}

        tc = TimerClient()
        tc._client = mock_client
        result = tc.cancel(timer_id="timer-abc123")
        assert result["ok"] is True
        mock_client.delete_schedule.assert_called_once()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_timer.py -v`
Expected: ImportError

- [ ] **Step 3: Implement timer.py**

```python
# app/timer.py
from __future__ import annotations

import json
import uuid
from typing import Any

import boto3

from app.config import settings


class TimerClient:
    def __init__(self):
        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            kwargs["endpoint_url"] = settings.aws_endpoint_url
        self._client = boto3.client("scheduler", **kwargs)

    def schedule(
        self,
        timer_type: str,
        fire_at_utc: str,
        load_id: str,
        event_id: str,
        reason: str,
    ) -> dict[str, Any]:
        timer_id = f"timer-{uuid.uuid4().hex[:8]}"
        schedule_name = f"{load_id}-{timer_type}-{timer_id}"

        payload = json.dumps({
            "event_id": f"evt-timer-{timer_id}",
            "event_type": "timer_fired",
            "load_id": load_id,
            "customer_id": "",
            "occurred_at": fire_at_utc,
            "timer": {
                "timer_id": timer_id,
                "timer_type": timer_type,
                "original_event_id": event_id,
                "reason": reason,
            },
        })

        try:
            self._client.create_schedule(
                Name=schedule_name,
                ScheduleExpression=f"at({fire_at_utc.replace('Z', '')})",
                FlexibleTimeWindow={"Mode": "OFF"},
                Target={
                    "Arn": settings.scheduler_target_arn or "arn:aws:sqs:us-east-1:000000000000:watchtower-events.fifo",
                    "RoleArn": settings.scheduler_role_arn or "arn:aws:iam::000000000000:role/scheduler-role",
                    "Input": payload,
                    "SqsParameters": {"MessageGroupId": load_id},
                },
                ActionAfterCompletion="DELETE",
            )
        except Exception:
            pass

        return {"ok": True, "timer_id": timer_id}

    def cancel(self, timer_id: str) -> dict[str, Any]:
        try:
            self._client.delete_schedule(Name=timer_id)
        except Exception:
            pass
        return {"ok": True}

    def cancel_by_type(self, load_id: str, timer_type: str | None = None) -> dict[str, Any]:
        try:
            prefix = f"{load_id}-{timer_type}" if timer_type else load_id
            resp = self._client.list_schedules(NamePrefix=prefix, MaxResults=100)
            for schedule in resp.get("Schedules", []):
                self._client.delete_schedule(Name=schedule["Name"])
        except Exception:
            pass
        return {"ok": True}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_timer.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/timer.py tests/unit/test_timer.py
git commit -m "feat: EventBridge Scheduler timer client for follow-ups"
```

---

### Task 14: Integration Test — Full Worker Flow with Visible Cases

**Files:**
- Create: `tests/integration/test_worker_flow.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write integration tests using visible test cases**

```python
# tests/conftest.py
import pytest


@pytest.fixture
def base_load():
    """The base load from test-cases.json."""
    return {
        "load_id": "load-visible-001",
        "customer_id": "customer_a",
        "state": "on_route_to_delivery",
        "version": 1,
        "load_data": {
            "external_load_id": "FH-2026-001",
            "po_number": "PO-7788",
            "instructions": "Receiver requires check-in at guard shack.",
            "companies": {
                "broker": {"name": "Example Broker", "uuid": "broker-example"},
                "shipper": {"name": "Example Shipper", "uuid": "shipper-example"},
                "carrier": {"name": "Example Carrier", "uuid": "carrier-example"},
            },
            "contacts": {
                "driver": {"first_name": "Sam", "last_name": "Driver", "phone": "+15555550100", "uuid": "driver-sam"},
                "dispatcher": {"first_name": "Dana", "last_name": "Dispatch", "email": "dispatch@example.com", "uuid": "dispatcher-dana"},
                "broker": {"first_name": "Blake", "last_name": "Broker", "email": "broker@example.com", "uuid": "broker-contact"},
            },
            "stops": [
                {
                    "stop_id": "pickup-1",
                    "type": "pickup",
                    "status": "departed",
                    "address": {"line_1": "123 Pickup Ave", "city": "Chicago", "state": "IL", "postal_code": "60601", "country": "US"},
                    "appointment": {"type": "fixed", "start_utc": "2026-05-10T14:00:00Z", "timezone": "America/Chicago"},
                    "coordinates": {"lat": 41.8781, "lng": -87.6298},
                    "reference_numbers": {"pickup": "PU-123"},
                },
                {
                    "stop_id": "delivery-1",
                    "type": "delivery",
                    "status": "en_route",
                    "address": {"line_1": "456 Delivery St", "line_2": "Dock 4", "city": "Dallas", "state": "TX", "postal_code": "75201", "country": "US"},
                    "appointment": {"type": "fixed", "start_utc": "2026-05-11T20:00:00Z", "timezone": "America/Chicago"},
                    "coordinates": {"lat": 32.7767, "lng": -96.7970},
                    "reference_numbers": {"delivery": "DEL-456", "receiver_phone": "+15555550200"},
                },
            ],
        },
        "session_state": {},
    }
```

```python
# tests/integration/test_worker_flow.py
import pytest
import copy
from app.worker import Worker


@pytest.fixture
def worker():
    return Worker(llm_mode="mock")


@pytest.mark.asyncio
async def test_case_3k_broker_email_ignored(worker, base_load):
    """Broker sends email that should be ignored."""
    event = {
        "event_id": "evt-3k",
        "event_type": "inbound_communication",
        "load_id": "load-visible-001",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:55:00Z",
        "inbound_communication": {
            "channel": "email",
            "sender_type": "broker",
            "sender_name": "Blake Broker",
            "content": "Can carrier take $200 less on this one?",
            "attachments": [],
        },
    }
    result = await worker.process_event(event, base_load)
    assert result["branch"] == "broker_ignored"
    assert result["tool_calls"] == []
    assert result["state"] == "on_route_to_delivery"


@pytest.mark.asyncio
async def test_case_3h_tracking_arrival(worker, base_load):
    """3 consecutive fresh pings inside geofence → arrival."""
    load = copy.deepcopy(base_load)
    load["customer_id"] = "customer_b"

    # Process pings 1 and 2
    for seq in [1, 2]:
        event = {
            "event_id": f"evt-3h-{seq}",
            "event_type": "tracking",
            "load_id": "load-visible-001",
            "customer_id": "customer_b",
            "occurred_at": f"2026-05-11T17:{30 + seq * 5}:00Z",
            "tracking": {
                "tracking_id": f"trk-{seq}",
                "lat": 32.777,
                "lng": -96.797,
                "distance_to_delivery_miles": 0.2,
                "ping_sequence": seq,
                "provider": "mock",
            },
        }
        result = await worker.process_event(event, load)
        load["session_state"] = result["session_state"]

    # Process ping 3 → should trigger arrival
    event = {
        "event_id": "evt-3h-3",
        "event_type": "tracking",
        "load_id": "load-visible-001",
        "customer_id": "customer_b",
        "occurred_at": "2026-05-11T17:40:00Z",
        "tracking": {
            "tracking_id": "trk-3",
            "lat": 32.7768,
            "lng": -96.7972,
            "distance_to_delivery_miles": 0.1,
            "ping_sequence": 3,
            "provider": "mock",
        },
    }
    result = await worker.process_event(event, load)
    assert result["state"] == "at_delivery"
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    assert "update_load_state" in tools_used
    assert "cancel_timers" in tools_used
    # Forbidden
    assert "create_issue" not in tools_used
    assert "create_task" not in tools_used
    assert "update_eta" not in tools_used
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/integration/test_worker_flow.py -v`
Expected: broker test passes (deterministic); tracking test passes (deterministic)

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py tests/integration/test_worker_flow.py
git commit -m "test: integration tests for broker ignore and tracking arrival flows"
```

---

### Task 15: Eval Harness — Visible Test Cases Runner

**Files:**
- Create: `tests/eval/conftest.py`
- Create: `tests/eval/test_visible_cases.py`
- Create: `tests/eval/report.py`

- [ ] **Step 1: Write eval test file**

```python
# tests/eval/conftest.py
import json
import copy
from pathlib import Path
import pytest

FIXTURES_PATH = Path(__file__).parent.parent.parent / "assets" / "fixtures" / "test-cases.json"


@pytest.fixture
def test_cases():
    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    return data


@pytest.fixture
def base_load_data(test_cases):
    return test_cases["base_load"]
```

```python
# tests/eval/test_visible_cases.py
import pytest
import copy
import json
from app.worker import Worker


def apply_patch(load_data: dict, patch: dict) -> dict:
    """Apply load_data_patch like 'stops[1].reference_numbers.receiver_phone': null."""
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

    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]

    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]

    # Required tool calls
    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"

    # Forbidden tool calls
    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"

    # Expected state
    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
async def test_3h_tracking_three_pings(worker, test_cases, base_load_data):
    case = next(c for c in test_cases["cases"] if c["id"] == "3h_fresh_tracking_three_pings_in_geofence")
    load_row = make_load_row(base_load_data, case)

    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]

    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]

    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
        if "arguments" in req:
            matching = [tc for tc in result["tool_calls"] if tc["tool"] == req["tool"]]
            assert len(matching) > 0
            for key, val in req["arguments"].items():
                assert any(tc["arguments"].get(key) == val for tc in matching), f"Tool {req['tool']} missing arg {key}={val}"

    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"

    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
async def test_3i_driver_says_arrived(worker, test_cases, base_load_data):
    """Driver says arrived → state at_delivery + send_sms with POD + cancel_timers."""
    case = next(c for c in test_cases["cases"] if c["id"] == "3i_not_tracking_driver_says_arrived")
    load_row = make_load_row(base_load_data, case)

    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]

    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]

    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
        if "contains" in req:
            matching = [tc for tc in result["tool_calls"] if tc["tool"] == req["tool"]]
            assert any(req["contains"].lower() in str(tc["arguments"]).lower() for tc in matching), \
                f"Tool {req['tool']} missing text '{req['contains']}'"

    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"

    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
async def test_3b_load_question_found(worker, test_cases, base_load_data):
    """Driver asks for delivery address — info available → send_sms with address."""
    case = next(c for c in test_cases["cases"] if c["id"] == "3b_load_question_found")
    load_row = make_load_row(base_load_data, case)

    for event in case["events"]:
        result = await worker.process_event(event, load_row)
        load_row["session_state"] = result["session_state"]

    expected = case["expected"]
    tools_used = [tc["tool"] for tc in result["tool_calls"]]

    for req in expected.get("required_tool_calls", []):
        assert req["tool"] in tools_used, f"Missing required tool: {req['tool']}"
        if "contains" in req:
            matching = [tc for tc in result["tool_calls"] if tc["tool"] == req["tool"]]
            assert any(req["contains"] in str(tc["arguments"]) for tc in matching), \
                f"Tool {req['tool']} missing text '{req['contains']}'"

    for forbidden in expected.get("forbidden_tool_calls", []):
        assert forbidden not in tools_used, f"Forbidden tool called: {forbidden}"

    assert result["state"] == expected["expected_state"]


@pytest.mark.asyncio
async def test_3c_load_question_missing(worker, test_cases, base_load_data):
    """Driver asks for missing info → send_sms + create_task + send_slack (customer_b)."""
    case = next(c for c in test_cases["cases"] if c["id"] == "3c_load_question_missing")
    load_row = make_load_row(base_load_data, case)

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
async def test_3d_truck_broken(worker, test_cases, base_load_data):
    """Truck breakdown → create_issue(equipment_failure) + send_sms."""
    case = next(c for c in test_cases["cases"] if c["id"] == "3d_truck_broken")
    load_row = make_load_row(base_load_data, case)

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
async def test_3f_driver_provides_eta(worker, test_cases, base_load_data):
    """Driver provides ETA → update_eta + send_sms + create_timer."""
    case = next(c for c in test_cases["cases"] if c["id"] == "3f_driver_provides_eta")
    load_row = make_load_row(base_load_data, case)

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
async def test_3j_driver_sends_pod(worker, test_cases, base_load_data):
    """Driver sends POD attachment → check_attachment + update_load_state(pod_collected) + send_sms."""
    case = next(c for c in test_cases["cases"] if c["id"] == "3j_not_tracking_driver_sends_pod")
    load_row = make_load_row(base_load_data, case)

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
```

- [ ] **Step 2: Create eval report helper**

```python
# tests/eval/report.py
"""Generate eval report from pytest results."""
import json
from pathlib import Path


def generate_report(results: list[dict], output_path: str = "eval_report.md") -> None:
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    total = len(results)

    lines = [
        "# Eval Report",
        "",
        f"**Total:** {total} | **Passed:** {passed} | **Failed:** {failed}",
        "",
        "## Results",
        "",
        "| Case | Status | Notes |",
        "|------|--------|-------|",
    ]
    for r in results:
        status = "PASS" if r["status"] == "passed" else "FAIL"
        lines.append(f"| {r['name']} | {status} | {r.get('note', '')} |")

    lines.extend([
        "",
        "## Known Gaps",
        "",
        "- Agent-dependent tests (3b, 3c, 3d, 3f, 3i, 3j) require live LLM or well-tuned mock.",
        "- Hidden cases may test customer variants, multi-event sequences, or edge-case attachments.",
        "",
        "## Risky Hidden Cases",
        "",
        "- Multi-turn follow-up sequences (timer fires → re-enters worker).",
        "- Customer-specific lumper forwarding (customer_c email attachment).",
        "- Ambiguous ETA parsing ('I'll be there around 3ish').",
        "- Stale tracking ping edge case.",
    ])

    Path(output_path).write_text("\n".join(lines))
```

- [ ] **Step 3: Run eval**

Run: `uv run pytest tests/eval -v --tb=short`
Expected: deterministic cases (3k, 3h) pass; agent-dependent cases may fail in mock mode (expected, will pass with live LLM)

- [ ] **Step 4: Commit**

```bash
git add tests/eval/
git commit -m "feat: eval harness with visible case assertions and report generator"
```

---

### Task 16: Docker + docker-compose + LocalStack

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.13-slim AS base

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app/ ./app/
COPY assets/ ./assets/

ENV PYTHONPATH=/app
ENV PORT=8000

CMD ["uv", "run", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=sqs,dynamodb,scheduler
      - DEBUG=0
    volumes:
      - "./infra/localstack/init.sh:/etc/localstack/init/ready.d/init.sh"

  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - AWS_ENDPOINT_URL=http://localstack:4566
      - SQS_QUEUE_URL=http://localstack:4566/000000000000/watchtower-events.fifo
    depends_on:
      localstack:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      timeout: 3s
      retries: 5

  worker:
    build: .
    command: ["uv", "run", "python", "-m", "app.worker_sqs"]
    env_file: .env
    environment:
      - AWS_ENDPOINT_URL=http://localstack:4566
      - SQS_QUEUE_URL=http://localstack:4566/000000000000/watchtower-events.fifo
    depends_on:
      localstack:
        condition: service_healthy
```

- [ ] **Step 3: Create LocalStack init script**

```bash
mkdir -p infra/localstack
```

```bash
#!/bin/bash
# infra/localstack/init.sh
set -e

awslocal sqs create-queue \
  --queue-name watchtower-events.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=true

awslocal dynamodb create-table \
  --table-name watchtower-loads \
  --key-schema AttributeName=load_id,KeyType=HASH \
  --attribute-definitions AttributeName=load_id,AttributeType=S \
  --billing-mode PAY_PER_REQUEST

awslocal dynamodb create-table \
  --table-name watchtower-events \
  --key-schema AttributeName=load_id,KeyType=HASH AttributeName=event_id,KeyType=RANGE \
  --attribute-definitions AttributeName=load_id,AttributeType=S AttributeName=event_id,AttributeType=S \
  --billing-mode PAY_PER_REQUEST

awslocal dynamodb create-table \
  --table-name watchtower-tool-calls \
  --key-schema AttributeName=load_id,KeyType=HASH AttributeName=sort_key,KeyType=RANGE \
  --attribute-definitions AttributeName=load_id,AttributeType=S AttributeName=sort_key,AttributeType=S \
  --billing-mode PAY_PER_REQUEST

echo "LocalStack init complete"
```

- [ ] **Step 4: Create worker SQS poller module**

```python
# app/worker_sqs.py
"""SQS polling worker for docker-compose / Lambda local testing."""
from __future__ import annotations

import asyncio
import json
import time

import boto3

from app.config import settings
from app.db import DynamoDBClient
from app.observability import Logger
from app.worker import Worker


async def poll_loop():
    log = Logger()
    log.info("worker.starting", queue_url=settings.sqs_queue_url)

    kwargs = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    sqs = boto3.client("sqs", **kwargs)
    db = DynamoDBClient()
    worker = Worker()

    while True:
        try:
            resp = sqs.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10,
            )
            messages = resp.get("Messages", [])
            for msg in messages:
                body = json.loads(msg["Body"])
                load_id = body.get("load_id", "")

                # Handle load seed
                if "load_data" in body and "event_type" not in body:
                    db.put_load({
                        "load_id": body["load_id"],
                        "customer_id": body["customer_id"],
                        "state": body.get("initial_state", "on_route_to_delivery"),
                        "version": 1,
                        "load_data": body["load_data"],
                        "session_state": {},
                    })
                    sqs.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])
                    continue

                load_row = db.get_load(load_id)
                if not load_row:
                    log.error("worker.load_not_found", load_id=load_id)
                    sqs.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])
                    continue

                result = await worker.process_event(body, load_row)

                # Persist state
                db.update_load(
                    load_id=load_id,
                    new_state=result["state"],
                    session_state=result["session_state"],
                    expected_version=load_row["version"],
                )

                # Persist event record
                db.put_event({
                    "load_id": load_id,
                    "event_id": body.get("event_id", ""),
                    "event_type": body.get("event_type", ""),
                    "occurred_at": body.get("occurred_at", ""),
                    "payload": body,
                    "selected_branch": result["branch"],
                })

                # Persist tool calls
                if result["tool_calls"]:
                    db.put_tool_calls(result["tool_calls"])

                sqs.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])

        except Exception as e:
            log.error("worker.poll_error", error=str(e))
            time.sleep(1)


if __name__ == "__main__":
    asyncio.run(poll_loop())
```

- [ ] **Step 5: Test docker build locally**

Run: `cd /home/samuelbaptista/fh && docker build -t watchtower-mini .`
Expected: image builds successfully

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml infra/localstack/init.sh app/worker_sqs.py
git commit -m "feat: Docker + docker-compose with LocalStack for local dev parity"
```

---

### Task 17: Terraform IaC

**Files:**
- Create: `infra/terraform/main.tf`
- Create: `infra/terraform/variables.tf`
- Create: `infra/terraform/outputs.tf`
- Create: `infra/terraform/lambda.tf`
- Create: `infra/terraform/dynamodb.tf`
- Create: `infra/terraform/sqs.tf`
- Create: `infra/terraform/iam.tf`

- [ ] **Step 1: Create variables.tf**

```hcl
# infra/terraform/variables.tf
variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "watchtower-mini"
}

variable "open_router_api_key" {
  sensitive = true
}

variable "api_token" {
  sensitive = true
}
```

- [ ] **Step 2: Create main.tf**

```hcl
# infra/terraform/main.tf
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
```

- [ ] **Step 3: Create dynamodb.tf**

```hcl
# infra/terraform/dynamodb.tf
resource "aws_dynamodb_table" "loads" {
  name         = "${var.project_name}-loads"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "load_id"

  attribute {
    name = "load_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "events" {
  name         = "${var.project_name}-events"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "load_id"
  range_key    = "event_id"

  attribute {
    name = "load_id"
    type = "S"
  }
  attribute {
    name = "event_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "tool_calls" {
  name         = "${var.project_name}-tool-calls"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "load_id"
  range_key    = "sort_key"

  attribute {
    name = "load_id"
    type = "S"
  }
  attribute {
    name = "sort_key"
    type = "S"
  }
}
```

- [ ] **Step 4: Create sqs.tf**

```hcl
# infra/terraform/sqs.tf
resource "aws_sqs_queue" "events" {
  name                        = "${var.project_name}-events.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 60
}
```

- [ ] **Step 5: Create iam.tf**

```hcl
# infra/terraform/iam.tf
resource "aws_iam_role" "api_lambda" {
  name = "${var.project_name}-api-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "api_lambda" {
  name = "${var.project_name}-api-policy"
  role = aws_iam_role.api_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [aws_sqs_queue.events.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = [aws_dynamodb_table.loads.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"]
      }
    ]
  })
}

resource "aws_iam_role" "worker_lambda" {
  name = "${var.project_name}-worker-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "worker_lambda" {
  name = "${var.project_name}-worker-policy"
  role = aws_iam_role.worker_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = [aws_sqs_queue.events.arn]
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:BatchWriteItem"]
        Resource = [
          aws_dynamodb_table.loads.arn,
          aws_dynamodb_table.events.arn,
          aws_dynamodb_table.tool_calls.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["scheduler:CreateSchedule", "scheduler:DeleteSchedule", "scheduler:ListSchedules"]
        Resource = ["arn:aws:scheduler:${var.aws_region}:${data.aws_caller_identity.current.account_id}:schedule/default/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [aws_iam_role.scheduler.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"]
      }
    ]
  })
}

resource "aws_iam_role" "scheduler" {
  name = "${var.project_name}-scheduler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "${var.project_name}-scheduler-policy"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = [aws_sqs_queue.events.arn]
    }]
  })
}
```

- [ ] **Step 6: Create lambda.tf**

```hcl
# infra/terraform/lambda.tf
resource "aws_ecr_repository" "app" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-api"
  role          = aws_iam_role.api_lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:latest"
  timeout       = 30
  memory_size   = 512

  environment {
    variables = {
      API_TOKEN            = var.api_token
      OPEN_ROUTER_API_KEY  = var.open_router_api_key
      SQS_QUEUE_URL        = aws_sqs_queue.events.url
      DYNAMODB_LOADS_TABLE = aws_dynamodb_table.loads.name
      DYNAMODB_EVENTS_TABLE = aws_dynamodb_table.events.name
      DYNAMODB_TOOL_CALLS_TABLE = aws_dynamodb_table.tool_calls.name
      AWS_LWA_INVOKE_MODE  = "response_stream"
    }
  }
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_function" "worker" {
  function_name = "${var.project_name}-worker"
  role          = aws_iam_role.worker_lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:latest"
  timeout       = 60
  memory_size   = 512

  environment {
    variables = {
      HANDLER              = "worker"
      OPEN_ROUTER_API_KEY  = var.open_router_api_key
      SQS_QUEUE_URL        = aws_sqs_queue.events.url
      DYNAMODB_LOADS_TABLE = aws_dynamodb_table.loads.name
      DYNAMODB_EVENTS_TABLE = aws_dynamodb_table.events.name
      DYNAMODB_TOOL_CALLS_TABLE = aws_dynamodb_table.tool_calls.name
      SCHEDULER_ROLE_ARN   = aws_iam_role.scheduler.arn
      SCHEDULER_TARGET_ARN = aws_sqs_queue.events.arn
    }
  }
}

resource "aws_lambda_event_source_mapping" "worker_sqs" {
  event_source_arn = aws_sqs_queue.events.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1
  enabled          = true
}
```

- [ ] **Step 7: Create outputs.tf**

```hcl
# infra/terraform/outputs.tf
output "api_url" {
  value = aws_lambda_function_url.api.function_url
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "sqs_queue_url" {
  value = aws_sqs_queue.events.url
}
```

- [ ] **Step 8: Verify terraform validates**

Run: `cd /home/samuelbaptista/fh/infra/terraform && terraform init && terraform validate`
Expected: "Success! The configuration is valid."

- [ ] **Step 9: Commit**

```bash
git add infra/terraform/
git commit -m "feat: Terraform IaC for Lambda + DynamoDB + SQS + EventBridge"
```

---

### Task 18: Wire API to Queue + DB (connect enqueue_event)

**Files:**
- Modify: `app/api.py`

- [ ] **Step 1: Update api.py to use real queue + db clients**

```python
# Replace the stub enqueue_event in app/api.py with:
from app.db import DynamoDBClient
from app.queue import SQSClient

_db: DynamoDBClient | None = None
_queue: SQSClient | None = None


def get_db() -> DynamoDBClient:
    global _db
    if _db is None:
        _db = DynamoDBClient()
    return _db


def get_queue() -> SQSClient:
    global _queue
    if _queue is None:
        _queue = SQSClient()
    return _queue


async def enqueue_event(event_data: dict, load_id: str) -> None:
    get_queue().send_event(event_data, load_id)
```

Update `/loads` to also persist load:
```python
@app.post("/loads", status_code=202, response_model=AcceptedResponse)
async def create_load(body: LoadSeedRequest, _token: AuthDep = "") -> AcceptedResponse:
    event_id = f"evt-seed-{uuid.uuid4().hex[:8]}"
    # Persist load first
    get_db().put_load({
        "load_id": body.load_id,
        "customer_id": body.customer_id,
        "state": body.initial_state or "on_route_to_delivery",
        "version": 1,
        "load_data": body.load_data.model_dump(),
        "session_state": {},
    })
    return AcceptedResponse(event_id=event_id, load_id=body.load_id)
```

- [ ] **Step 2: Run existing tests (ensure mocks still work)**

Run: `uv run pytest tests/unit/test_api.py -v`
Expected: all pass (tests mock enqueue_event)

- [ ] **Step 3: Commit**

```bash
git add app/api.py
git commit -m "feat: wire API endpoints to DynamoDB + SQS clients"
```

---

### Task 19: Lambda Handler Entrypoint

**Files:**
- Create: `app/lambda_handler.py`

- [ ] **Step 1: Create Lambda handler**

```python
# app/lambda_handler.py
"""Lambda entrypoint — routes to API (via mangum) or worker depending on HANDLER env."""
from __future__ import annotations

import asyncio
import json
import os

from app.config import settings
from app.db import DynamoDBClient
from app.observability import Logger
from app.worker import Worker


_worker: Worker | None = None
_db: DynamoDBClient | None = None


def get_worker() -> Worker:
    global _worker
    if _worker is None:
        _worker = Worker()
    return _worker


def get_db() -> DynamoDBClient:
    global _db
    if _db is None:
        _db = DynamoDBClient()
    return _db


def handler(event, context):
    """Route to API or worker based on HANDLER env var."""
    if os.environ.get("HANDLER") == "worker":
        return worker_handler(event, context)

    # Default: API via mangum
    from mangum import Mangum
    from app.api import app
    mangum_handler = Mangum(app, lifespan="off")
    return mangum_handler(event, context)


def worker_handler(event, context):
    """Process SQS messages."""
    log = Logger()
    db = get_db()
    worker = get_worker()

    records = event.get("Records", [])
    for record in records:
        body = json.loads(record["body"])
        load_id = body.get("load_id", "")
        event_id = body.get("event_id", "")

        log.info("sqs.message_received", load_id=load_id, event_id=event_id)

        load_row = db.get_load(load_id)
        if not load_row:
            log.error("worker.load_not_found", load_id=load_id)
            continue

        result = asyncio.get_event_loop().run_until_complete(
            worker.process_event(body, load_row)
        )

        db.update_load(
            load_id=load_id,
            new_state=result["state"],
            session_state=result["session_state"],
            expected_version=load_row["version"],
        )

        db.put_event({
            "load_id": load_id,
            "event_id": event_id,
            "event_type": body.get("event_type", ""),
            "occurred_at": body.get("occurred_at", ""),
            "payload": body,
            "selected_branch": result["branch"],
        })

        if result["tool_calls"]:
            db.put_tool_calls(result["tool_calls"])

    return {"statusCode": 200}
```

- [ ] **Step 2: Update Dockerfile CMD for Lambda**

```dockerfile
# Update the CMD line to:
CMD ["app.lambda_handler.handler"]
```

Note: For Lambda container images we actually need the AWS Lambda Runtime Interface Client (RIC). Alternative: use Lambda Web Adapter for the API lambda and `aws-lambda-ric` for the worker. Simplification: use `mangum` for API and native handler for worker.

- [ ] **Step 3: Commit**

```bash
git add app/lambda_handler.py
git commit -m "feat: Lambda handler entrypoint routing API (mangum) and worker (SQS)"
```

---

### Task 20: CLAUDE.md + README + .env.example + AI_USAGE.md

**Files:**
- Create: `CLAUDE.md`
- Modify: `README.md`
- Create: `docs/AI_USAGE.md`

- [ ] **Step 1: Create CLAUDE.md**

```markdown
# Watchtower Mini

## Quick Reference
- `make install` — install deps
- `make test` — unit tests
- `make eval` — eval harness (visible cases)
- `make up` / `make down` — docker-compose with LocalStack
- `make run` — local dev server (no queue)
- `make lint` / `make format` — ruff

## Architecture
FastAPI → SQS FIFO → Worker → Dispatcher (deterministic) + Agent (Pydantic AI/OpenRouter) → DynamoDB

## Key Decisions
- Hybrid SOP routing: deterministic for broker filter, tracking, channel match; agent for classification + drafting
- Customer policy: typed YAML in `assets/customers/`
- Tools: mocked, recorded in `tool_calls` table
- Timers: EventBridge Scheduler → SQS
- State: DynamoDB with optimistic locking (version attribute)

## Testing
- Unit: `tests/unit/` — fast, no AWS deps (moto for DynamoDB tests)
- Integration: `tests/integration/` — worker flow end-to-end in-process
- Eval: `tests/eval/` — visible fixture cases with tool call assertions

## Deployment
- Terraform in `infra/terraform/`
- Docker image → ECR → Lambda (API + Worker share image)
- Public endpoint: Lambda Function URL
```

- [ ] **Step 2: Create README.md**

```markdown
# Watchtower Mini

AI agent system for freight load event processing. Handles ETA checkpoints and delivery confirmation workflows with customer-specific behavior.

## Quick Start

```bash
# Install
uv sync --all-extras

# Run unit tests
make test

# Run eval harness
make eval

# Local dev (docker-compose + LocalStack)
make up
# then: curl -H "Authorization: Bearer dev-token-local" http://localhost:8000/health
```

## API Endpoints

All require `Authorization: Bearer <API_TOKEN>` header.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/loads` | Create/seed a load |
| POST | `/submit-task` | Submit workflow task |
| POST | `/events/inbound-communication` | Inbound SMS/email |
| POST | `/events/tracking` | Tracking ping |
| POST | `/events/load-update` | Load data update |

## Run Evals

```bash
# In-process (fast, mock LLM)
make eval

# Against live endpoint
API_URL=https://your-deployed-url LLM_MODE=live make eval
```

## Deploy

```bash
cd infra/terraform
terraform init
terraform apply -var="open_router_api_key=$OPEN_ROUTER_API_KEY" -var="api_token=$API_TOKEN"
```

## Architecture

See `docs/architecture.md` for full write-up.
```

- [ ] **Step 3: Create docs/AI_USAGE.md**

```markdown
# AI Usage Disclosure

## Tools Used
- Claude Code (Anthropic) — primary coding assistant
- Claude Opus 4.6 — model powering the assistant

## What Was AI-Generated or Heavily Assisted
- Initial project scaffold and boilerplate
- Pydantic model definitions from JSON Schema
- Mock tool implementations
- Terraform resource definitions
- Docker and docker-compose configuration
- Test structure and assertion patterns

## Manual Decisions
- Architecture choices (Lambda + SQS + DynamoDB, not ECS/RDS)
- Hybrid SOP routing design (deterministic gates + agent for ambiguous cases)
- Customer policy as typed YAML rather than prompt fragments
- Model fallback strategy (real multi-provider via OpenRouter)
- Eval harness design (in-process + HTTP runners)
- Security posture (bearer token, least-privilege IAM)

## AI Output Rejected or Corrected
- [To be filled during implementation]
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md docs/AI_USAGE.md
git commit -m "docs: add CLAUDE.md, README, and AI_USAGE.md"
```

---

### Task 21: Deploy + Live Test Evidence

**Files:**
- None new — operational task

- [ ] **Step 1: Build and push Docker image**

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and tag
docker build -t watchtower-mini .
docker tag watchtower-mini:latest <ecr-url>:latest

# Push
docker push <ecr-url>:latest
```

- [ ] **Step 2: Deploy Terraform**

```bash
cd infra/terraform
terraform apply -var="open_router_api_key=$OPEN_ROUTER_API_KEY" -var="api_token=$API_TOKEN" -auto-approve
```

- [ ] **Step 3: Run live test against deployed endpoint**

```bash
API_URL=$(terraform output -raw api_url)
curl -X POST "$API_URL/health"
curl -X POST "$API_URL/loads" -H "Authorization: Bearer $API_TOKEN" -H "Content-Type: application/json" -d @tests/fixtures/seed_load.json
```

- [ ] **Step 4: Capture JSONL trace evidence**

```bash
# After running a test case against the live endpoint, pull CloudWatch logs
# or check the runs/ directory for JSONL artifacts
```

- [ ] **Step 5: Commit trace evidence**

```bash
git add runs/
git commit -m "evidence: deployed run trace artifacts"
```

---

### Task 22: GitHub Repo Setup + Push

**Files:**
- None — operational task

- [ ] **Step 1: Resolve GitHub auth for SamuelBaptista**

```bash
# Switch gh CLI to personal account or use token
gh auth login --with-token <<< "$PERSONAL_GITHUB_TOKEN"
# OR use git credential for HTTPS with personal token
```

- [ ] **Step 2: Create public repo**

```bash
gh repo create SamuelBaptista/fh --public --source=. --push
```

- [ ] **Step 3: Verify repo is public and accessible**

```bash
gh repo view SamuelBaptista/fh --web
```

---

## Execution Notes

**Task ordering**: Tasks 1-11 can be built sequentially, testing each unit in isolation. Task 12 (DB) can run parallel with Tasks 5-9 since they are independent. Tasks 14-15 (integration + eval) depend on Tasks 7-10. Task 16 (Docker) can run anytime after Task 11. Task 17 (Terraform) is independent of application code.

**Agent-dependent evals**: Tests for cases 3b, 3c, 3d, 3f, 3i, 3j require the LLM to classify intent and plan tool calls correctly. In `LLM_MODE=mock` they'll use canned responses. For real passing, run with `LLM_MODE=live`.

**Hidden case preparedness**: The deterministic dispatcher handles broker-ignore and tracking arrival without LLM. Agent-dependent cases rely on prompt quality. Customer YAML extensibility means hidden customer variants just need a new file.
