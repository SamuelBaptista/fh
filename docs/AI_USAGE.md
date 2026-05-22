# AI Usage Disclosure

## Tools Used

- **Claude Code** (Anthropic CLI) — primary development assistant
- **Claude Opus 4.6** — model powering the assistant
- **OpenRouter** — LLM gateway for agent runtime (Claude Sonnet 4.6 + GPT-4o-mini fallback)

## What Was AI-Generated or Heavily Assisted

- Initial project scaffold and boilerplate (pyproject.toml, Makefile, config)
- Pydantic model definitions translated from JSON Schema
- Mock tool implementations (mechanical translation from tool contracts)
- Terraform resource definitions (standard AWS patterns)
- Docker and docker-compose configuration
- Test structure and assertion patterns
- Eval harness framework

## Manual Decisions

- **Architecture**: ECS Fargate + SQS + DynamoDB (better for long-running operations, simpler container deployment)
- **Hybrid SOP routing**: deterministic gates for exact rules + LLM only for ambiguous classification (reduces cost, improves reliability for deterministic cases)
- **Customer policy as typed YAML**: scales by adding files, not prompt edits
- **Model fallback strategy**: real multi-provider via OpenRouter, not mocked
- **Eval design**: in-process runner for fast CI + xfail for agent-dependent tests in mock mode
- **Security posture**: bearer token auth via Secrets Manager, least-privilege IAM per ECS service
- **ALB over API Gateway**: simpler for container-based services, adequate for evaluation traffic

## AI Output Rejected or Corrected

- Rejected initial suggestion to use LangGraph (adds dependency surface without proportional benefit for this scope)
- Corrected model names to match current OpenRouter identifiers
- Moved from Lambda to ECS Fargate after initial deployment (better for long-running operations, simpler container management)
- Adjusted customer policy fields after reviewing customer-expectations.md more carefully
- Removed unnecessary error handling around broker filtering (deterministic path doesn't need try/except)
