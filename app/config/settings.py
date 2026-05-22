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
