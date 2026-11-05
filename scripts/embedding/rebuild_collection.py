"""保留源集合，私有备份后向独立集合重建嵌入向量。"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from qdrant_client.models import PointStruct, VectorParams


def records(client, collection):
    offset = None
    while True:
        points, offset = client.scroll(collection_name=collection, offset=offset, limit=100,
                                       with_payload=True, with_vectors=True)
        yield from points
        if offset is None:
            break


def fingerprint(points):
    rows = sorted((json.dumps(p.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
                   for p in points))
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def rebuild(client, source, target, embed, backup, batch_size=10, model="", dimensions=1536):
    if source == target or client.collection_exists(target):
        raise ValueError("目标必须是尚不存在的独立集合")
    original = list(records(client, source))
    if not original:
        raise ValueError("源集合为空，请先核实实际目标")
    if any(not isinstance(p.payload.get("document"), str) or not p.payload["document"]
           for p in original):
        raise ValueError("源记录缺少文献正文，不能静默跳过")
    backup.mkdir(parents=True, exist_ok=False, mode=0o700)
    export = backup / "source.jsonl"
    with export.open("w") as stream:
        os.chmod(export, 0o600)
        for point in original:
            stream.write(json.dumps(point.model_dump(mode="json"), ensure_ascii=False) + "\n")
    source_hash = fingerprint(original)
    info = client.get_collection(source)
    client.create_collection(collection_name=target,
                             vectors_config=VectorParams(size=dimensions,
                                                         distance=info.config.params.vectors.distance))
    for start in range(0, len(original), batch_size):
        batch = original[start:start + batch_size]
        vectors = embed([p.payload["document"] for p in batch])
        if len(vectors) != len(batch) or any(
            len(v) != dimensions or not all(math.isfinite(x) for x in v) for v in vectors
        ):
            raise ValueError("模型响应数量、维度或数值不正确；原集合保持不变")
        client.upsert(collection_name=target, wait=True, points=[
            PointStruct(id=p.id, payload=p.payload, vector=v) for p, v in zip(batch, vectors)
        ])
        print(json.dumps({"completed": start + len(batch), "total": len(original)}), flush=True)
    rebuilt = list(records(client, target))
    if {str(p.id): p.payload for p in original} != {str(p.id): p.payload for p in rebuilt}:
        raise ValueError("目标 ID 或 payload 与源集合不一致，禁止切换")
    if any(not isinstance(p.vector, list) or len(p.vector) != dimensions
           or not all(math.isfinite(x) for x in p.vector) for p in rebuilt):
        raise ValueError("重读目标向量校验失败，禁止切换")
    if fingerprint(list(records(client, source))) != source_hash:
        raise ValueError("重建期间源集合变化，禁止切换")
    result = {"source": source, "target": target, "points": len(original),
              "source_sha256": source_hash, "model": model, "dimensions": dimensions,
              "payloads_preserved": True, "source_unchanged": True, "passed": True}
    (backup / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    os.chmod(backup / "receipt.json", 0o600)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="paper_chunks")
    parser.add_argument("--target", required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--dimensions", type=int, default=1536)
    args = parser.parse_args()
    from backend.ingest.embedder import embed_texts
    from backend.rag.config import settings
    from backend.rag.qdrant_connection import create_qdrant_client

    settings.embedding_base_url = args.base_url
    settings.embedding_api_key = args.key_file.read_text().strip()
    settings.embedding_model = "Qwen/Qwen3-Embedding-4B"
    settings.embedding_dimensions = args.dimensions
    result = rebuild(create_qdrant_client(), args.source, args.target, embed_texts,
                     args.backup, model=settings.embedding_model, dimensions=args.dimensions)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
