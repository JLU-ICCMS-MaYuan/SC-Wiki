"""启动可配置数量的 RQ 上传 Worker，并由第一个进程负责延迟任务调度。"""

from __future__ import annotations

import multiprocessing
import signal
import sys
from typing import NoReturn

from redis import Redis
from rq import Worker as ForkWorker, SpawnWorker

from backend.ingest.upload_tasks import QUEUE_NAME, handle_upload_job_failure
from backend.rag.config import settings
from backend.rq_runtime import run_worker_forever


# macOS 下 fork 后加载 PDF/ML 原生库可使 workhorse 以 signal 6 退出。
Worker = SpawnWorker if sys.platform == 'darwin' else ForkWorker


def _work_horse_killed(job, _pid, exit_code, _usage) -> None:
    """RQ 子进程异常终止不会进入普通 exception_handlers，需单独收敛任务。"""
    if str(getattr(job, 'func_name', '')).endswith('run_evidence_job'):
        from backend.ingest.property_evidence import evidence_job_failed
        evidence_job_failed(job, None)
        return
    error = RuntimeError(f"上传 Worker 子进程异常退出：{exit_code}")
    handle_upload_job_failure(job, RuntimeError, error, None)


def _run_worker(with_scheduler: bool) -> None:
    run_worker_forever(
        lambda: Worker(
            [QUEUE_NAME],
            connection=Redis.from_url(settings.redis_url),
            exception_handlers=[handle_upload_job_failure],
            work_horse_killed_handler=_work_horse_killed,
        ),
        lambda worker: worker.work(with_scheduler=with_scheduler),
        label="upload worker",
    )


def main() -> NoReturn:
    count = max(1, settings.upload_llm_concurrency)
    processes = [
        multiprocessing.Process(target=_run_worker, args=(index == 0,))
        for index in range(count)
    ]
    for process in processes:
        process.start()

    def stop(_signum, _frame) -> None:
        for process in processes:
            if process.is_alive():
                process.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    for process in processes:
        process.join()
    raise SystemExit(max((process.exitcode or 0) for process in processes))


if __name__ == "__main__":
    main()
