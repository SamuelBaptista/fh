from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config.settings import settings
from app.observability import Logger


OPENROUTER_BASE = "https://openrouter.ai/api/v1"


@dataclass
class LLMResponse:
    content: str
    model: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
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

    async def complete_with_tool_loop(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        tool_executor: Any,
        load_id: str = "",
        event_id: str = "",
        max_iterations: int = 5,
    ) -> LLMResponse:
        """Multi-turn tool loop: call LLM, execute tools, feed results back, repeat."""
        log = Logger(load_id=load_id, event_id=event_id)

        if self._mode == "mock":
            return self._mock_response()

        model = self._primary
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        all_tool_calls: list[dict[str, Any]] = []
        total_input_tokens = 0
        total_output_tokens = 0
        start = time.time()

        for iteration in range(max_iterations):
            try:
                data = await self._raw_call(model, messages, tools)
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                if model == self._primary:
                    log.warn("llm.primary_failed", model=model, error=str(e))
                    model = self._fallback
                    try:
                        data = await self._raw_call(model, messages, tools)
                    except Exception as e2:
                        log.error("llm.fallback_failed", model=model, error=str(e2))
                        raise
                else:
                    raise

            usage = data.get("usage", {})
            total_input_tokens += usage.get("prompt_tokens", 0)
            total_output_tokens += usage.get("completion_tokens", 0)

            choice = data["choices"][0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "")

            # Append assistant message to conversation
            messages.append(message)

            raw_tool_calls = message.get("tool_calls", [])

            if not raw_tool_calls or finish_reason == "stop":
                # No more tool calls — done
                break

            # Execute each tool call and append results
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}

                all_tool_calls.append({"tool": tool_name, "arguments": args})

                # Execute the tool
                result = tool_executor(tool_name, args)

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(result, default=str),
                })

        duration_ms = int((time.time() - start) * 1000)
        content = messages[-1].get("content", "") if messages[-1].get("role") == "assistant" else ""

        log.info("llm.tool_loop_complete", model=model, iterations=iteration + 1, tool_calls=len(all_tool_calls), tokens_in=total_input_tokens, tokens_out=total_output_tokens, duration_ms=duration_ms)

        return LLMResponse(
            content=content or "",
            model=model,
            tool_calls=all_tool_calls,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            duration_ms=duration_ms,
            was_fallback=(model == self._fallback),
        )

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
        data = await self._raw_call(model, messages, tools)

        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        usage = data.get("usage", {})

        raw_tool_calls = message.get("tool_calls", [])
        parsed_tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {}
            parsed_tool_calls.append({"tool": fn.get("name", ""), "arguments": args})

        return LLMResponse(
            content=content,
            model=model,
            tool_calls=parsed_tool_calls,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )

    async def _raw_call(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OPENROUTER_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _mock_response() -> LLMResponse:
        return LLMResponse(
            content='{"intent": "acknowledge", "branch": "no_action", "reasoning": "Mock response", "tool_calls": []}',
            model="mock",
            tool_calls=[],
            input_tokens=0,
            output_tokens=0,
            duration_ms=0,
        )
