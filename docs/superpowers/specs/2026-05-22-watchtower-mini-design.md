# Watchtower Mini — Design Spec

**Date**: 2026-05-22
**Author**: Samuel Baptista
**Status**: Draft for review
**Challenge source**: `technical_challenge.txt` (FreightHero AI Engineer take-home)

## Goal

Production-shaped slice of the FreightHero Watchtower system covering two workflows:

1. **On Route to Delivery / ETA Checkpoint** — monitor ETA, tracking pings, driver questions, operational exceptions.
2. **Confirm Delivery** — confirm unloading, validate POD, handle lumper receipts, follow-ups.

Must process visible cases in `assets/fixtures/test-cases.json` and remain easy to run against hidden variants. Production-shaped, not feature-complete. Deployed to a real cloud endpoint.

## Non-Goals

- Real OCR (use fixture-provided attachment metadata + mock `check_attachment`).
- Real SMS/email/Slack delivery (mocked tools, recorded calls).
- Multi-region, autoscaling tuning, or other ops sophistication beyond review needs.
- Read APIs for load/event state (challenge explicitly does not require).
- Any persistence path beyond per-load session state needed to pass evals.

## Required Properties (from challenge)

- API and agent execution decoupled by a queue or durable async work mechanism.
- Per-load state persisted outside process memory.
- Events for the same load isolated from other loads, safe under concurrency.
- Agent behavior driven by SOP content + customer-specific differences.
- Tools mocked but recorded and testable.
- Containerized.
- Deployed in a real cloud account via IaC.
- Model fallback strategy.
- Short-term per-load session state for follow-ups.
- Public write endpoints: `POST /loads`, `POST /submit-task`, `POST /events/inbound-communication`, `POST /events/tracking`, `POST /events/load-update`.
- Scheduled follow-ups modeled as time-based events, not as a `task_instruction_type`.
- Eval harness with single command, assertions over tool calls + state transitions.

## Architectural Choices (with rationale, for write-up)

| Concern | Choice | Why |
|---|---|---|
| Cloud | AWS, free-tier first | OpenRouter key already provided; throwaway eval traffic; idle cost ~$0 on Lambda/SQS/DynamoDB free tiers. |
| API | FastAPI on Lambda (container image, Lambda Web Adapter) exposed via Lambda Function URL | Containerized + cheap + scales to zero. Function URL avoids API Gateway cost and Terraform sprawl; same image runs locally via docker-compose. |
| Queue | SQS FIFO, `MessageGroupId = load_id` | In-order per load, parallel across loads, free tier covers eval volume. |
| Worker | Lambda triggered by SQS | Same container image; `MAIN=worker` env switches entrypoint. |
| State | DynamoDB (3 tables: `loads`, `events`, `tool_calls`) | Always-free idle; conditional updates give optimistic concurrency safety net under FIFO. |
| Timers | EventBridge Scheduler one-off schedules → SQS message | Free tier (14M invocations/mo), separate from `/submit-task`, re-enters worker like any event. |
| Agent framework | Pydantic AI | Lightweight, type-safe tool calls, OpenAI-compatible client, OTel-friendly, no LangChain weight. |
| LLM | OpenRouter; primary `anthropic/claude-sonnet-4.5`, fallback `openai/gpt-4o-mini` | One auth, two real providers — real fallback story, not a mock. |
| SOP organization | Hybrid: deterministic router + typed customer policy + agent for classification & drafting | Bulletproof on tracking math, broker filter, geofence, channel match; LLM only for classification + message drafting; scales by adding YAML, not code. |
| Local dev | docker-compose with LocalStack (SQS + DynamoDB + EventBridge) | Full parity to cloud, single command up, no AWS calls during dev. |
| IaC | Terraform | Common, simple state file in S3 backend (or local for one-shot deploy). |
| Observability | Structured JSON logs (CloudWatch + stdout) + JSONL trace artifact per run | Free, satisfies rubric trace surfaces, easy to attach to submission. |

### Why not LangGraph
LangSmith trace integration is the main draw; LangSmith is paid past the free tier and adds a vendor dependency. LangGraph itself works without LangSmith but adds dependency surface. Pydantic AI is lighter, OTel-native, and the SOP routing benefits of an explicit graph are achieved more reliably with deterministic Python branching here (the rubric explicitly rewards declarative customer behavior).

