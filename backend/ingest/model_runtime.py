"""上传解析的可取消请求、持久检查点和公开动态；科学审核仍由原管线负责。"""
from __future__ import annotations

from collections import defaultdict
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import queue
import random
import re
import threading
import time
from uuid import uuid4

import httpx
from openai import APIConnectionError, APITimeoutError, APIStatusError


class ExecutionStopped(BaseException):
    """控制信号：不能被科学提取中的通用Exception兜底吞掉。"""


class ModelRequestError(RuntimeError):
    pass


_execution = ContextVar("upload_model_execution", default=None)


def current_execution():
    return _execution.get()


@contextmanager
def execution_context(runtime):
    token = _execution.set(runtime)
    try:
        yield runtime
    finally:
        _execution.reset(token)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False)
            handle.flush()
            import os
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def read_events(directory, *, before=None, limit=100):
    path = Path(directory) / 'events.jsonl'
    if not path.exists():
        return {'events':[], 'has_more':False}
    rows = deque(maxlen=limit + 1)
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            if line.endswith('\n'):
                row = json.loads(line)
                if before is None or row['updated_at'] < before:
                    rows.append(row)
    return {'events':list(rows)[-limit:], 'has_more':len(rows)>limit}


def redact(value):
    if isinstance(value, dict):
        return {key: ("[已隐藏]" if any(word in key.lower() for word in
            ("api_key", "authorization", "password", "access_token", "secret")) else redact(item))
            for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)Bearer\s+[^\s,;]+", "Bearer [已隐藏]", value)
        value = re.sub(r"(?i)(api[_ -]?key|token|password|secret)\s*[:=]\s*[^\s,;]+", r"\1=[已隐藏]", value)
        return re.sub(r"\bsk-[A-Za-z0-9_-]+", "[已隐藏]", value)
    return value


def error_detail(error, *, output_started=False):
    body = getattr(error, "body", None)
    node = body.get("error", body) if isinstance(body, dict) else {}
    node = node if isinstance(node, dict) else {}
    code = str(node.get("code") or getattr(error, 'code', None) or type(error).__name__)
    fallback = str(error) if type(error).__name__ in {"StructuredOutputError", "ContextBudgetError", "UserCredentialError", "ModelNoOutputError", "ModelProgressTimeout"} else None
    message = redact(str(node.get("message") or fallback or {
        "APIConnectionError": "无法连接模型服务", "APITimeoutError": "等待模型响应超时",
    }.get(type(error).__name__, "模型请求未完成，请查看错误类型")))[:1000]
    request_id = node.get("request_id") or getattr(error, "request_id", None)
    return {"error_type": type(error).__name__, "status_code": getattr(error, "status_code", None),
            "code": redact(code)[:100], "message": message,
            "request_id": redact(str(request_id))[:180] if request_id else None,
            "output_started": bool(output_started)}


def context_overflow(error):
    body = getattr(error, "body", None)
    node = body.get("error", body) if isinstance(body, dict) else {}
    return isinstance(node, dict) and node.get("code") in {
        "context_length_exceeded", "context_window_exceeded", "input_too_long"}


def transient(error):
    from backend.rag.llm_context import UserCredentialError
    from backend.rag.llm import ModelNoOutputError
    if isinstance(error, ModelNoOutputError):
        return True
    if isinstance(error, UserCredentialError):
        return error.code == 'LLM_URL_UNRESOLVABLE'
    body = getattr(error, 'body', None)
    node = body.get('error', body) if isinstance(body, dict) else {}
    if isinstance(node, dict) and node.get('retryable') is False:
        return False
    if isinstance(node, dict) and node.get('code') in {'insufficient_quota', 'billing_hard_limit_reached', 'credit_balance_too_low'}:
        return False
    return (isinstance(error, (APIConnectionError, APITimeoutError, httpx.TransportError)) or
        isinstance(error, APIStatusError) and error.status_code in {408, 429, 500, 502, 503, 504})


