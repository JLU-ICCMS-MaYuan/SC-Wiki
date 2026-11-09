"""上传任务共用的模型请求额度；跨RQ进程，停止后释放本次持有的租约。"""
from contextlib import contextmanager
import threading
from redis.exceptions import LockError


@contextmanager
def upload_request_slot(runtime):
    from .upload_tasks import redis_client
    from backend.rag.config import settings
    client = redis_client()
    limit = max(1, int(settings.upload_llm_concurrency))
    held = None
    while held is None:
        runtime.check()
        for index in range(limit):
            lock = client.lock(f'upload:model-request-slot:{index}', timeout=120, thread_local=False)
            if lock.acquire(blocking=False):
                held = lock
                break
        if held is None:
            runtime.wait(.2)
    done = threading.Event()
    failed = threading.Event()
    def renew():
        while not done.wait(20):
            try:
                runtime.check()
                held.extend(120, replace_ttl=True)
            except BaseException:
                failed.set()
                runtime.close_clients()
                return
    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        runtime.check()
        yield
        if failed.is_set():
            raise RuntimeError('模型请求额度租约失效，响应未作为成功结果保存')
    finally:
        done.set()
        thread.join(timeout=1)
        try:
            held.release()
        except LockError:
            pass
