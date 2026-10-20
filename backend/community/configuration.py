"""服务端模型清单及短期任务凭据，禁止浏览器配置进入后台。"""
from dataclasses import asdict
import hashlib
import json
import os
from redis import Redis
from backend.rag.llm_catalog import get_catalog
from backend.rag.llm_context import LlmConfig, catalog_config, get_server_default_config, llm_display_metadata
from .generation import GenerationError

QUEUE = "scwiki-community-ai"
TIMEOUT = 600
TTL = 86400


def redis_connection():
    return Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=5, socket_timeout=10)


def identity(config):
    return hashlib.sha256((config.base_url.rstrip("/") + "\0" + config.model).encode()).hexdigest()


def models():
    result = []
    seen = set()
    configs = [catalog_config(item.id) for item in get_catalog().items]
    configs.append(get_server_default_config())
    for config in configs:
        if not all((config.api_key, config.base_url, config.model)) or identity(config) in seen:
            continue
        seen.add(identity(config))
        meta = llm_display_metadata(config)
        result.append((config.catalog_id or "server-default", meta.get("provider_name") or config.model, config))
    if not result:
        raise GenerationError("no_models")
    return result


def key(job_id):
    return f"community-ai:credentials:{job_id}"


def save_configs(connection, job_id, configs):
    connection.setex(key(job_id), TTL, json.dumps({i: asdict(c) for i, c in configs.items()}))


def load_config(connection, job_id, model_id, config_hash):
    try:
        payload = json.loads(connection.get(key(job_id)) or "{}")
        config = LlmConfig(**payload[model_id])
    except (KeyError, TypeError, ValueError):
        raise GenerationError("credentials_expired") from None
    if config.user_supplied or identity(config) != config_hash:
        raise GenerationError("model_config_changed")
    return config


def current_configs(tasks):
    available = {i: c for i, _, c in models()}
    result = {}
    for task in tasks:
        config = available.get(task.model_id)
        if config is None or identity(config) != task.config_hash:
            raise GenerationError("model_config_changed")
        result[task.model_id] = config
    return result
