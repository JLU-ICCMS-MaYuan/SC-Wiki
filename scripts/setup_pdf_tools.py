"""准备隔离 Marker 与官方 llama.cpp 制品，只写指定运行目录。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from urllib.request import Request, urlopen

REPOSITORY = Path(__file__).resolve().parents[1]


def setup(root, existing_marker=None, existing_llama=None):
    root = Path(root).absolute()
    root.mkdir(parents=True, exist_ok=True)
    marker, llama = root / "marker", root / "llama"
    if not marker.exists():
        if existing_marker:
            marker.symlink_to(Path(existing_marker).absolute(), target_is_directory=True)
        else:
            subprocess.run([sys.executable, "-m", "venv", str(marker)], check=True)
    def probe():
        return json.loads(subprocess.check_output([str(marker / "bin/python"), "-c",
            "import importlib.metadata as m,json\nvalues={}\nfor n in ['marker-pdf','surya-ocr','torch']:\n try: values[n]=m.version(n)\n except m.PackageNotFoundError: values[n]=None\nprint(json.dumps(values))"], text=True))
    versions = probe()
    if versions["marker-pdf"] is None and not existing_marker and not marker.is_symlink():
        if platform.system() == "Linux":
            # 默认 llama.cpp CPU 路径无需 CUDA；官方 CPU 制品避免下载整套 GPU runtime。
            subprocess.run([str(marker / "bin/python"), "-m", "pip", "install",
                            "torch==2.14.1+cpu", "torchvision==0.29.1+cpu", "--extra-index-url",
                            "https://download.pytorch.org/whl/cpu"], check=True)
        subprocess.run([str(marker / "bin/python"), "-m", "pip", "install", "-r",
                        str(REPOSITORY / "backend/ingest/marker-requirements.txt")], check=True)
        versions = probe()
    if versions["marker-pdf"] != "2.0.0" or versions["surya-ocr"] != "0.22.1":
        raise ValueError("已有 Marker 环境版本不匹配，不覆盖")
    if not llama.exists():
        if existing_llama:
            llama.symlink_to(Path(existing_llama).absolute(), target_is_directory=True)
        else:
            system = {"Darwin": "macos", "Linux": "ubuntu"}.get(platform.system())
            arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "AMD64": "x64"}.get(platform.machine())
            if not system or not arch:
                raise ValueError("此平台需要显式准备 llama-server")
            asset_name = f"llama-b11580-bin-{system}-{arch}.tar.gz"
            with urlopen("https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b11580", timeout=60) as response:
                release = json.load(response)
            asset = next((a for a in release["assets"] if a["name"] == asset_name), None)
            if not asset or not asset.get("digest", "").startswith("sha256:"):
                raise ValueError("官方制品或校验摘要不可用")
            archive = root / asset_name
            with urlopen(Request(asset["url"], headers={"Accept": "application/octet-stream", "User-Agent": "SC-Wiki"}), timeout=120) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
            with archive.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != asset["digest"].split(":", 1)[1]:
                raise ValueError("llama.cpp 制品校验失败")
            unpack = root / "llama-package"
            unpack.mkdir(exist_ok=True)
            with tarfile.open(archive) as tar:
                tar.extractall(unpack, filter="data")
            binary = next(unpack.rglob("llama-server"))
            llama.symlink_to(binary.parent, target_is_directory=True)
    if not (llama / "llama-server").is_file():
        raise ValueError("缺少 llama-server")
    binary_version = subprocess.run([str(llama / "llama-server"), "--version"], check=True, capture_output=True, text=True)
    if "11580" not in binary_version.stdout + binary_version.stderr:
        raise ValueError("llama.cpp 运行版本不是 b11580，不覆盖既有制品")
    data = {"marker_python": str(marker / "bin/python"), "llama_server": str(llama / "llama-server"), "versions": versions}
    (root / "runtime.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root", type=Path, default=REPOSITORY / ".local/pdf-tools")
    cli.add_argument("--existing-marker", type=Path)
    cli.add_argument("--existing-llama", type=Path)
    args = cli.parse_args()
    setup(args.root, args.existing_marker, args.existing_llama)
