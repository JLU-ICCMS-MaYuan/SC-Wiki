"""在独立虚拟环境中启动固定模型的标准 vLLM 嵌入服务。"""

import json
import os
from pathlib import Path
import sys

from download_model import MANIFEST, verify_model


def main():
    if len(os.environ.get("VLLM_API_KEY", "")) < 32:
        raise RuntimeError("必须在私有环境文件配置至少 32 字符的访问密钥")
    root = Path(os.environ.get("EMBEDDING_ROOT", "/home/singeuser/qwen3-embedding"))
    model = root / "model"
    manifest = json.loads(MANIFEST.read_text())
    verify_model(model, manifest)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    os.environ["VLLM_NO_USAGE_STATS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "8"
    command = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", str(model), "--served-model-name", manifest["model"],
        "--runner", "pooling", "--convert", "embed",
        "--dtype", "bfloat16", "--host", "127.0.0.1", "--port", "8000",
        "--max-model-len", "16384", "--max-num-seqs", "2",
        "--max-num-batched-tokens", "16384", "--gpu-memory-utilization", "0.65",
        "--pooler-config", json.dumps({"pooling_type": "LAST", "normalize": True}),
        "--hf-overrides", json.dumps({"is_matryoshka": True,
                                      "matryoshka_dimensions": list(range(32, 2561))}),
        "--enforce-eager", "--disable-log-requests", "--disable-uvicorn-access-log",
    ]
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()
