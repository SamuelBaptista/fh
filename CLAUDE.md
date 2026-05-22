# Watchtower Mini

FreightHero AI Engineer take-home challenge. AI agent system for freight load event processing.

## Commands

```bash
uv sync --all-extras        # Install all deps
make test                   # Unit tests
make eval                   # Eval harness (visible fixture cases)
make lint                   # Ruff check
make format                 # Ruff format
make up                     # docker-compose up (LocalStack + API + Worker)
make down                   # docker-compose down
make run                    # Local dev server (uvicorn, no queue)
```

## Architecture

```
FastAPI (Lambda) → SQS FIFO (MessageGroupId=load_id) → Worker (Lambda)
                                                          │
                                              Dispatcher (deterministic)
                                              + Agent (Pydantic AI / OpenRouter)
                                                          │
                                              DynamoDB (loads/events/tool_calls)
```

- **Dispatcher**: handles broker filter, tracking geofence math, channel routing — no LLM needed
- **Agent**: handles intent classification, message drafting, ambiguous cases — uses LLM
- **Customer policy**: typed YAML in `assets/customers/` — add customer = add file
- **Timers**: EventBridge Scheduler → SQS (re-enters worker like any event)
- **Concurrency**: SQS FIFO per-load ordering + DynamoDB conditional update (version)

## Key Files

- `app/api.py` — FastAPI endpoints, bearer token auth
- `app/worker.py` — event processing orchestrator
- `app/dispatcher.py` — deterministic routing (broker, tracking, channel)
- `app/agent.py` — Pydantic AI agent with SOP-driven prompts
- `app/customer.py` — CustomerPolicy model + YAML loader
- `app/tools.py` — mock tool executor with recording
- `app/models.py` — Pydantic models for all API/event schemas
- `app/llm.py` — OpenRouter client with primary/fallback
- `app/db.py` — DynamoDB client (loads, events, tool_calls)
- `app/queue.py` — SQS FIFO client
- `app/timer.py` — EventBridge Scheduler client
- `app/session.py` — per-load session state (rolling window, ping streak)
- `app/observability.py` — structured JSON logger + JSONL writer

## Testing

- `tests/unit/` — fast, isolated, moto for DynamoDB
- `tests/integration/` — worker flow end-to-end in-process
- `tests/eval/` — visible fixture cases with tool call + state assertions

## Environment

- Python 3.13, uv package manager
- LLM: OpenRouter (`OPEN_ROUTER_API_KEY` in `.env`)
- AWS: DynamoDB + SQS + EventBridge + Lambda (LocalStack for local)
- Auth: `API_TOKEN` env var, sent as `Authorization: Bearer <token>`
- Config: `app/config.py` reads all settings from env / `.env` file

## Deployment

- Terraform in `infra/terraform/`
- Single Docker image → ECR → 2 Lambda functions (API + Worker)
- Public endpoint: Lambda Function URL
- Secrets: AWS Secrets Manager in cloud, `.env` locally

## Design Decisions

- Hybrid SOP routing: deterministic gates for exact rules + LLM for ambiguous classification
- Customer config as typed YAML: scales to N customers without code changes
- SQS FIFO MessageGroupId=load_id: guarantees per-load event ordering
- DynamoDB version attribute: optimistic concurrency safety net
- Real multi-model fallback via OpenRouter (Sonnet 4.6 primary, GPT-4o-mini fallback)
- Eval harness has in-process runner (fast, CI) + HTTP runner (live endpoint)
- Free-tier AWS: Lambda + DynamoDB + SQS + EventBridge = ~$0 idle cost
