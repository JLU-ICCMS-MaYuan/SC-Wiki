"""准备主站模型原始制品；沿用已验收下载包格式，不改变原始字节。"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("TC_MODEL_CACHE", ROOT / ".local/tc-model-demo")).resolve()
REPO = "henniggroup/BETE-NET"
REVISION = "56bc783908a60e8a15e31b60018e6f3c3e48f593"


def gh(*args):
    for attempt in range(3):
        try:
            return subprocess.check_output(["gh", "api", *args], timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def valid(path, sha):
    if not path.is_file():
        return False
    b = path.read_bytes()
    return hashlib.sha1(f"blob {len(b)}\0".encode() + b).hexdigest() == sha


def save(path, content, sha):
    digest = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
    if digest != sha:
        raise ValueError(f"上游对象校验不符：{path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    part.write_bytes(content)
    part.replace(path)


def blob(repo, entry, path):
    if not valid(path, entry["sha"]):
        data = gh(f"repos/{repo}/git/blobs/{entry['sha']}", "-H", "Accept: application/vnd.github.raw+json")
        save(path, data, entry["sha"])


def build_bete_dataset():
    """把同一公开版本的数据、结构和样本名单合为一份下载，原文件字节不变。"""
    tree = json.loads((CACHE / "bete-tree.json").read_text())
    entries = {e["path"]: e for e in tree["tree"] if e["type"] == "blob"}
    paths = [p for p in entries if p.startswith(("structures/", "indices/")) or p in ("database.json", "LICENSE")]
    output = CACHE / "datasets/bete-net-dataset.zip"
    temporary = output.with_suffix(".zip.part")
    manifest = []
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(paths):
            source = CACHE / "datasets/bete-net-database.json" if name == "database.json" else CACHE / "bete" / name
            if not valid(source, entries[name]["sha"]):
                raise ValueError(f"数据包内原文件校验失败：{name}")
            data = source.read_bytes()
            info = zipfile.ZipInfo(name, (2026, 10, 26, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
            manifest.append({"path": name, "git_blob": entries[name]["sha"], "sha256": hashlib.sha256(data).hexdigest()})
        readme = (
            "BETE-NET 作者公开数据集（SC-Wiki 整理下载包）\n\n"
            "database.json：材料的谱和性质数据。\n"
            "structures/：对应晶体结构，记录原子如何排列。\n"
            "indices/：作者的训练、验证和测试样本名单。\n"
            "LICENSE：作者发布的使用许可。SOURCE.json：固定版本、来源及原文件摘要。\n\n"
            "这些文件是同一套公开资料的组成部分，不是不同模型的数据集。原文件字节未改写，只有外层打包由本站完成。\n"
            "当前公开数据库含 806 条记录；论文和其他发布制品的样本数量存在差异。这个包收齐当前公开版本的上述文件，"
            "不代表补齐了作者未公开或不同版本的全部原始计算文件，也不证明论文指标已经完全复现。\n"
            f"原始网站：https://github.com/{REPO}\n固定版本：{REVISION}\n"
        )
        for name, data in [("README_SC_WIKI.txt", readme), ("SOURCE.json", json.dumps({"repository": REPO, "revision": REVISION, "packaged_by": "SC-Wiki Demo", "files": manifest}, ensure_ascii=False, indent=2))]:
            info = zipfile.ZipInfo(name, (2026, 10, 26, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data.encode())
    temporary.replace(output)
    return output


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    tree = json.loads(gh(f"repos/{REPO}/git/trees/{REVISION}?recursive=1"))
    if tree.get("truncated"):
        raise ValueError("作者文件树不完整")
    entries = {v["path"]: v for v in tree["tree"] if v["type"] == "blob"}
    (CACHE / "bete-tree.json").write_text(json.dumps(tree))
    # 结构和索引通过 GraphQL 批量读取，逐文件按原始 Git blob 校验。
    texts = [v for p, v in entries.items() if p.startswith(("structures/", "indices/", "utils/")) and not "__pycache__" in p or p in ("LICENSE", "README.md")]
    missing = [v for v in texts if not valid(CACHE / "bete" / v["path"], v["sha"])]
    for offset in range(0, len(missing), 40):
        batch = missing[offset:offset + 40]
        fields = " ".join(f'b{i}:object(oid:"{e["sha"]}"){{... on Blob{{text oid}}}}' for i, e in enumerate(batch))
        query = '{repository(owner:"henniggroup",name:"BETE-NET"){' + fields + '}}'
        result = json.loads(gh("graphql", "-f", "query=" + query))
        if result.get("errors"):
            raise ValueError(result["errors"])
        for i, e in enumerate(batch):
            value = result["data"]["repository"][f"b{i}"]
            save(CACHE / "bete" / e["path"], value["text"].encode(), e["sha"])
        print(f"结构／划分文件 {min(offset + 40, len(missing))}/{len(missing)}", flush=True)
    blob(REPO, entries["database.json"], CACHE / "datasets/bete-net-database.json")
    for repo, sha, name in [
        ("henniggroup/symbolic-regression-utilities", "17feb9f6a48ebe68f512364e8cbd43ec36b4b6cd", "sisso-2019-train.dat"),
        ("henniggroup/symbolic-regression-utilities", "cd1220ef2094a13b2ed3f9811af2e2604d8a2a28", "sisso-2019-data.csv"),
    ]:
        blob(repo, {"sha": sha}, CACHE / "datasets" / name)
    # 这是本站打包的辅助材料，压缩包内保留原文件与版本清单，不冒充作者发布包。
    with zipfile.ZipFile(CACHE / "datasets/bete-structures-splits.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for e in sorted(texts, key=lambda v: v["path"]):
            if e["path"].startswith(("structures/", "indices/")) or e["path"] == "LICENSE":
                info = zipfile.ZipInfo(e["path"], (2026, 10, 26, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, (CACHE / "bete" / e["path"]).read_bytes())
        info = zipfile.ZipInfo("SOURCE.json", (2026, 10, 26, 0, 0, 0))
        z.writestr(info, json.dumps({"repository": REPO, "revision": REVISION, "packaged_by": "SC-Wiki Demo", "files": [{"path": e["path"], "git_blob": e["sha"]} for e in texts if e["path"].startswith(("structures/", "indices/")) or e["path"] == "LICENSE"]}, indent=2))
    build_bete_dataset()
    weights = [entries[f"CSO/model_cso_{i}.pt"] for i in range(100)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for i, _ in enumerate(pool.map(lambda e: blob(REPO, e, CACHE / "bete" / e["path"]), weights), 1):
            if i % 5 == 0:
                print(f"CSO 原始权重 {i}/100", flush=True)
    # 原作者输出只用于数值回归验收，不用作网站预测结果。
    blob(REPO, entries["test_preds/CSO.json"], CACHE / "bete/reference-cso.json")
    # 上游暂时不可用不会破坏已取得的其他模型；后续重跑可补齐同一原始包。
    xie = CACHE / "datasets/xie-2022-data_tables.zip"
    expected_md5 = "86c68504d1780b6fc7eaccbd4116706c"
    if not xie.is_file() or hashlib.md5(xie.read_bytes()).hexdigest() != expected_md5:
        try:
            url = "https://archive.materialscloud.org/api/records/skdzy-kyx54/files/data_tables.zip/content"
            with urllib.request.urlopen(url, timeout=20) as response:
                data = response.read(1024 * 1024)
            if len(data) != 429059 or hashlib.md5(data).hexdigest() != expected_md5:
                raise ValueError("Xie 原包大小或发布方 MD5 不符")
            xie.write_bytes(data)
        except (OSError, ValueError) as exc:
            print(f"Xie 2022 原包暂不可用（{type(exc).__name__}），不生成替代文件", flush=True)
    print("原始文件准备完成", flush=True)


if __name__ == "__main__":
    main()