### Why hybrid SOP routing
- Deterministic gates (broker filter, 3-pings-arrival, channel match, geofence radius) are exact rules — putting them behind an LLM costs accuracy and money for no benefit.
- Customer policy is a small typed object; YAML scales by adding files, not by editing prompts.
- Agent owns what is genuinely ambiguous: intent classification, ETA parsing, attachment-vs-text reconciliation, message drafting.
- Tool wrappers (e.g. `escalate(reason)`) read customer policy and dispatch one or more raw tool calls — keeps the agent prompt simple while keeping behavior declarative.

## System Architecture

```
                     ┌──────────────┐
   POST /loads ─────▶│              │
   POST /submit-task▶│   FastAPI    │──── put ───▶ SQS FIFO ──▶ Worker (Lambda)
   POST /events/* ──▶│   (Lambda)   │                              │
                     │              │                              ▼
                     └──────────────┘                       ┌─────────────┐
                            │                               │  Dispatcher │
                            ▼                               │  (per-load) │
                       DynamoDB                             └──────┬──────┘
                       loads/events                                │
                                                  ┌────────────────┴────────────────┐
                                                  ▼                                 ▼
                                          deterministic                       Pydantic AI
                                          router                              agent
                                          (broker filter,                     (classify intent,
                                           tracking math,                      draft text)
                                           channel match)                          │
                                                  │                                ▼
                                                  └─────────────┬──────────tool wrappers
                                                                ▼
                                                       mocked tools (record to tool_calls)
                                                                │
                                                                ▼
                                                       update load state
                                                       schedule timers
                                                       (EventBridge Scheduler)
                                                                │
                                                                └─── fires ──▶ SQS FIFO
```

## Components

### `app.api`
- FastAPI app, validates payloads against Pydantic models translated from `challenge-input.schema.json`.
- Endpoints push events onto SQS FIFO with `MessageGroupId = load_id`.
- `POST /loads` writes initial `Load` row to DynamoDB *before* enqueueing any event.
- `POST /submit-task` enqueues a synthetic event tagged `task_instruction_type` so the worker can run the workflow with seeded context (fresh first-arrival contact for `confirm_delivery`, etc.).
- Returns 202 with `event_id`.

### `app.worker`
- Single SQS message → process one event end-to-end.
- Reads load row + session state with consistent read.
- Runs through the **dispatcher**.
- Writes new state, appends to `events`, appends tool calls to `tool_calls`.
- Updates DynamoDB with conditional `version` increment.

### `app.dispatcher`
Deterministic Python — *not* the LLM:
- If sender is broker → log "broker_ignored" reason, no further action.
- If event is tracking ping → run `tracking.update_streak(load, ping, customer.geofence_miles)`.
  - 3 consecutive fresh in-geofence → arrival → state `at_delivery`, cancel timers, hand off to confirm-delivery first-arrival flow.
  - else → keep state, may schedule ETA follow-up if streak resets.
- If event is inbound comm or task instruction → invoke **agent** with: workflow SOP prompt + customer policy + load context + recent session state + the event payload.
- Agent returns intent label + drafted text (when needed) + structured action plan.
- Dispatcher executes the plan via tool wrappers, writes records.

### `app.agent`
- Pydantic AI Agent with typed `Decision` output: intent, branch, reasoning, planned tool calls.
- Tools registered as Pydantic AI tools that delegate to `app.tools` wrappers.
- System prompt composed from: shared workflow SOP markdown + customer policy section rendered from typed config + communication guardrails.
- `model_settings` configured with primary model; fallback path on retryable errors.

### `app.customer`
- `CustomerPolicy` Pydantic model (typed fields):
  - `geofence_miles: float`
  - `eta_followup_minutes: int`
  - `escalation_channels: list[Literal["email", "slack"]]`
  - `pod_validation: Literal["automatic", "human_review"]`
  - `pod_received_visibility: bool`
  - `delivered_no_pod_visibility: bool`
  - `missing_info_visibility: bool`
  - `lumper_strategy: Literal["review_task", "forward_email_for_email_attachments"]`
  - `first_arrival_message: str`  (template)
- One YAML per customer in `assets/customers/customer_a.yaml` etc., loaded at startup, validated on load.
- Adding customer D = new file. No code change needed unless a brand-new policy axis appears.

### `app.tools`
- Mocked implementations for every contract in `assets/tools.md`.
- Each call appends a record to `tool_calls` (DynamoDB) and to per-event JSONL.
- High-level wrappers used by the dispatcher/agent:
  - `escalate(reason, customer_policy)` → fans out to email + slack tools per `escalation_channels`.
  - `notify_visibility(event, customer_policy)` → reads visibility flags.
  - `handle_attachments(event, customer_policy)` → loops attachments through `check_attachment`, applies POD/lumper/other rules.

