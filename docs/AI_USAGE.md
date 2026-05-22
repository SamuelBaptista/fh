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

- **Architecture**: Lambda + SQS + DynamoDB over ECS/RDS (cost optimization for throwaway eval traffic)
- **Hybrid SOP routing**: deterministic gates for exact rules + LLM only for ambiguous classification (reduces cost, improves reliability for deterministic cases)
- **Customer policy as typed YAML**: scales by adding files, not prompt edits
- **Model fallback strategy**: real multi-provider via OpenRouter, not mocked
- **Eval design**: in-process runner for fast CI + xfail for agent-dependent tests in mock mode
- **Security posture**: bearer token auth, least-privilege IAM per Lambda function
- **Free-tier targeting**: Lambda Function URL instead of API Gateway to minimize cost

## AI Output Rejected or Corrected

- Rejected initial suggestion to use LangGraph (adds dependency surface without proportional benefit for this scope)
- Corrected model names to match current OpenRouter identifiers
- Rejected API Gateway in favor of Lambda Function URL (simpler, cheaper)
- Adjusted customer policy fields after reviewing customer-expectations.md more carefully
- Removed unnecessary error handling around broker filtering (deterministic path doesn't need try/except)
