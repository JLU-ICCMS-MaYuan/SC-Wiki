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
from backend.rag.token_usage import token_request
from backend.rag.llm_client import get_llm_client
from backend.rag.llm_context import get_llm_config, UserCredentialError


_call_observer: ContextVar[Callable[[dict], None] | None] = ContextVar("llm_call_observer", default=None)
_call_phase: ContextVar[str] = ContextVar("llm_call_phase", default="")
_call_scope: ContextVar[dict] = ContextVar("llm_call_scope", default={})
_call_stats: ContextVar[dict] = ContextVar("llm_call_stats", default={})


class ModelNoOutputError(RuntimeError):
    """模型连接尚未给出任何内容就结束，不是科学输出的结构错误。"""
    code = 'LLM_EMPTY_RESPONSE'


class ModelProgressTimeout(httpx.ReadTimeout):
    """已开始响应但后续停滞；保留半截内容，整次请求按传输超时重发。"""
    code = 'LLM_STREAM_IDLE_TIMEOUT'


def set_call_observer(observer: Callable[[dict], None]):
    return _call_observer.set(observer)


def reset_call_observer(token) -> None:
    _call_observer.reset(token)


@contextmanager
def call_phase(name: str, **scope):
    token = _call_phase.set(name)
    scope_token = _call_scope.set(scope)
    try:
        yield
    finally:
        _call_phase.reset(token)
        _call_scope.reset(scope_token)


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
    _call_stats.set({"thinking": "disabled" if deepseek else "provider_default", "output_started": False})
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
    if tool_history:
        messages.extend(tool_history)
    client = _client(read_timeout)
    from backend.ingest.model_runtime import current_execution
    runtime = current_execution()
    if runtime:
        runtime.check()
        runtime.register_client(client)
    with token_request() as receive_usage:
        stream = client.chat.completions.create(
            model=config.model,
            messages=messages,
            response_format=response_format or {"type": "json_object"},
            temperature=0.1,
            extra_body=({"thinking": {"type": "disabled"}} if deepseek else {}),
            **({"max_tokens": 65536} if deepseek else {}),
            stream_options={"include_usage": True},
            stream=True,
            **({"tools": tool_definitions, "parallel_tool_calls": False} if tool_definitions else {}),
        )
        accumulated: list[str] = []
        actions: dict[int, dict] = {}
        call_ids: dict[int, str] = {}
        finish_reason = None
        output_seen = False
        last_progress = time.monotonic()
        try:
            for chunk in stream:
                now = time.monotonic()
                made_progress = False
                if getattr(chunk, "usage", None):
                    receive_usage(chunk.usage.model_dump())
                    _call_stats.set({**_call_stats.get(), "usage": chunk.usage.model_dump()})
                if not chunk.choices:
                    if now - last_progress >= read_timeout:
                        if runtime and not output_seen:
                            raise ModelNoOutputError('模型未返回任何输出，等待响应超时')
                        if runtime:
                            raise ModelProgressTimeout('模型输出停滞，超过读取等待时间；未完整响应不进入表单')
                        raise RuntimeError("模型持续返回空白或空响应，超过现有读取超时")
                    continue
                delta_object = chunk.choices[0].delta
                delta = delta_object.content
                if not output_seen and (delta or getattr(delta_object, "tool_calls", None)):
                    output_seen = True
                    _call_stats.set({**_call_stats.get(), "output_started": True})
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
                if made_progress and runtime:
                    runtime.receiving.set()
                    runtime.check()
                if made_progress:
                    last_progress = now
                elif now - last_progress >= read_timeout:
                    if runtime and not output_seen:
                        raise ModelNoOutputError('模型未返回任何输出，等待响应超时')
                    if runtime:
                        raise ModelProgressTimeout('模型输出停滞，超过读取等待时间；未完整响应不进入表单')
                    raise RuntimeError("模型持续返回空白或空响应，超过现有读取超时")
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        _call_stats.set({**_call_stats.get(), "finish_reason": finish_reason})
        if runtime and not output_seen and finish_reason in (None, 'stop'):
            raise ModelNoOutputError('模型连接已结束，但未返回任何输出')
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


