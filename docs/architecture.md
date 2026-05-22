# Architecture Write-Up

## System Overview

Watchtower Mini is a production-shaped AI agent system that processes freight load events through two workflows:

1. **On Route to Delivery / ETA Checkpoint** — monitors delivery ETA, tracking pings, driver questions, and operational exceptions
2. **Confirm Delivery** — confirms unloading, collects/validates POD, handles lumper receipts, manages follow-ups

## Design Philosophy

**Production-shaped, not feature-complete.** The system demonstrates how to build an agentic application that is observable, testable, and deployable while respecting the constraints of a one-week timebox.

**Hybrid routing.** The core insight is that not every decision needs an LLM:
- Broker filtering: exact rule (sender_type == "broker" → ignore)
- Tracking arrival: exact math (3 consecutive pings inside geofence radius)
- Channel matching: exact rule (reply on same channel as inbound)
- Everything else: LLM classifies intent and plans tool calls

This reduces cost, improves reliability for deterministic cases, and makes the system easier to test.

## Component Architecture

### API Layer (FastAPI on ECS Fargate + ALB)
- Validates incoming requests against Pydantic models
- Authenticates via bearer token
- Persists load data to DynamoDB (for `/loads`)
- Enqueues events to SQS FIFO with `MessageGroupId = load_id`
- Returns 202 immediately — processing is async
- Exposed via Application Load Balancer on HTTP port 80

### Queue (SQS FIFO)
- `MessageGroupId = load_id` ensures in-order processing per load
- Parallel processing across different loads
- Content-based deduplication prevents duplicate processing
- Visibility timeout of 60s accommodates LLM latency

### Worker (ECS Fargate service with SQS polling)
- Long-polls SQS FIFO queue for events
- Reads load state from DynamoDB (consistent read)
- Routes event through Dispatcher (deterministic) or Agent (LLM)
- Executes tool calls, records them
- Updates load state with optimistic locking (version field)
- Writes JSONL trace artifacts

### Dispatcher
- Deterministic Python — no LLM calls
- Broker filter: immediate no-action for broker messages
- Tracking geofence: counts consecutive in-geofence pings, triggers arrival at 3
- Routes driver/dispatcher communications to Agent

### Agent
- Receives: SOP markdown + customer policy + event + load data + session context
- Returns: structured JSON decision (intent, branch, reasoning, tool_calls, draft_message)
- Fallback: Claude Sonnet 4.6 → GPT-4o-mini on retryable errors
- Mock mode for offline testing

### Customer Policy
- Typed YAML files in `app/config/customers/`
- One file per customer with all behavior parameters
- Adding a customer = adding a file, no code changes
- Policy fields cover: geofence, ETA timing, escalation channels, POD validation, lumper handling, visibility rules, first-arrival message

### Tools
- All tools are mocked but behave like production boundaries
- Every call produces a `ToolCallRecord` with load_id, event_id, tool name, arguments, result, timestamp
- Records stored in DynamoDB and JSONL trace files
- Eval harness asserts on these records

## Concurrency Safety

1. **SQS FIFO MessageGroupId**: guarantees per-load ordering
2. **DynamoDB conditional updates**: version increment prevents stale-write conflicts
3. **Belt and suspenders**: FIFO alone is sufficient; conditional update is the safety net

## Timer Design

Timers are scheduled follow-ups that re-enter the worker as events:
- Implemented via EventBridge Scheduler one-off schedules
- Target: SQS FIFO queue with `MessageGroupId = load_id`
- On fire: synthetic `timer_fired` event processed like any other event
- Cancel: delete the schedule by name

This keeps timers separate from `/submit-task` (as required) while using the same processing pipeline.

## Observability

- Structured JSON logs: every log line has load_id, event_id, event_type, customer_id, branch, model
- JSONL trace files: per-event artifacts in `runs/` directory
- Tool call records: queryable in DynamoDB for eval
- LLM metadata: model name, token counts, duration per call, fallback flag

## Tradeoffs

| Decision | Tradeoff |
|----------|----------|
| ECS Fargate vs Lambda | Better for long-running operations and simpler container deployment, but always-on costs more than Lambda scale-to-zero |
| DynamoDB vs Postgres | Free tier, no connection pooling needed, but less flexible queries |
| Mock tools vs real | Faster dev, testable, but no real delivery verification |
| Hybrid routing vs pure-agent | More code to maintain, but deterministic cases are bullet-proof |
| SQS FIFO vs standard | Guaranteed ordering per load, but throughput cap (300 msg/s per group) |
| Single-region | No HA, but adequate for evaluation traffic |
| ALB vs API Gateway | Simpler for container-based services, HTTP only (no custom domains needed for eval) |

## What I Would Do Differently With More Time

1. **Live eval pass rate**: tune the agent prompt to achieve >90% on all visible cases with live LLM
2. **Multi-turn session context**: richer session state for follow-up events that reference prior context
3. **Timer integration test**: end-to-end test where a timer fires and re-enters the worker
4. **Metrics dashboard**: CloudWatch dashboard with key indicators (latency, error rate, model usage)
5. **Customer config validation**: schema enforcement on YAML + integration tests per customer
6. **Prompt versioning**: track prompt versions in traces for A/B comparison
7. **Rate limiting**: per-customer rate limits on the public API
