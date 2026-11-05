"""当前字段核对的公开小型进度投影，不读取或发布完整科学快照。"""
import json
from redis.exceptions import WatchError

HISTORY_LIMIT = 12


def public_activity(value):
    if not isinstance(value, dict):
        return None
    result = {key: value[key][:limit] for key, limit in (
        ("stage", 32), ("message", 240), ("tool", 64), ("file_id", 128), ("summary", 400))
        if isinstance(value.get(key), str) and value[key].strip()}
    if not result.get("message"):
        return None
    if isinstance(value.get("page"), int) and not isinstance(value["page"], bool) and value["page"] > 0:
        result["page"] = value["page"]
    return result


def public_history(value):
    if not isinstance(value, list):
        return []
    return [clean for item in value[-HISTORY_LIMIT:] if (clean := public_activity(item))]


def update_activity(job_id, owner, activity):
    from .upload_tasks import redis_client, TASK_TTL
    from .property_evidence import job_control_key
    clean = public_activity(activity)
    if clean is None:
        return
    key = job_control_key(job_id)
    client = redis_client()
    with client.pipeline() as pipe:
        while True:
            try:
                pipe.watch(key)
                raw = pipe.get(key)
                if not raw:
                    return
                control = json.loads(raw)
                if control.get("owner") != owner or control.get("status") not in {"queued", "running"}:
                    return
                history = public_history(control.get("activity_log"))
                if not history or history[-1] != clean:
                    history.append(clean)
                control.update(activity=clean, activity_log=history[-HISTORY_LIMIT:])
                pipe.multi()
                pipe.setex(key, TASK_TTL, json.dumps(control, ensure_ascii=False))
                pipe.execute()
                return
            except WatchError:
                continue