def _retryable_unstarted_service_error(error):
    """只读取明确的无输出/可重试标记；缺失或互相矛盾均不重试。"""
    if error.status_code != 503 or _call_stats.get().get('output_started') is not False:
        return False
    bodies = [error.body]
    try:
        bodies.append(error.response.json())
    except (ValueError, httpx.ResponseNotRead):
        pass
    nodes = []
    for body in bodies:
        if isinstance(body, dict):
            nodes.append(body)
            if isinstance(body.get('error'), dict):
                nodes.append(body['error'])
    started = [node['output_started'] for node in nodes if 'output_started' in node]
    retryable = [node['retryable'] for node in nodes if 'retryable' in node]
    return bool(started and retryable and all(value is False for value in started)
                and all(value is True for value in retryable))


def _complete_json(
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
    _single_attempt: bool = False,
) -> dict[str, Any]:
    """流式请求并校验JSON；明确未输出的可重试503最多额外两次，其余沿原预算。"""
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
        if isinstance(exc, (UserCredentialError, ModelNoOutputError, ModelProgressTimeout)):
            event['error_code'] = exc.code
        if on_call:
            on_call(dict(event))
        observer = _call_observer.get()
        if observer:
            observer({**event, "phase": _call_phase.get(), "model": get_llm_config().model,
                      "prompt_hash": hashlib.sha256(system_prompt.encode()).hexdigest(),
                      "input_chars": len(system_prompt) + len(user_prompt), "tokens": None,
                      "input_tokens_estimate": (len(system_prompt) + len(user_prompt) + 3) // 4})
    last_error: Exception | None = None
    for attempt in range(1 if _single_attempt else max(retries, 2) + 1):
        started = time.monotonic()
        _call_stats.set({"output_started": False})
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
            service_retryable = _retryable_unstarted_service_error(exc)
            _call_stats.set({**_call_stats.get(), "unstarted_service_retryable": service_retryable,
                             "retry_scheduled": not _single_attempt and attempt < 2 and service_retryable})
            record_failure(exc, attempt, started)
            if _single_attempt:
                raise  # 运行器需要原始错误码识别上下文超限；不能提前包装成结构错误。
            if not _single_attempt and attempt < 2 and service_retryable:
                print(f"  [LLM] 上游503明确未输出，{attempt + 1}/2 次传输重试")
                time.sleep(min(2 ** attempt, 8))
                continue
            if (response_schema is not None or tool_definitions) and exc.status_code in (400, 422):
                raise StructuredOutputError("当前模型接口拒绝严格输出结构；未降级或自动重试") from exc
            raise
        # 流式响应中途断开（httpx.TransportError）不经 OpenAI 包装，同样按可重试处理。
        except (APITimeoutError, APIConnectionError, httpx.TransportError, json.JSONDecodeError, RuntimeError) as exc:
            record_failure(exc, attempt, started)
            last_error = exc
            if _single_attempt and isinstance(exc, (UserCredentialError, ModelNoOutputError)):
                raise  # DNS/网址错误发生在请求前，不能冒充模型返回了非法JSON。
            if (response_schema is not None or tool_definitions) and isinstance(exc, (json.JSONDecodeError, RuntimeError)):
                raise StructuredOutputError("严格输出未返回完整有效JSON；原响应保留，未自动纠错") from exc
            if _single_attempt or attempt >= retries:
                break
            print(f"  [LLM] 请求或响应格式异常，{attempt + 1}/{retries} 次重试")
            time.sleep(min(2 ** attempt, 8))
    assert last_error is not None
    raise last_error


def complete_json(system_prompt: str, user_prompt: str, **options) -> dict[str, Any]:
    """上传执行使用持久运行器；其他宿主保留原有调用契约。"""
    from backend.ingest.model_runtime import current_execution
    runtime = current_execution()
    if runtime:
        return runtime.call(_complete_json, system_prompt, user_prompt, **options)
    return _complete_json(system_prompt, user_prompt, **options)
