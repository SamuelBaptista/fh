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
FastAPI (ECS Fargate + ALB) → SQS FIFO (MessageGroupId=load_id) → Worker (ECS Fargate)
                                                                       │
                                                           Dispatcher (deterministic)
                                                           + Agent (Pydantic AI / OpenRouter)
                                                                       │
                                                           DynamoDB (loads/events/tool_calls)
```

- **Dispatcher**: handles broker filter, tracking geofence math, channel routing — no LLM needed
- **Agent**: handles intent classification, message drafting, ambiguous cases — uses LLM
- **Customer policy**: typed YAML in `app/config/customers/` — add customer = add file
- **Timers**: EventBridge Scheduler → SQS (re-enters worker like any event)
- **Concurrency**: SQS FIFO per-load ordering + DynamoDB conditional update (version)

## Key Files

- `app/api/routes.py` — FastAPI endpoints, bearer token auth
- `app/api/deps.py` — dependency injection for auth
- `app/worker/handler.py` — event processing orchestrator
- `app/worker/sqs_poller.py` — SQS long polling for worker
- `app/agent/agent.py` — Pydantic AI agent with SOP-driven prompts
- `app/agent/dispatcher.py` — deterministic routing (broker, tracking, channel)
- `app/agent/tools_schema.py` — tool definitions and schemas
- `app/config/customer.py` — CustomerPolicy model + YAML loader
- `app/config/settings.py` — settings and configuration
- `app/config/customers/` — per-customer YAML policy files
- `app/core/tools.py` — mock tool executor with recording
- `app/core/models.py` — Pydantic models for all API/event schemas
- `app/core/session.py` — per-load session state (rolling window, ping streak)
- `app/infra/llm.py` — OpenRouter client with primary/fallback
- `app/infra/db.py` — DynamoDB client (loads, events, tool_calls)
- `app/infra/queue.py` — SQS FIFO client
- `app/infra/timer.py` — EventBridge Scheduler client
- `app/observability.py` — structured JSON logger + JSONL writer

## Testing

- `tests/unit/` — fast, isolated, moto for DynamoDB
- `tests/integration/` — worker flow end-to-end in-process
- `tests/eval/` — visible fixture cases with tool call + state assertions

## Environment

- Python 3.13, uv package manager
- LLM: OpenRouter (`OPEN_ROUTER_API_KEY` in `.env`)
- AWS: DynamoDB + SQS + EventBridge + ECS Fargate + ALB (LocalStack for local)
- Auth: `API_TOKEN` env var, sent as `Authorization: Bearer <token>`
- Secrets: AWS Secrets Manager in cloud, `.env` locally
- Config: `app/config/settings.py` reads all settings from env / `.env` file

## Deployment

- Terraform in `infra/terraform/`
- Single Docker image → ECR → 2 ECS Fargate services (API + Worker)
- Public endpoint: Application Load Balancer (ALB)
- Deployed URL: `http://watchtower-mini-alb-1307411393.us-east-1.elb.amazonaws.com`
- Auth token: `fh-eval-token-2026`
- Secrets: AWS Secrets Manager in cloud, `.env` locally

## Design Decisions

- Hybrid SOP routing: deterministic gates for exact rules + LLM for ambiguous classification
- Customer config as typed YAML: scales to N customers without code changes
- SQS FIFO MessageGroupId=load_id: guarantees per-load event ordering
- DynamoDB version attribute: optimistic concurrency safety net
- Real multi-model fallback via OpenRouter (Anthropic primary, OpenAI fallback)
- Eval harness has in-process runner (fast, CI) + HTTP runner (live endpoint)
- ECS Fargate over Lambda: better for long-running operations, simpler container deployment
