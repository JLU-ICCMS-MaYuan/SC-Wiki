"""通过真实 HTTP 请求验收嵌入服务，不输出凭据或完整向量。"""

import argparse
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request


MODEL = "Qwen/Qwen3-Embedding-4B"
TEXTS = [
    "Instruct: Given a research paper query, retrieve relevant scientific passages that answer the query\n"
    "Query: 高压下富氢材料为什么可能具有较高的超导临界温度？",
    "Hydrogen-rich materials under high pressure can exhibit high superconducting transition "
    "temperatures due to strong electron-phonon coupling and high phonon frequencies.",
    "This recipe describes baking a chocolate cake with butter, flour, sugar and eggs.",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--max-model-len", type=int, default=16384)
    args = parser.parse_args()
    key = args.key_file.read_text().strip() if args.key_file else os.environ["VLLM_API_KEY"]
    checks = []

    def request(method, route, payload=None, token=key):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(args.base_url.rstrip("/") + route, method=method,
                                     data=json.dumps(payload).encode() if payload is not None else None,
                                     headers=headers)
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=args.timeout) as response:
                return response.status, json.load(response), time.perf_counter() - start
        except urllib.error.HTTPError as exc:
            return exc.code, {}, time.perf_counter() - start

    def embed(texts, dimensions=None):
        payload = {"model": MODEL, "input": texts, "encoding_format": "float"}
        if dimensions is not None:
            payload["dimensions"] = dimensions
        status, response, elapsed = request("POST", "/v1/embeddings", payload)
        assert status == 200, f"嵌入请求失败: HTTP {status}"
        count = 1 if isinstance(texts, str) else len(texts)
        data = response["data"]
        assert response["model"] == MODEL
        assert len(data) == count and [row["index"] for row in data] == list(range(count))
        for row in data:
            vector = row["embedding"]
            assert len(vector) == (dimensions or 2560)
            assert all(isinstance(v, (float, int)) and math.isfinite(v) for v in vector)
            assert abs(math.sqrt(sum(v * v for v in vector)) - 1) < 0.01
        checks.append({"name": "embedding", "count": count, "dimensions": dimensions or 2560,
                       "elapsed_seconds": round(elapsed, 4)})
        return [row["embedding"] for row in data]

    for token in [None, "incorrect-key"]:
        for method, route, payload in [
            ("GET", "/v1/models", None),
            ("POST", "/v1/embeddings", {"model": MODEL, "input": "test"}),
        ]:
            status, _, _ = request(method, route, payload, token)
            assert status == 401, f"鉴权未拒绝: {route}, HTTP {status}"
            checks.append({"name": "authentication_rejected", "route": route, "status": status})
    status, models, _ = request("GET", "/v1/models")
    assert status == 200 and MODEL in [item["id"] for item in models["data"]]
    native = embed(TEXTS)
    reduced = embed(TEXTS, 1536)
    embed(TEXTS[1], 32)
    for index, text in enumerate(TEXTS):
        single = embed(text)[0]
        assert sum(x * y for x, y in zip(single, native[index])) > 0.999
    for dimensions, vectors in [(2560, native), (1536, reduced)]:
        related = sum(x * y for x, y in zip(vectors[0], vectors[1]))
        unrelated = sum(x * y for x, y in zip(vectors[0], vectors[2]))
        assert related > unrelated, "相关英文片段的相似度未高于无关片段"
        checks.append({"name": "cross_language_relevance_smoke", "dimensions": dimensions,
                       "related": round(related, 6), "unrelated": round(unrelated, 6)})
    invalids = [
        {"model": MODEL, "input": "test", "dimensions": 0},
        {"model": MODEL, "input": "test", "dimensions": 31},
        {"model": MODEL, "input": "test", "dimensions": 2561},
        {"model": "wrong-model", "input": "test"},
        {"model": MODEL, "input": []},
        {"model": MODEL, "input": "hello " * (args.max_model_len + 1)},
    ]
    for payload in invalids:
        status, _, _ = request("POST", "/v1/embeddings", payload)
        assert 400 <= status < 500, f"非法输入未被拒绝: HTTP {status}"
        checks.append({"name": "invalid_input_rejected", "status": status})
    print(json.dumps({"model": MODEL, "checks": checks, "passed": True}, indent=2))


if __name__ == "__main__":
    main()
