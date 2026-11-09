"""#170：一次隔离真实模型请求，保存用量与任务快照重读证据。"""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/01_decentralized_uploading"))

from pytest import MonkeyPatch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend import database, models
from backend.ingest import upload_tasks, upload_contracts
from backend.ingest.model_runtime import ModelRuntime, execution_context
from backend.ingest.upload_usage import collect_upload_usage
from backend.rag import llm
from backend.rag.llm_context import get_server_default_config, set_llm_config, reset_llm_config
from test_upload_extraction_timing import MemoryRedis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    config = get_server_default_config()
    engine = create_engine("sqlite://")
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    client = MemoryRedis()
    receipts = []
    with MonkeyPatch.context() as patch:
        patch.setattr(database, "SessionLocal", sessions)
        patch.setattr(upload_tasks, "redis_client", lambda: client)
        patch.setattr(upload_tasks, "upload_task_lock", lambda _: nullcontext())
        state = upload_tasks.create_task(7, filename="token用量隔离验证.pdf", file_kind="pdf")
        task_id = state["task_id"]
        with sessions.begin() as db:
            db.add(models.ScientificUploadDraft(task_id=task_id, owner_id=7, state=state, draft={}))
        upload_tasks.update_state(task_id, status="extracting", execution_generation=1)
        runtime = ModelRuntime(task_id, 1, args.output / "runtime", lambda: upload_tasks.get_state(task_id),
            lambda **changes: upload_tasks.update_state(task_id, **changes), lambda: nullcontext(),
            identity={"provider": config.provider, "model": config.model})
        token = set_llm_config(config)
        observer = llm.set_call_observer(receipts.append)
        try:
            with execution_context(runtime), collect_upload_usage(task_id):
                # 验证请求只发一次，不因传输错误无限重试；不是整篇科学解析验收。
                result = llm._complete_json("只返回JSON对象，不要解释。", '返回 {"verified": true}。',
                                            read_timeout=60, _single_attempt=True)
            assert result == {"verified": True}, result
        finally:
            llm.reset_call_observer(observer)
            reset_llm_config(token)
        state = upload_tasks.update_state(task_id, status="ready")
        usage = state["extraction_token_usage"]
        assert usage["request_count"] == usage["recorded_requests"] == 1, usage
        actual = receipts[-1]["usage"]
        assert usage["input_tokens"] == actual["prompt_tokens"]
        assert usage["output_tokens"] == actual["completion_tokens"]
        assert usage["total_tokens"] == actual["total_tokens"]
        client.values.clear()
        restored = upload_tasks.get_state(task_id)
        assert restored["extraction_token_usage"] == usage
        public = upload_contracts.public_task_state(restored)
        evidence = {"verified_at": datetime.now(timezone.utc).isoformat(),
            "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_files_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in ["backend/rag/llm.py", "backend/rag/token_usage.py", "backend/ingest/upload_usage.py",
                             "backend/ingest/upload_contracts.py", "backend/ingest/upload_tasks.py"]},
            "model": config.model, "host": urlparse(config.base_url).hostname,
            "provider_usage": actual, "task_usage": usage, "sqlite_restore_matches": True,
            "scope": "一次合成验证请求；模型服务真实，任务/Redis传输/SQLite隔离；不是整篇PDF或生产部署验收"}
        (args.output / "live-usage.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        (args.output / "live-task.json").write_text(json.dumps(public, ensure_ascii=False, indent=2))
        print(json.dumps({"model": config.model, "actual_usage": actual,
                          "task_usage": usage, "sqlite_restore_matches": True}, ensure_ascii=False))
    engine.dispose()


if __name__ == "__main__":
    main()
