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
