# Watchtower Mini — Architecture Diagrams

## System Architecture

High-level view of all services and how data flows through the system.

![System Architecture](system-architecture.png)

**Flow:**
1. Client sends POST requests (loads, events, tasks) to the ALB
2. API service validates, persists load data, and enqueues to SQS FIFO
3. Worker service polls SQS, processes events through dispatcher/agent
4. State updates written to DynamoDB with optimistic locking
5. EventBridge Scheduler fires timers back into SQS for follow-ups
6. LLM (OpenRouter) handles classification and message drafting via multi-turn tool loop

---

## Event Processing Flow

Internal processing logic when a message is received from SQS.

![Event Processing](event-processing.png)

**Key decision points:**
- **Broker messages**: immediately ignored, no LLM call
- **Tracking pings**: deterministic geofence math, 3 consecutive pings = arrival
- **Communications**: routed to agent for multi-turn tool loop with function calling
- **Tool loop**: LLM calls tools → results fed back → LLM continues until done

---

## Deployment Topology

Infrastructure layout showing all AWS resources and CI/CD pipeline.

![Deployment Topology](deployment-topology.png)

**Resources:**
- **ECS Fargate**: 2 services (API + Worker), 256 CPU / 512 MB each
- **ALB**: public HTTP endpoint on port 80
- **SQS FIFO**: per-load ordering via MessageGroupId
- **DynamoDB**: 3 tables (loads, events, tool_calls), PAY_PER_REQUEST
- **Secrets Manager**: API_TOKEN + OPEN_ROUTER_API_KEY
- **EventBridge Scheduler**: one-off timer schedules
- **ECR**: container image registry
- **CloudWatch**: structured JSON logs
- **GitHub Actions**: CI/CD on push to main