def retry_delay(error, attempt):
    response = getattr(error, "response", None)
    header = response.headers.get("retry-after") if response is not None else None
    if header:
        try:
            return max(0, float(header))
        except ValueError:
            try:
                return max(0, (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError):
                pass
    body = getattr(error, "body", None)
    node = body.get("error", body) if isinstance(body, dict) else {}
    delay = node.get("retry_after_seconds") if isinstance(node, dict) else None
    if delay is None and isinstance(body, dict):
        delay = body.get('retry_after_seconds')
    if type(delay) in (int, float) and delay >= 0:
        return float(delay)
    return min(60, 2 ** min(attempt, 6)) + random.uniform(0, 1)


def input_identity(state):
    return digest({"user_id": state.get("user_id"), "files": [
        {key: item.get(key) for key in ("file_id", "role", "sha256")}
        for item in state.get("files", [])], "parser_profile": state.get("parser_profile"),
        "file_sha256": state.get("file_sha256") if not state.get("files") else None, "runtime_version": 1})


class ModelRuntime:
    def __init__(self, task_id, generation, root, read_state, write_state, lock, *, identity):
        self.task_id, self.generation, self.root = task_id, generation, Path(root)
        self.read_state, self.write_state, self.lock = read_state, write_state, lock
        self.identity = identity
        self.occurrences = defaultdict(int)
        self.clients = []
        self.receiving = threading.Event()
        self.last_heartbeat = 0.0

    def check(self):
        state = self.read_state()
        if (not state or state.get("execution_generation") != self.generation or
                state.get("status") in {"pausing", "paused", "cancelling", "cancelled", "submitted"}):
            raise ExecutionStopped("当前执行已停止或被新执行替代")
        return state

    def event(self, status, **fields):
        with self.lock():
            state = self.check()
            previous = state.get("model_activity") or {}
            event = {key: value for key, value in previous.items() if key != "history"}
            event.update(status=status, updated_at=time.time(), **fields)
            self.root.mkdir(parents=True, exist_ok=True)
            with (self.root / 'events.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(redact(event), ensure_ascii=False) + '\n')
                handle.flush()
            history = list(previous.get("history") or [])
            history.append(dict(event))
            self.write_state(model_activity={**event, "history": history[-100:]},
                             execution_heartbeat=time.time())

    def heartbeat(self):
        if time.monotonic() - self.last_heartbeat > 5:
            self.check()
            self.write_state(execution_heartbeat=time.time())
            self.last_heartbeat = time.monotonic()

    def wait(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check()
            self.heartbeat()
            time.sleep(min(.2, max(0, end - time.monotonic())))
        self.check()

    def register_client(self, client):
        self.clients.append(client)

    def close_clients(self):
        clients, self.clients = self.clients, []
        # close可能等待底层socket；不能让停止按钮继续阻塞在close上。
        def close():
            for client in clients:
                try:
                    client.close()
                except Exception:
                    pass
        threading.Thread(target=close, daemon=True).start()

    def interruptible(self, operation):
        result = queue.Queue(maxsize=1)
        context = copy_context()
        stopped = threading.Event()
        late_path = self.root / 'late' / f'g{self.generation}-{uuid4().hex}.json'
        def archive_late(okay, value):
            with self.lock():
                if self.read_state():
                    atomic_json(late_path, {'generation':self.generation, 'operation':operation.__name__,
                        'status':'late_ignored', 'completed_at':time.time(),
                        'result':value if okay else None, 'error':None if okay else error_detail(value)})
        def run():
            try:
                value = (True, context.run(operation))
            except BaseException as exc:
                value = (False, exc)
            result.put(value)
            if stopped.is_set():
                archive_late(*value)
        threading.Thread(target=run, daemon=True).start()
        receiving_announced = False
        try:
            while True:
                self.check()
                self.heartbeat()
                try:
                    okay, value = result.get(timeout=.2)
                except queue.Empty:
                    if self.receiving.is_set() and not receiving_announced:
                        self.receiving.clear()
                        self.event("receiving")
                        receiving_announced = True
                    continue
                self.check()
                if okay:
                    return value
                raise value
        except ExecutionStopped:
            stopped.set()
            try:
                archive_late(*result.get_nowait())
            except queue.Empty:
                pass
            self.close_clients()
            raise

    def call(self, complete, system_prompt, user_prompt, **options):
        from backend.rag.llm import _call_phase, _call_scope
        from .model_memory import prepare_request, ContextBudgetError, validate_context_output
        self.check()
        phase = _call_phase.get() or str(self.read_state().get("reading_state") or "model_request")
        request = {"system_prompt": system_prompt, "user_prompt": user_prompt,
            **{key: value for key, value in options.items() if key not in {"on_partial", "on_call"}}}
        key = digest({"identity": self.identity, "phase": phase, "request": request})
        occurrence = self.occurrences[key]
        self.occurrences[key] += 1
        directory = self.root / "calls" / f"{key}-{occurrence}"
        try:
            payload = json.loads(user_prompt)
            document = payload.get("document") or {}
            filename = document.get("filename")
            pages = [row.get("pdf_page") for row in payload.get("attached_page_images", [])]
        except (ValueError, AttributeError, TypeError):
            filename, pages = None, []
        filename = filename or _call_scope.get().get('filename')
        pages = pages or _call_scope.get().get('pages') or []
        cached = read_json(directory / "result.json")
        if cached is not None:
            self.event("reused", phase=phase, attempt=0, retry_at=None, error=None,
                       filename=filename, pages=pages, action=None, note=None)
            return cached["response"]
        atomic_json(directory / "request.json", {"request": request, "phase": phase,
            "identity": self.identity, "generation": self.generation})
        prepared = dict(request)
        # 未知网关上限采用保守请求预算；不据模型名称推断实际服务上下文。
        budget = 96000
        attempt = max(len(list(directory.glob('attempt-*.json'))), len(list(directory.glob('failure-*.json'))))
        compacted, prepared_once = False, False
        while True:
            self.check()
            attempt += 1
            self.receiving.clear()
            self.event("requesting", phase=phase, attempt=attempt, started_at=time.time(),
                       retry_at=None, error=None, filename=filename, pages=pages, action=None, note=None)
            with self.lock():
                self.check()
                atomic_json(directory / f'attempt-{attempt}-{uuid4().hex}.json',
                            {'generation': self.generation, 'attempt': attempt, 'started_at':time.time()})
            partial = {"text": ""}
            def receive(text):
                partial["text"] = text
                self.receiving.set()
                if options.get("on_partial"):
                    options["on_partial"](text)
            def invoke():
                return complete(prepared["system_prompt"], prepared["user_prompt"],
                    **{key: value for key, value in prepared.items() if key not in {"system_prompt", "user_prompt"}},
                    on_partial=receive, **({"on_call": options["on_call"]} if options.get("on_call") else {}),
                    _single_attempt=True)
            try:
                if not prepared_once and not compacted:
                    prepared = self.interruptible(lambda: prepare_request(request, directory, budget=budget))
                    with self.lock():
                        self.check()
                        atomic_json(directory / 'prepared-request.json', {'request':prepared,
                            'budget':budget, 'token_estimator':'o200k_base+image_allowance',
                            'original_request_hash':digest(request), 'generation':self.generation})
                    prepared_once = True
                    self.event('requesting', phase=phase, attempt=attempt, filename=filename, pages=pages,
                               started_at=time.time(), error=None, retry_at=None)
                response = self.interruptible(invoke)
                validate_context_output(response, prepared)
            except ExecutionStopped:
                raise
            except Exception as exc:
                self.close_clients()
                detail = error_detail(exc, output_started=bool(partial["text"]) or self.receiving.is_set())
                with self.lock():
                    self.check()
                    atomic_json(directory / f"failure-{attempt}-{uuid4().hex}.json", {
                        "error": detail, "body": redact(getattr(exc, "body", None)),
                        "partial_response": partial["text"], "created_at": time.time()})
                if context_overflow(exc) and not compacted:
                    self.event("compacting", phase=phase, error=detail)
                    budget //= 2
                    try:
                        prepared = self.interruptible(lambda: prepare_request(request, directory, budget=budget, force=True))
                    except ContextBudgetError as error:
                        self.event("blocked", error={**detail, "message": str(error)})
                        raise ModelRequestError(str(error)) from exc
                    compacted = True
                    continue
                if transient(exc):
                    delay = retry_delay(exc, attempt)
                    self.event("retry_wait", phase=phase, error=detail, retry_at=time.time() + delay)
                    self.wait(delay)
                    continue
                if isinstance(exc, ContextBudgetError):
                    detail["message"] = str(exc)
                self.event("blocked", phase=phase, error=detail, retry_at=None)
                raise ModelRequestError(detail["message"]) from exc
            with self.lock():
                self.check()
                atomic_json(directory / "result.json", {"response": response, "completed_at": time.time()})
            self.close_clients()
            action = response.get("action") or {} if isinstance(response, dict) else {}
            notes = response.get("uncertainties") or [] if isinstance(response, dict) else []
            self.event("completed", phase=phase, retry_at=None, error=None,
                       action=action.get("name"), note=str(notes[0])[:400] if notes else None)
            return response


def start_runtime(task_id):
    from .upload_tasks import get_state, update_state, upload_task_lock, artifact_directory
    from backend.rag.llm_context import get_llm_config
    with upload_task_lock(task_id):
        state = get_state(task_id)
        if not state or state.get("status") != "queued" or state.get("execution_claimed"):
            raise ExecutionStopped("任务未排队或已由其他执行领取")
        generation = int(state.get("execution_generation") or 0) + 1
        input_hash = input_identity(state)
        config = get_llm_config()
        identity = {"provider": config.provider, "model": config.model, "catalog_id": config.catalog_id,
                    "input_hash": input_hash, "endpoint_hash": digest(config.base_url)}
        update_state(task_id, execution_generation=generation, execution_input_hash=input_hash,
                     execution_model=identity, execution_heartbeat=time.time(), execution_claimed=True,
                     execution_resumable=True)
    return ModelRuntime(task_id, generation, artifact_directory(task_id) / "model-runtime" / input_hash,
        lambda: get_state(task_id), lambda **changes: update_state(task_id, **changes),
        lambda: upload_task_lock(task_id), identity=identity)


def _pause_task_state(task_id):
    from .upload_tasks import get_state, get_draft, update_state, upload_task_lock, redis_client, draft_key
    with upload_task_lock(task_id):
        state = get_state(task_id) or {}
        if state.get("status") in {"pausing", "paused"}:
            return state
        if state.get("status") not in {"queued", "extracting", "reading", "summarizing"} or state.get("paper_id"):
            raise ValueError("当前任务不能停止；已送审论文请使用返修或审核入口")
        queued = state["status"] == "queued" and not state.get("execution_claimed")
        # 暂停保留到主动清理；不能只保住任务状态而让当前草稿24小时后过期。
        redis_client().persist(draft_key(task_id))
        return update_state(task_id, status="paused" if queued else "pausing", processing_status="paused" if queued else "pausing",
            execution_generation=int(state.get("execution_generation") or 0)+1,
            execution_draft_hash=digest(get_draft(task_id)), execution_resumable=True,
            processing_error=None, model_activity={**(state.get("model_activity") or {}),
                "status": "paused" if queued else "pausing", "retry_at": None})


def pause_task(task_id):
    state = _pause_task_state(task_id)
    if state.get("status") == "pausing" and state.get("job_id"):
        # 原生PDF/第三方HTTP可能阻塞在Python检查边界之外；只停止本任务的RQ作业。
        # workhorse失败回调将pausing收敛为paused；等待确认前不能重新领取执行。
        from .upload_tasks import upload_queue
        from rq.job import Job
        from rq.command import send_stop_job_command
        from rq.exceptions import NoSuchJobError, InvalidJobOperation
        try:
            connection = upload_queue().connection
            job = Job.fetch(state["job_id"], connection=connection)
            if job.args and job.args[0] == task_id and job.get_status(refresh=True) == "started":
                send_stop_job_command(connection, job.id)
        except (NoSuchJobError, InvalidJobOperation):
            pass  # 已结束的作业由原执行/失败回调处理，不扩大停止对象。
    return state


def reconcile_execution(task_id, state):
    """以RQ实际终止状态收敛中断；不能用PID或超时本身宣告作业已停。"""
    if state.get('status') != 'pausing' and not (
            state.get('execution_resumable') and state.get('status') in {'extracting','reading','summarizing'}
            and time.time() - float(state.get('execution_heartbeat') or 0) > 60):
        return state
    if not state.get('job_id'):
        return state
    from .upload_tasks import upload_queue, upload_task_lock, get_state, update_state, get_draft
    from rq.job import Job
    from rq.exceptions import NoSuchJobError
    try:
        job = Job.fetch(state['job_id'], connection=upload_queue().connection)
        if job.get_status(refresh=True) not in {'stopped','failed','canceled','finished'}:
            return state
    except NoSuchJobError:
        return state
    with upload_task_lock(task_id):
        latest = get_state(task_id) or {}
        if latest.get('job_id') != state['job_id'] or latest.get('status') in {'ready','submitted','paused','cancelled'}:
            return latest
        return update_state(task_id, status='paused', processing_status='paused',
            execution_generation=int(latest.get('execution_generation') or 0)+1,
            execution_draft_hash=digest(get_draft(task_id)),
            model_activity={**(latest.get('model_activity') or {}), 'status':'paused', 'retry_at':None})


def resume_task(task_id):
    from .upload_tasks import get_state, get_draft, update_state, upload_task_lock, enqueue_processing, redis_client, draft_key
    from backend.rag.llm_context import get_llm_config
    with upload_task_lock(task_id):
        state = get_state(task_id) or {}
        if state.get("status") == "queued" and state.get("execution_resume_requested"):
            return state
        if state.get("paper_id") or state.get("status") not in {"paused", "failed"}:
            raise ValueError("当前任务不能继续")
        if state.get("execution_input_hash") and state["execution_input_hash"] != input_identity(state):
            raise ValueError("输入文件或角色已变化，不能沿用旧解析上下文")
        if state.get("execution_draft_hash") and state["execution_draft_hash"] != digest(get_draft(task_id)):
            raise ValueError("当前草稿已变化，不能用旧上下文覆盖，请保留草稿后处理")
        identity = state.get("execution_model") or {}
        config = get_llm_config()
        if identity and any(identity.get(key) != value for key, value in {
                "provider": config.provider, "model": config.model, "catalog_id": config.catalog_id}.items()):
            raise ValueError("所选模型与原任务不同，请选择原模型后继续")
        if identity.get('endpoint_hash') and identity['endpoint_hash'] != digest(config.base_url):
            raise ValueError('模型服务地址已变化，不能沿用旧请求上下文')
        raw_draft = redis_client().get(draft_key(task_id))
        update_state(task_id, status="queued", resume=True, retry=state.get("status") == "failed",
            execution_claimed=False, execution_resume_requested=True, processing_status="processing",
            reparse_expected_draft_hash=hashlib.sha256(raw_draft.encode()).hexdigest() if raw_draft else None,
            processing_error=None, error_code=None,
            model_activity={**(state.get('model_activity') or {}), 'status':'queued', 'retry_at':None, 'error':None})
        try:
            enqueue_processing(task_id)
        except Exception:
            update_state(task_id, status="paused", processing_status="paused", processing_error="继续任务未能入队，请重试")
            raise
        return get_state(task_id)