### `app.timer`
- `schedule(timer_type, fire_at_utc, load_id, payload)` → EventBridge Scheduler create one-off schedule with target = SQS queue, message body is a synthetic timer event.
- `cancel(timer_id)` / `cancel_by_type(load_id, timer_type)` / `cancel_all(load_id)`.
- Local: LocalStack EventBridge Scheduler.

### `app.session`
- Session state lives on the `loads` row (`session_state` JSON attribute).
- Holds: rolling 10 events, ping-streak counter, last-known ETA, attachments seen, pending follow-ups.
- Read & rewritten on every worker invocation under conditional update.

### `app.observability`
- `bind_context(load_id, event_id, request_id)` context vars.
- Structured logger emits one `event.received`, one `event.processed`, one log per tool call, one per state transition.
- Each event's logs are written to JSONL artifact at `runs/<event_id>.jsonl` for eval/debug.
- AWS Lambda → CloudWatch automatically picks up stdout JSON.

## Data Model

### `loads` table
- PK: `load_id` (string)
- attrs: `customer_id`, `state`, `version` (number), `load_data` (json), `session_state` (json), `created_at`, `updated_at`
- Conditional updates on `version` for concurrency safety.

### `events` table
- PK: `load_id` (string), SK: `event_id` (string)
- attrs: `event_type`, `occurred_at`, `payload`, `processed_at`, `selected_branch`, `decision_reason`, `final_state`

### `tool_calls` table
- PK: `load_id` (string), SK: `created_at#tool_call_id`
- attrs per `tools.md`: `tool_call_id`, `event_id`, `tool`, `arguments`, `result`, `created_at`
- GSI optional: `event_id-index` (PK `event_id`, SK `created_at`) for eval queries.

## Event Flow Examples

### Inbound SMS "What's the delivery address?" (customer_a)
1. API validates, enqueues to SQS with `MessageGroupId = load_id`.
2. Worker pulls message, loads `Load` from Dynamo, builds session.
3. Dispatcher: sender = driver, channel = sms → call agent.
4. Agent classifies intent = `load_information_question`, returns plan calling `get_load_info("delivery_address")` then `send_sms` with the value.
5. Tools execute, records appended.
6. State unchanged. Worker updates `loads` with version increment.

### Tracking ping streak reaches 3 inside 2-mile geofence (customer_b)
1. API enqueues each ping.
2. Worker handles ping 1 → streak=1, no state change.
3. Worker handles ping 2 → streak=2.
4. Worker handles ping 3 → streak=3, in geofence ≤ 2mi → arrival → `update_load_state("at_delivery")` + `cancel_timers()`. Hand off to confirm-delivery first-arrival contact (drafts message per customer_b policy on next eligible event).

### Broker email arrives
1. API enqueues.
2. Worker dispatcher: sender = broker → log `broker_ignored`, write event with `selected_branch = "broker_ignored"`, no tools called.
3. Done. Eval asserts no forbidden tool calls.

### Driver provides ETA "ETA delivery 2:30pm central" (customer_c)
1. Agent classifies `driver_provides_eta`. Calls `validate_eta(raw, "America/Chicago")`, then `update_eta(...)`, then `send_sms("ETA updated...")`, then `create_timer("eta_followup", now + 45 min, ...)`.
2. State unchanged.

### Lumper receipt via email (customer_c, special rule)
1. Attachment classified as `lumper_receipt` AND channel == email → `forward_email()` to broker special address.
2. POD handling continues independently (rule says "make sure POD handling is not skipped").

## Public API

| Method | Path | Body |
|---|---|---|
| POST | `/loads` | `load_seed_request` |
| POST | `/submit-task` | `submit_task_request` |
| POST | `/events/inbound-communication` | `inbound_communication_event` |
| POST | `/events/tracking` | `tracking_event` |
| POST | `/events/load-update` | `load_update_event` |

All endpoints: 202 + `{event_id}`. Validation via Pydantic models that mirror `challenge-input.schema.json`.

## Eval Harness

- `tests/eval/cases.py` reads `assets/fixtures/test-cases.json`.
- For each case: seed load (apply `load_data_patch` if present) → enqueue events sequentially → wait for processing → assert.
- Two runners:
  - **`runner=inproc`** (default): bypass SQS, call worker handler directly with each event. Fast, deterministic, what CI runs.
  - **`runner=http`**: hit a running endpoint (local docker-compose or deployed URL). Used for live verification.
- Assertions:
  - For each `required_tool_calls`: matching tool was called with matching args/contains.
  - For each `forbidden_tool_calls`: tool was *not* called.
  - Final load state == `expected_state`.
