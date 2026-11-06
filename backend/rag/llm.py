"""统一的 OpenAI 兼容 LLM JSON 调用入口。"""

from __future__ import annotations

import json
import time
import hashlib
from contextvars import ContextVar
from contextlib import contextmanager
from collections.abc import Callable
from typing import Any

import httpx
from openai import APIConnectionError, APITimeoutError, APIStatusError, OpenAI
from backend.rag.llm_client import get_llm_client
from backend.rag.llm_context import get_llm_config


_call_observer: ContextVar[Callable[[dict], None] | None] = ContextVar("llm_call_observer", default=None)
_call_phase: ContextVar[str] = ContextVar("llm_call_phase", default="")
_call_stats: ContextVar[dict] = ContextVar("llm_call_stats", default={})


def set_call_observer(observer: Callable[[dict], None]):
    return _call_observer.set(observer)


def reset_call_observer(token) -> None:
    _call_observer.reset(token)


@contextmanager
def call_phase(name: str):
    token = _call_phase.set(name)
    try:
        yield
    finally:
        _call_phase.reset(token)


def _client(read_timeout: float) -> OpenAI:
    return get_llm_client(read_timeout=read_timeout)


def _extract_json(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("LLM 未返回有效 JSON")
        return json.loads(text[start : end + 1])


def _stream_json(
    system_prompt: str,
    user_prompt: str,
    *,
    images: list[str] | None,
    on_partial: Callable[[str], None] | None,
    read_timeout: float,
    response_format: dict | None = None,
    tool_definitions: list[dict] | None = None,
    tool_history: list[dict] | None = None,
) -> dict[str, Any]:
    """单次流式调用：逐块累积文本，可选回报中间内容，结束后解析 JSON。"""
    user_content: Any = user_prompt
    if images:
        user_content = [{"type": "text", "text": user_prompt},
                        *({"type": "image_url", "image_url": {"url": url}} for url in images)]
    config = get_llm_config()
    deepseek = config.model.startswith("deepseek")
    _call_stats.set({"thinking": "disabled" if deepseek else "provider_default"})
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
    if tool_history:
        messages.extend(tool_history)
    stream = _client(read_timeout).chat.completions.create(
        model=config.model,
        messages=messages,
        response_format=response_format or {"type": "json_object"},
        temperature=0.1,
        extra_body=({"thinking": {"type": "disabled"}} if deepseek else {}),
        **({"max_tokens": 65536, "stream_options": {"include_usage": True}} if deepseek else {}),
        stream=True,
        **({"tools": tool_definitions, "parallel_tool_calls": False} if tool_definitions else {}),
    )
    accumulated: list[str] = []
    actions: dict[int, dict] = {}
    call_ids: dict[int, str] = {}
    finish_reason = None
    last_progress = time.monotonic()
    try:
        for chunk in stream:
            now = time.monotonic()
            made_progress = False
            if getattr(chunk, "usage", None):
                _call_stats.set({**_call_stats.get(), "usage": chunk.usage.model_dump()})
            if not chunk.choices:
                if now - last_progress >= read_timeout:
                    raise RuntimeError("模型持续返回空白或空响应，超过现有读取超时")
                continue
            delta_object = chunk.choices[0].delta
            delta = delta_object.content
            made_progress = bool(delta and delta.strip())
            finish_reason = getattr(chunk.choices[0], "finish_reason", None) or finish_reason
            for call in getattr(delta_object, "tool_calls", None) or []:
                if getattr(call, "id", None):
                    call_ids[call.index] = call.id
                action = actions.setdefault(call.index, {"name": "", "arguments": ""})
                if call.function is not None:
                    action["name"] += call.function.name or ""
                    action["arguments"] += call.function.arguments or ""
                    made_progress = made_progress or bool((call.function.name or "").strip()
                        or (call.function.arguments or "").strip())
                if on_partial:
                    on_partial(json.dumps({"tool_calls": list(actions.values())}, ensure_ascii=False))
            if delta:
                accumulated.append(delta)
                if on_partial is not None:
                    on_partial("".join(accumulated))
            if made_progress:
                last_progress = now
            elif now - last_progress >= read_timeout:
                raise RuntimeError("模型持续返回空白或空响应，超过现有读取超时")
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()
    _call_stats.set({**_call_stats.get(), "finish_reason": finish_reason})
    if actions:
        from .structured_output import StructuredOutputError, validate_tool_action
        if len(actions) != 1 or finish_reason != "tool_calls" or not tool_definitions:
            raise StructuredOutputError("只接受一次完整的已登记工具调用")
        index, action = next(iter(actions.items()))
        raw_arguments = action["arguments"]
        try:
            action["arguments"] = json.loads(action["arguments"])
        except json.JSONDecodeError as exc:
            raise StructuredOutputError("工具参数未形成完整JSON") from exc
        validate_tool_action(action, tool_definitions)
        result = {"action": action}
        if index in call_ids:
            result["_tool_call"] = {"id": call_ids[index], "type": "function",
                "function": {"name": action["name"], "arguments": raw_arguments}}
        return result
    if finish_reason not in (None, "stop"):
        raise RuntimeError("模型输出未完整结束")
    result = _extract_json("".join(accumulated))
    if tool_definitions and isinstance(result, dict) and "_tool_call" in result:
        from .structured_output import StructuredOutputError
        raise StructuredOutputError("模型文本不能伪造工具调用回执")
    if tool_definitions and isinstance(result, dict) and "action" in result:
        from .structured_output import validate_tool_action
        validate_tool_action(result["action"], tool_definitions)
    return result


def complete_json(
    system_prompt: str,
    user_prompt: str,
    *,
    images: list[str] | None = None,
    on_partial: Callable[[str], None] | None = None,
    on_call: Callable[[dict], None] | None = None,
    read_timeout: float = 90.0,
    retries: int = 2,
    response_schema: dict | None = None,
    tool_definitions: list[dict] | None = None,
    tool_history: list[dict] | None = None,
) -> dict[str, Any]:
    """流式请求 LLM 并解析 JSON。连接中断或读超时最多额外重试 retries 次。"""
    from .structured_output import StructuredOutputError, output_format, validate_output
    format_options = {"response_format": output_format(response_schema)} if response_schema is not None else {}
    if tool_definitions:
        for definition in tool_definitions:
            if definition.get("type") != "function" or definition["function"].get("strict") is not True:
                raise StructuredOutputError("只接受严格定义的工具")
            output_format(definition["function"]["parameters"])
        format_options["tool_definitions"] = tool_definitions
    if tool_history:
        format_options["tool_history"] = tool_history
    def record_failure(exc, attempt, started):
        # 只记录类型和HTTP状态；异常文本/响应正文可能包含凭据，不进入回执。
        event = {**_call_stats.get(), "attempt": attempt + 1, "status": "failed",
                 "error_type": type(exc).__name__, "elapsed_seconds": time.monotonic() - started}
        if isinstance(exc, APIStatusError):
            event["status_code"] = exc.status_code
        if on_call:
            on_call(dict(event))
        observer = _call_observer.get()
        if observer:
            observer({**event, "phase": _call_phase.get(), "model": get_llm_config().model,
                      "prompt_hash": hashlib.sha256(system_prompt.encode()).hexdigest(),
                      "input_chars": len(system_prompt) + len(user_prompt), "tokens": None,
                      "input_tokens_estimate": (len(system_prompt) + len(user_prompt) + 3) // 4})
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            result = _stream_json(
                system_prompt, user_prompt,
                images=images, on_partial=on_partial, read_timeout=read_timeout,
                **format_options,
            )
            if response_schema is not None:
                validate_output(result, response_schema)
            if on_call:
                on_call({**_call_stats.get(), "attempt": attempt + 1, "status": "completed",
                         "elapsed_seconds": time.monotonic() - started})
            observer = _call_observer.get()
            if observer:
                output_chars = len(json.dumps(result, ensure_ascii=False))
                observer({**_call_stats.get(), "phase": _call_phase.get(), "model": get_llm_config().model, "prompt_hash": hashlib.sha256(system_prompt.encode()).hexdigest(),
                          "attempt": attempt + 1, "status": "completed", "elapsed_seconds": time.monotonic() - started,
                          "input_chars": len(system_prompt) + len(user_prompt),
                          "output_chars": output_chars, "tokens": None,
                          "input_tokens_estimate": (len(system_prompt) + len(user_prompt) + 3) // 4,
                          "output_tokens_estimate": (output_chars + 3) // 4})
            return result
        except StructuredOutputError as exc:
            record_failure(exc, attempt, started)
            raise
        except APIStatusError as exc:
            record_failure(exc, attempt, started)
            if (response_schema is not None or tool_definitions) and exc.status_code in (400, 422):
                raise StructuredOutputError("当前模型接口拒绝严格输出结构；未降级或自动重试") from exc
            raise
        # 流式响应中途断开（httpx.TransportError）不经 OpenAI 包装，同样按可重试处理。
        except (APITimeoutError, APIConnectionError, httpx.TransportError, json.JSONDecodeError, RuntimeError) as exc:
            record_failure(exc, attempt, started)
            last_error = exc
            if (response_schema is not None or tool_definitions) and isinstance(exc, (json.JSONDecodeError, RuntimeError)):
                raise StructuredOutputError("严格输出未返回完整有效JSON；原响应保留，未自动纠错") from exc
            if attempt >= retries:
                break
            print(f"  [LLM] 请求或响应格式异常，{attempt + 1}/{retries} 次重试")
            time.sleep(min(2 ** attempt, 8))
    assert last_error is not None
    raise last_error
