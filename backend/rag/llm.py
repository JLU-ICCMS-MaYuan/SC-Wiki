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
from openai import APIConnectionError, APITimeoutError, OpenAI
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
) -> dict[str, Any]:
    """单次流式调用：逐块累积文本，可选回报中间内容，结束后解析 JSON。"""
    user_content: Any = user_prompt
    if images:
        user_content = [{"type": "text", "text": user_prompt},
                        *({"type": "image_url", "image_url": {"url": url}} for url in images)]
    config = get_llm_config()
    deepseek = config.model.startswith("deepseek")
    _call_stats.set({"thinking": "disabled" if deepseek else "provider_default"})
    stream = _client(read_timeout).chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        extra_body=({"thinking": {"type": "disabled"}} if deepseek else {}),
        **({"max_tokens": 65536, "stream_options": {"include_usage": True}} if deepseek else {}),
        stream=True,
    )
    accumulated: list[str] = []
    finish_reason = None
    for chunk in stream:
        if getattr(chunk, "usage", None):
            _call_stats.set({**_call_stats.get(), "usage": chunk.usage.model_dump()})
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        finish_reason = getattr(chunk.choices[0], "finish_reason", None) or finish_reason
        if not delta:
            continue
        accumulated.append(delta)
        if on_partial is not None:
            on_partial("".join(accumulated))
    _call_stats.set({**_call_stats.get(), "finish_reason": finish_reason})
    if finish_reason not in (None, "stop"):
        raise RuntimeError("模型输出未完整结束")
    return _extract_json("".join(accumulated))


def complete_json(
    system_prompt: str,
    user_prompt: str,
    *,
    images: list[str] | None = None,
    on_partial: Callable[[str], None] | None = None,
    on_call: Callable[[dict], None] | None = None,
    read_timeout: float = 90.0,
    retries: int = 2,
) -> dict[str, Any]:
    """流式请求 LLM 并解析 JSON。连接中断或读超时最多额外重试 retries 次。"""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            result = _stream_json(
                system_prompt, user_prompt,
                images=images, on_partial=on_partial, read_timeout=read_timeout,
            )
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
        # 流式响应中途断开（httpx.TransportError）不经 OpenAI 包装，同样按可重试处理。
        except (APITimeoutError, APIConnectionError, httpx.TransportError, json.JSONDecodeError, RuntimeError) as exc:
            if on_call:
                on_call({**_call_stats.get(), "attempt": attempt + 1, "status": "failed",
                         "error_type": type(exc).__name__, "elapsed_seconds": time.monotonic() - started})
            observer = _call_observer.get()
            if observer:
                observer({**_call_stats.get(), "phase": _call_phase.get(), "model": get_llm_config().model, "prompt_hash": hashlib.sha256(system_prompt.encode()).hexdigest(),
                          "attempt": attempt + 1, "status": "failed", "error_type": type(exc).__name__,
                          "elapsed_seconds": time.monotonic() - started,
                          "input_chars": len(system_prompt) + len(user_prompt), "tokens": None,
                          "input_tokens_estimate": (len(system_prompt) + len(user_prompt) + 3) // 4})
            last_error = exc
            if attempt >= retries:
                break
            print(f"  [LLM] 请求或响应格式异常，{attempt + 1}/{retries} 次重试")
            time.sleep(min(2 ** attempt, 8))
    assert last_error is not None
    raise last_error
