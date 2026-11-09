"""上传解析轮次内的实际token聚合与任务收集上下文。"""
from contextlib import contextmanager
from uuid import uuid4

from backend.rag.token_usage import token_usage_recorder


def new_extraction_token_usage():
    return {"run_id": uuid4().hex, "input_tokens": 0, "output_tokens": 0,
            "total_tokens": 0, "request_count": 0, "recorded_requests": 0}


def normalized_usage(receipt):
    if not isinstance(receipt, dict):
        return None
    incoming = receipt.get("prompt_tokens", receipt.get("input_tokens"))
    outgoing = receipt.get("completion_tokens", receipt.get("output_tokens"))
    if any(type(value) is not int or value < 0 for value in (incoming, outgoing)):
        return None
    total = receipt.get("total_tokens", incoming + outgoing)
    if type(total) is not int or total != incoming + outgoing:
        return None
    return {"input_tokens": incoming, "output_tokens": outgoing, "total_tokens": total}


def apply_token_usage_event(state, event):
    current = state.get("extraction_token_usage")
    if not isinstance(current, dict) or not isinstance(event, dict) or event.get("run_id") != current.get("run_id"):
        return
    request_id = event.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return
    requests = dict(state.get("_extraction_token_requests") or {})
    usage = dict(current)
    if event.get("kind") == "started" and request_id not in requests:
        requests[request_id] = "pending"
        usage["request_count"] += 1
    elif event.get("kind") == "finished" and requests.get(request_id) == "pending":
        receipt = normalized_usage(event.get("usage"))
        requests[request_id] = "recorded" if receipt is not None else "missing"
        if receipt is not None:
            for key, value in receipt.items():
                usage[key] += value
            usage["recorded_requests"] += 1
    else:
        return
    state["extraction_token_usage"] = usage
    state["_extraction_token_requests"] = requests


@contextmanager
def collect_upload_usage(task_id):
    from .upload_tasks import get_state, update_state
    from .model_runtime import ExecutionStopped
    usage = (get_state(task_id) or {}).get("extraction_token_usage")
    run_id = usage.get("run_id") if isinstance(usage, dict) else None
    def record(kind, request_id, receipt):
        if not run_id:
            return  # 历史任务不伪造完整统计；明确重试才初始化新轮次。
        try:
            update_state(task_id, _token_usage_event={"run_id": run_id,
                "request_id": request_id, "kind": kind, "usage": receipt})
        except ExecutionStopped:
            if kind == "started":
                raise
            # 已停止的旧执行不能写入迟到回执；原请求保留为用量未知。
    with token_usage_recorder(record):
        yield
