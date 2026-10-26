"""本机 Demo：真实模型推理和经校验的原文件下载。"""
import hashlib
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from inference import CACHE, predict

HERE = Path(__file__).resolve().parent
CATALOG = json.loads((HERE / "catalog.json").read_text())
FILES = {item["id"]: item for item in CATALOG["datasets"]}
app = FastAPI(title="SC-Wiki 模型 Demo", docs_url=None, redoc_url=None, openapi_url=None)


def file_status(item):
    path = CACHE / "datasets" / item["filename"]
    if not item.get("sha256") and not path.is_file():
        return "上游文件暂不可用；原始发布页仍可查询"
    if not path.is_file() or path.is_symlink():
        return "本地原文件缺失，请重新准备数据"
    if path.stat().st_size != item["size"]:
        return "文件大小校验失败，已停止下载"
    # 直接校验完整字节，不仅凭文件存在或 HTTP 状态判断成功。
    with path.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    if item.get("sha256") and sha != item["sha256"]:
        return "文件摘要校验失败，已停止下载"
    if not item.get("sha256"):
        with path.open("rb") as stream:
            md5 = hashlib.file_digest(stream, "md5").hexdigest()
        if md5 != item.get("publisher_md5"):
            return "发布方摘要校验失败，已停止下载"
    return None


def checked_file(identifier):
    item = FILES.get(identifier)
    if not item:
        raise HTTPException(404, "没有这个数据文件")
    error = file_status(item)
    if error:
        raise HTTPException(503, error)
    return item, CACHE / "datasets" / item["filename"]


@app.get("/demo-api/health")
def health():
    return {"status": "ok", "environment": "本地实时开发 Demo", "weights": sum((CACHE / "bete/CSO" / f"model_cso_{i}.pt").is_file() for i in range(100))}


@app.get("/demo-api/catalog")
def catalog():
    datasets = []
    for item in CATALOG["datasets"]:
        error = file_status(item)
        view = {**item, "available": error is None, "error": error, "download_url": f"/demo-api/datasets/{item['id']}" if error is None else None}
        if not error and not item.get("sha256"):
            with (CACHE / "datasets" / item["filename"]).open("rb") as stream:
                view["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        datasets.append(view)
    return {"models": CATALOG["models"], "datasets": datasets}


@app.api_route("/demo-api/datasets/{identifier}", methods=["GET", "HEAD"])
def download(identifier):
    item, path = checked_file(identifier)
    media = "application/zip" if path.suffix == ".zip" else "application/json" if path.suffix == ".json" else "text/plain; charset=utf-8"
    with path.open("rb") as stream:
        sha = item["sha256"] or hashlib.file_digest(stream, "sha256").hexdigest()
    return FileResponse(path, media_type=media, filename=item["filename"], headers={"X-Content-SHA256": sha, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/demo-api/examples/{identifier}")
def example(identifier):
    ids = {"nb": "305", "pb": "21", "al": "689"}
    if identifier not in ids:
        raise HTTPException(404, "未知样本")
    path = CACHE / "bete/structures" / f"{ids[identifier]}.cif"
    if not path.is_file():
        raise HTTPException(503, "作者结构样本尚未准备完成")
    return {"structure": path.read_text(), "format": "cif", "source": f"https://github.com/henniggroup/BETE-NET/blob/56bc783908a60e8a15e31b60018e6f3c3e48f593/structures/{ids[identifier]}.cif", "note": "作者发布样本用于演示实际运行；不作为独立泛化评估。"}


@app.post("/demo-api/predict")
async def prediction(request: Request):
    body = await request.body()
    if len(body) > 300 * 1024:
        raise HTTPException(413, "输入超过 Demo 大小限制")
    try:
        data = json.loads(body)
        if not isinstance(data, dict) or data.get("model_id") not in ("bete-cso", "sisso-2019", "sisso-2022"):
            raise ValueError("请选择已接入的模型")
        if not isinstance(data.get("parameters", {}), dict):
            raise ValueError("参数格式不正确")
        if not isinstance(data.get("structure", ""), str):
            raise ValueError("结构必须为文本")
        return await run_in_threadpool(predict, data)
    except (ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, "模型制品缺失，请重新准备原始文件") from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc) if "正在运行" in str(exc) else "模型执行失败，请检查本地服务日志") from exc
