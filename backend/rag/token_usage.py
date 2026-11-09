"""实际模型请求的用量边界；不估算、不额外发送请求。"""
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4


_recorder = ContextVar("model_token_usage_recorder", default=None)


@contextmanager
def token_usage_recorder(recorder):
    token = _recorder.set(recorder)
    try:
        yield
    finally:
        _recorder.reset(token)


@contextmanager
def token_request():
    """只在物理请求处调用；结束前最后一份回执为权威用量。"""
    recorder = _recorder.get()
    usage = None
    def receive(value):
        nonlocal usage
        usage = value
    request_id = uuid4().hex
    if recorder:
        recorder("started", request_id, None)
    try:
        yield receive
    finally:
        if recorder:
            recorder("finished", request_id, usage)
