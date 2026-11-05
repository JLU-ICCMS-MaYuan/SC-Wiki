"""下载固定版本模型，并核对 Hugging Face Git/LFS 文件身份。"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request


MANIFEST = Path(__file__).with_name("model-manifest.json")


def valid_file(path, item):
    if not path.is_file() or path.stat().st_size != item["size"]:
        return False
    digest = hashlib.sha256() if "lfs" in item else hashlib.sha1()
    if "lfs" not in item:
        digest.update(f"blob {item['size']}\0".encode())
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    expected = item["lfs"]["oid"] if "lfs" in item else item["oid"]
    return digest.hexdigest() == expected


def verify_model(target, manifest):
    failed = [item["path"] for item in manifest["files"]
              if not valid_file(target / item["path"], item)]
    if failed:
        raise RuntimeError("模型文件缺失或校验失败: " + ", ".join(failed))


def download_file(target, manifest, item, weights_source):
    path = target / item["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if valid_file(path, item):
        print("verified", item["path"], flush=True)
        return
    quoted = urllib.parse.quote(item["path"], safe="/")
    if weights_source == "modelscope" and path.suffix == ".safetensors":
        url = f"https://modelscope.cn/models/{manifest['model']}/resolve/master/{quoted}"
    else:
        url = (f"https://hf-mirror.com/{manifest['model']}/resolve/"
               f"{manifest['revision']}/{quoted}")
    partial = path.with_name(path.name + ".partial")
    for attempt in range(3):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset == item["size"]:
            if valid_file(partial, item):
                partial.replace(path)
                return
            raise RuntimeError("下载内容与固定 revision 不符: " + item["path"])
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        if offset:
            request.add_header("Range", f"bytes={offset}-")
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                if response.status == 206:
                    if not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                        raise RuntimeError("下载续传位置错误")
                    mode = "ab"
                else:
                    mode = "wb"
                print("downloading", item["path"], "offset", offset, flush=True)
                with partial.open(mode) as stream:
                    while block := response.read(1024 * 1024):
                        stream.write(block)
                        if stream.tell() > item["size"]:
                            raise RuntimeError("下载文件超出清单大小")
            if not valid_file(partial, item):
                raise RuntimeError("下载内容与固定 revision 不符: " + item["path"])
            partial.replace(path)
            print("downloaded and verified", item["path"], flush=True)
            return
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--weights-source", choices=["modelscope", "hf-mirror"], default="modelscope")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    if not args.verify_only:
        args.target.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda item: download_file(args.target, manifest, item, args.weights_source),
                          manifest["files"]))
    verify_model(args.target, manifest)
    print(json.dumps({"model": manifest["model"], "revision": manifest["revision"],
                      "files_verified": len(manifest["files"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