- Single command: `make eval` (or `uv run python -m app.eval`).
- Output: JSON report + markdown summary + JSONL trace per case.

## Observability Strategy

- **Structured logs**: every log line is JSON with `load_id`, `event_id`, `request_id`, `event_type`, `selected_branch`, `customer_id`, plus event-specific fields.
- **Tool call records**: written to `tool_calls` table AND JSONL artifact. Each record has `tool`, `arguments`, `result`, timestamps, `event_id`, `load_id`.
- **State transitions**: dedicated log line `state_change` whenever load state moves.
- **Trace artifact**: `runs/<event_id>.jsonl` is committed for at least one deployed run as evidence.
- **Cost/latency**: log model name + token counts + duration per LLM call.

## Model Fallback

- Primary: `anthropic/claude-sonnet-4.5` via OpenRouter.
- Fallback: `openai/gpt-4o-mini` via OpenRouter on retryable errors (`5xx`, rate limit, timeout).
- Implementation: thin wrapper around Pydantic AI's model client that catches retryable exceptions, swaps to fallback model, retries once, logs which model handled the call.
- Configurable via env: `LLM_PRIMARY`, `LLM_FALLBACK`, `LLM_MODE` (`live` | `mock` for offline runs).

## Deployment

- Terraform under `infra/terraform/` provisions:
  - DynamoDB tables (`loads`, `events`, `tool_calls`)
  - SQS FIFO queue (with content-based dedup)
  - Lambda function (API) + Lambda Function URL (public, no auth toggle)
  - Lambda function (worker) + SQS event source mapping
  - EventBridge Scheduler IAM role
  - Secrets in AWS Secrets Manager (OpenRouter key, etc.) referenced by Lambda env
  - CloudWatch log groups
  - IAM least-privilege per Lambda
- Single image built via Dockerfile, pushed to ECR.
- Two Lambda functions share the image; `HANDLER` env decides entrypoint.
- Public endpoint = Lambda Function URL.
- Secrets: `.env` for local, AWS Secrets Manager for cloud, never committed.

## Security & Least Privilege

- API Lambda IAM: `sqs:SendMessage` on the FIFO queue, `dynamodb:PutItem`/`UpdateItem`/`GetItem` on `loads` only, `secretsmanager:GetSecretValue` on the OpenRouter secret.
- Worker Lambda IAM: SQS receive/delete, full CRUD on the three tables, scheduler create/delete, secrets read.
- No `*` resources in policies.
- Env vars never hold the OpenRouter key in cloud (Secrets Manager). Local uses `.env`.
- Authorization on the public API: optional bearer token via env `API_KEY` (skipped if unset for review convenience; documented as a tradeoff).

## Repository Layout

```
fh/
├── app/
│   ├── __init__.py
│   ├── api.py
│   ├── worker.py
│   ├── dispatcher.py
│   ├── agent.py
│   ├── customer.py
│   ├── tools.py
│   ├── timer.py
│   ├── session.py
│   ├── observability.py
│   ├── llm.py
│   ├── models.py            # pydantic models for events / load
│   └── eval/
│       ├── __init__.py
│       └── runner.py
├── assets/                  # provided
│   ├── customers/           # NEW: customer_a.yaml, customer_b.yaml, customer_c.yaml
│   ├── sops/                # provided
│   └── ...
├── infra/
│   └── terraform/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── eval/
├── docs/
│   ├── architecture.md      # write-up for submission
│   ├── AI_USAGE.md
│   └── superpowers/specs/
├── runs/                    # JSONL trace artifacts
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
├── .env.example
└── README.md
```

## Risks / Gaps / Tradeoffs

- **Single-region**, single-AZ for cost. Documented.
- **Cold start on Lambda** ~1–2s per first invocation. Acceptable for review traffic.
- **No real auth** on public endpoints by default. Documented as deliberate tradeoff for review convenience.
- **Hidden customer behavior axes**: if hidden tests introduce a new policy axis, hybrid still requires a code change for the tool wrapper. Mitigation: prefer adding fields to `CustomerPolicy` rather than new branches in the dispatcher.
- **Long context**: short rolling session window (10 events). Hidden multi-turn tests beyond 10 events may lose context. Documented.
- **Concurrency**: SQS FIFO + DynamoDB conditional updates is the fail-safe. SQS FIFO alone is enough; the conditional check is belt-and-suspenders.

## Out-of-Scope (intentional)

- Read APIs for load/event state.
- Real OCR.
- Real model providers beyond OpenRouter.
- Multi-region.
- A frontend.
- Production-grade autoscaling tuning.
