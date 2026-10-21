#!/usr/bin/env python3
"""对已校验 Docker 归档生成/恢复差分；还原结果必须与完整目标归档逐字节一致。"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path: Path, expected: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest(path) != expected:
        raise ValueError("归档摘要不一致：" + path.name)


def verify_export(folder: Path) -> dict:
    rows = [line.split() for line in (folder / "checksums.sha256").read_text().splitlines()]
    if len(rows) != 2 or {row[1] for row in rows if len(row) == 2} != {"image.tar.gz", "source.json"}:
        raise ValueError("源归档校验清单无效")
    for expected, name in rows:
        check(folder / name, expected)
    return json.loads((folder / "source.json").read_text())


def expand(source: Path, target: Path) -> None:
    with gzip.open(source, "rb") as inp, target.open("xb") as out:
        shutil.copyfileobj(inp, out, 1024 * 1024)


def create(base: Path, target: Path, output: Path, source_commit: str) -> None:
    verify_export(base)
    source = verify_export(target)
    config = source["config"]
    if (config["architecture"] != "amd64" or config["os"] != "linux"
            or config["config"]["Labels"]["org.opencontainers.image.revision"] != source_commit):
        raise ValueError("目标架构或源码身份不一致")
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="scwiki-image-delta-", dir=output.parent) as tmp:
        scratch = Path(tmp)
        a, b = scratch / "base.tar", scratch / "target.tar"
        expand(base / "image.tar.gz", a)
        expand(target / "image.tar.gz", b)
        manifest = {
            "format": "scwiki-docker-archive-delta-v1", "source_commit": source_commit,
            "image_digest": source["Digest"], "target_tar_bytes": b.stat().st_size,
            "base_archive_sha256": digest(base / "image.tar.gz"),
            "target_archive_sha256": digest(target / "image.tar.gz"),
            "base_tar_sha256": digest(a), "target_tar_sha256": digest(b),
            "source_sha256": digest(target / "source.json"),
        }
        delta = output / "image.vcdiff"
        subprocess.run(["xdelta3", "-e", "-S", "lzma", "-B", "268435456", "-s", str(a), str(b), str(delta)], check=True)
        manifest["delta_sha256"] = digest(delta)
        # 删除本步骤自己的临时完整目标，给真实解码验证腾出磁盘空间。
        b.unlink()
        subprocess.run(["xdelta3", "-d", "-s", str(a), str(delta), str(b)], check=True)
        check(b, manifest["target_tar_sha256"])
        shutil.copyfile(target / "source.json", output / "source.json")
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps({"delta_bytes": delta.stat().st_size,
                          "target_tar_bytes": manifest["target_tar_bytes"], "roundtrip_verified": True}))


def restore(base_archive: Path, package: Path, output: Path) -> None:
    manifest = json.loads((package / "manifest.json").read_text())
    if manifest["format"] != "scwiki-docker-archive-delta-v1":
        raise ValueError("未知差分格式")
    if output.exists():
        raise ValueError("目标文件已经存在，拒绝覆盖")
    check(base_archive, manifest["base_archive_sha256"])
    check(package / "source.json", manifest["source_sha256"])
    check(package / "image.vcdiff", manifest["delta_sha256"])
    with tempfile.TemporaryDirectory(prefix="scwiki-image-base-", dir=output.parent) as tmp:
        a = Path(tmp) / "base.tar"
        expand(base_archive, a)
        check(a, manifest["base_tar_sha256"])
        subprocess.run(["xdelta3", "-d", "-s", str(a), str(package / "image.vcdiff"), str(output)], check=True)
        check(output, manifest["target_tar_sha256"])
    print(json.dumps({"restored": True, "target_tar_bytes": output.stat().st_size,
                      "target_tar_sha256": manifest["target_tar_sha256"]}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    c = commands.add_parser("create")
    c.add_argument("--base", type=Path, required=True)
    c.add_argument("--target", type=Path, required=True)
    c.add_argument("--output", type=Path, required=True)
    c.add_argument("--source-commit", required=True)
    r = commands.add_parser("restore")
    r.add_argument("--base-archive", type=Path, required=True)
    r.add_argument("--package", type=Path, required=True)
    r.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "create":
        create(args.base, args.target, args.output, args.source_commit)
    else:
        restore(args.base_archive, args.package, args.output)


if __name__ == "__main__":
    main()
