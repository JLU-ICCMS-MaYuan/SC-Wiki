"""可由 spawn 导入的独立 RQ 消费者。"""
import os
import sys
import time
from redis import Redis
from rq import Worker, SpawnWorker

def consume():
    from .configuration import QUEUE
    from .service import reconcile
    while True:
        connection = Redis.from_url(os.environ["REDIS_URL"], socket_timeout=None, socket_connect_timeout=5)
        try:
            reconcile()
            worker_class = SpawnWorker if sys.platform == "darwin" else Worker
            worker_class([QUEUE], connection=connection).work(with_scheduler=False)
        except Exception:
            # 不输出包含连接信息或凭据的异常字符串。
            import logging
            logging.getLogger(__name__).exception("社区 AI Worker 中断", exc_info=False)
            time.sleep(5)
        finally:
            connection.close()
