# Watchtower Mini

AI agent system for freight load event processing. Handles ETA checkpoint and delivery confirmation workflows with customer-specific behavior.

## Deployed Endpoint

**URL**: `http://watchtower-mini-alb-1307411393.us-east-1.elb.amazonaws.com`

**Auth**: All endpoints require `Authorization: Bearer fh-eval-token-2026` header.

## Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Run unit tests
make test

# Run eval harness (mock mode — deterministic cases pass, agent cases xfail)
make eval

# Run eval with live LLM (requires OPEN_ROUTER_API_KEY in .env)
LLM_MODE=live make eval

# Local dev with docker-compose (full AWS parity via LocalStack)
make up
curl -H "Authorization: Bearer dev-token-local" http://localhost:8000/health
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/loads` | Create/seed a load with customer ID and initial data |
| POST | `/submit-task` | Submit a workflow task (delivery_eta_checkpoint or confirm_delivery) |
| POST | `/events/inbound-communication` | Enqueue inbound SMS/email message |
| POST | `/events/tracking` | Enqueue a tracking ping |
| POST | `/events/load-update` | Enqueue a load data or milestone update |
| GET | `/health` | Health check (no auth required) |

## Running Evals

```bash
# In-process with mock LLM (fast, CI-friendly)
make eval

# Against deployed endpoint with live LLM
LLM_MODE=live API_URL=https://your-deployed-url make eval
```

## Deployment

```bash
cd infra/terraform
terraform init
terraform apply -var="open_router_api_key=$OPEN_ROUTER_API_KEY" -var="api_token=$API_TOKEN"
```

See `docs/architecture.md` for full write-up.

## Architecture

```
FastAPI (ECS Fargate + ALB) → SQS FIFO → Worker (ECS Fargate) → DynamoDB
                                              │
                                  ┌───────────┴───────────┐
                                  ▼                       ▼
                           Dispatcher              Agent (LLM)
                           (deterministic)         (classification)
                                  │                       │
                                  └───────────┬───────────┘
                                              ▼
                                      Tool Executor
                                      (mock + record)
```

## Cloud Resources

- **ECS Fargate** × 2 services (API + Worker) — container images from ECR
- **Application Load Balancer (ALB)** — public HTTP endpoint on port 80
- **SQS FIFO** — per-load event ordering
- **DynamoDB** × 3 (loads, events, tool_calls)
- **EventBridge Scheduler** — timer follow-ups
- **ECR** — container image registry
- **Secrets Manager** — API_TOKEN and OPEN_ROUTER_API_KEY
- **CloudWatch** — structured JSON logs

## Secrets Management

- `.env` for local development (gitignored)
- AWS Secrets Manager for deployed secrets (API_TOKEN, OPEN_ROUTER_API_KEY)
- No secrets committed to repository
- Bearer token (`API_TOKEN`) required on all write endpoints
