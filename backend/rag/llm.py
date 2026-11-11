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

JSON_OUTPUT_INSTRUCTION = (
    "You must return valid JSON. When calling tools, use the registered tools with JSON arguments."
)


def _json_output_prompt(system_prompt: str) -> str:
    """JSON mode要求消息明确要求JSON；在归档/预算前补齐，传输边界保持幂等。"""
    return (system_prompt if 'json' in system_prompt.casefold()
            else system_prompt + "\n\n" + JSON_OUTPUT_INSTRUCTION)


class ModelNoOutputError(RuntimeError):
    """模型连接尚未给出任何内容就结束，不是科学输出的结构错误。"""
    code = 'LLM_EMPTY_RESPONSE'


class ModelProgressTimeout(httpx.ReadTimeout):
    """已开始响应但后续停滞；保留半截内容，整次请求按传输超时重发。"""
    code = 'LLM_STREAM_IDLE_TIMEOUT'


class ModelIncompleteStreamError(httpx.RemoteProtocolError):
    """流在正常结束标记之前关闭；半截响应不能进入JSON或工具校验。"""
    code = 'LLM_STREAM_INCOMPLETE'


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


def _has_repair_tool(definitions):
    return any(item['function']['name'].startswith('repair_') for item in definitions or [])


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
    _strict_transport: str | None = None,
    _tool_argument_context: dict | None = None,
) -> dict[str, Any]:
    """单次流式调用：逐块累积文本，可选回报中间内容，结束后解析 JSON。"""
    user_content: Any = user_prompt
    if images:
        user_content = [{"type": "text", "text": user_prompt},
                        *({"type": "image_url", "image_url": {"url": url}} for url in images)]
    config = get_llm_config()
    deepseek = config.model.startswith("deepseek")
    _call_stats.set({"thinking": "disabled" if deepseek else "provider_default", "output_started": False})
    messages = [{"role": "system", "content": _json_output_prompt(system_prompt)}, {"role": "user", "content": user_content}]
    if tool_definitions:
        messages[0]['content'] += '\nCall exactly ONE registered function per response. Wait for its result before choosing the next action. Never emit parallel or repeated calls in one response.'
    if tool_history:
        messages.extend(tool_history)
    client = _client(read_timeout)
    from backend.ingest.model_runtime import current_execution
    runtime = current_execution()
    if runtime:
        runtime.check()
        runtime.register_client(client)
    from .responses_json import protocol_for, call as responses_call
    protocol = protocol_for(config)
    _call_stats.set({**_call_stats.get(), 'api_protocol': protocol})
    if protocol == 'responses':
        with token_request() as receive_usage:
            def usage(value):
                receive_usage(value)
                _call_stats.set({**_call_stats.get(),'usage':value})
            result = responses_call(client, config, system_prompt, user_prompt, images=images,
                definitions=tool_definitions, history=tool_history, response_format=response_format,
                on_partial=on_partial,on_usage=usage,
                on_started=lambda: _call_stats.set({**_call_stats.get(),'output_started':True}),
                argument_context=_tool_argument_context)
            _call_stats.set({**_call_stats.get(),'finish_reason':'stop'})
            return result
    wire_definitions = tool_definitions
    source_ids = {}
    if _strict_transport:
        from .deepseek_strict import MODE, official, request_view
        if _strict_transport != MODE or not official(config) or not tool_definitions:
            from .structured_output import StructuredOutputError
            raise StructuredOutputError('严格传输与当前模型接口不匹配')
        client.base_url = 'https://api.deepseek.com/beta'
        actual = request_view({'system_prompt':messages[0]['content'],'user_prompt':user_prompt,
                               'tool_definitions':tool_definitions,'tool_history':tool_history})
        wire_definitions = actual['tool_definitions'];source_ids=actual['source_ids']
        messages[0]['content']=actual['system_prompt']
        if images:messages[1]['content'][0]['text']=actual['user_prompt']
        else:messages[1]['content']=actual['user_prompt']
        _call_stats.set({**_call_stats.get(), 'schema_transport': MODE,
                         'source_reference_codec':'sref-v1' if source_ids else None,
                         'source_reference_count':len(source_ids)})
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
            **({"tools": wire_definitions, "parallel_tool_calls": False} if tool_definitions else {}),
            **({'tool_choice':{'type':'function','function':{'name':'report_structured_output'}}}
               if tool_definitions and len(tool_definitions)==1 and tool_definitions[0]['function']['name']=='report_structured_output'
               else {'tool_choice':'required'} if any(d['function']['name'].startswith(('report_', 'repair_')) for d in tool_definitions or []) else {}),
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
        if runtime and output_seen and finish_reason is None:
            raise ModelIncompleteStreamError('模型流在正常完成标记前结束；已保留未完整响应，原请求将按传输故障处理')
        if runtime and not output_seen and finish_reason in (None, 'stop'):
            raise ModelNoOutputError('模型连接已结束，但未返回任何输出')
        if actions:
            from .structured_output import StructuredOutputError, validate_tool_action
            _call_stats.set({**_call_stats.get(), 'tool_call_count': len(actions),
                'tool_names': [action['name'] for action in actions.values()]})
            if len(actions) != 1 or finish_reason != "tool_calls" or not tool_definitions:
                raise StructuredOutputError("只接受一次完整的已登记工具调用")
            index, action = next(iter(actions.items()))
            raw_arguments = action["arguments"]
            try:
                action["arguments"] = json.loads(action["arguments"])
            except json.JSONDecodeError as exc:
                raise StructuredOutputError("工具参数未形成完整JSON") from exc
            if source_ids:
                from .deepseek_strict import restore_source_ids
                action['arguments']=restore_source_ids(action['arguments'],source_ids)
            action, bindings = validate_tool_action(action, tool_definitions, argument_context=_tool_argument_context)
            result = {"action": action, **({'_panel_bindings': bindings} if bindings else {})}
            if index in call_ids:
                result["_tool_call"] = {"id": call_ids[index], "type": "function",
                    "function": {"name": action["name"], "arguments": raw_arguments}}
            return result
        if _has_repair_tool(tool_definitions):
            from .structured_output import StructuredOutputError
            raise StructuredOutputError('修订阶段必须返回登记的原生工具调用，未采用自由JSON替代工具回执')
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
    _strict_transport: str | None = None,
    _tool_argument_context: dict | None = None,
) -> dict[str, Any]:
    """流式请求并校验JSON；明确未输出的可重试503最多额外两次，其余沿原预算。"""
    from .structured_output import StructuredOutputError, output_format, validate_output
    from urllib.parse import urlparse
    config = get_llm_config()
    schema_tool = (response_schema is not None and not tool_definitions
        and urlparse(getattr(config,'base_url','')).hostname=='api.deepseek.com')
    if schema_tool:
        tool_definitions = [{'type':'function','function':{'name':'report_structured_output',
            'description':'Return the complete requested JSON using exactly this strict schema.',
            'strict':True,'parameters':response_schema}}]
    format_options = {"response_format": output_format(response_schema)} if response_schema is not None else {}
    if schema_tool:format_options['response_format']={'type':'json_object'}
    if _strict_transport:
        format_options['_strict_transport'] = _strict_transport
    if _tool_argument_context:
        format_options['_tool_argument_context'] = _tool_argument_context
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
        if isinstance(exc, (UserCredentialError, ModelNoOutputError, ModelProgressTimeout, ModelIncompleteStreamError)):
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
            if schema_tool:
                if not result.get('_tool_call') or (result.get('action') or {}).get('name')!='report_structured_output':
                    raise StructuredOutputError('当前接口未返回登记的严格结构工具回执，未降级采用自由文本')
                result=result['action']['arguments']
                _call_stats.set({**_call_stats.get(),'schema_transport':_call_stats.get().get('schema_transport','strict_function')})
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
    validate_result = options.pop('validate_result',None)
    system_prompt = _json_output_prompt(system_prompt)
    if _has_repair_tool(options.get('tool_definitions')):
        # 只更新受影响修订请求的检查点；此前成功读取/完整报告保持原身份复用。
        system_prompt += '\nRepair transport native-required-v1: use a registered native tool call; plain JSON content is not a tool receipt.'
    from urllib.parse import urlparse
    config = get_llm_config()
    if (options.get('response_schema') is not None and not options.get('tool_definitions')
            and urlparse(getattr(config,'base_url','')).hostname=='api.deepseek.com'):
        system_prompt += '\nSchema transport strict-function-v1: use the registered report_structured_output function for the complete JSON response.'
    if options.get('images') and get_llm_config().model in {'deepseek-v4-pro'}:
        raise UserCredentialError('所选模型不支持图片输入；请在起始模型选择中使用视觉模型，未自动切换。',
            code='LLM_IMAGE_UNSUPPORTED')
    from .image_inputs import prepare_image_inputs
    system_prompt, options = prepare_image_inputs(system_prompt, options)
    from .deepseek_strict import MODE, MARKER, official
    if official(config) and (options.get('response_schema') is not None or options.get('tool_definitions')):
        from .responses_json import protocol_for
        if protocol_for(config) == 'chat_completions':
            options[MARKER] = MODE
    from backend.ingest.model_runtime import current_execution
    runtime = current_execution()
    if runtime:
        return runtime.call(_complete_json, system_prompt, user_prompt, validate_result=validate_result, **options)
    result = _complete_json(system_prompt, user_prompt, **options)
    if validate_result is not None:validate_result(result)
    return result
