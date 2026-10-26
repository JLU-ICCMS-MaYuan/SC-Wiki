"""隔离旧模型依赖；主服务无需导入 Torch／e3nn。"""
import asyncio
import json
import logging
import os
from pathlib import Path
import signal

from .inference import CACHE, ROOT

logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 120
_lock = asyncio.Lock()


class PredictionError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def runtime_python():
    return Path(os.environ.get("TC_MODEL_PYTHON", CACHE / "venv/bin/python"))


async def _terminate(process):
    if process.returncode is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    await process.wait()


async def run_structure(request):
    if _lock.locked():
        raise PredictionError(429, "结构模型正在运行，请稍后重试")
    executable = runtime_python()
    if not executable.is_file():
        raise PredictionError(503, "结构模型环境未就绪，请准备本地模型运行环境")
    async with _lock:
        try:
            process = await asyncio.create_subprocess_exec(
                str(executable), "-m", "backend.prediction.worker",
                cwd=str(ROOT), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, start_new_session=True,
                env={**os.environ, "PYTHONNOUSERSITE": "1", "TC_MODEL_CACHE": str(CACHE)},
            )
        except OSError as exc:
            raise PredictionError(503, "无法启动结构模型运行环境") from exc
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(json.dumps(request, allow_nan=False).encode()), timeout=TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            await _terminate(process)
            raise PredictionError(504, "结构模型计算超时，请减少结构规模后重试") from exc
        except BaseException:
            await _terminate(process)
            raise
        if process.returncode:
            logger.error("结构模型进程退出 %s：%s", process.returncode, stderr.decode(errors="replace")[-4000:])
            raise PredictionError(503, "结构模型运行失败，请检查服务日志")
        try:
            response = json.loads(stdout)
        except (ValueError, TypeError) as exc:
            logger.error("结构模型输出无效：%s", stderr.decode(errors="replace")[-4000:])
            raise PredictionError(503, "结构模型没有返回有效结果") from exc
        if "error" in response:
            raise PredictionError(response.get("status", 503), response["error"])
        return response["result"]
