"""主站多模型预测与来源数据接口。"""
import hashlib
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.prediction import artifacts
from backend.prediction.inference import CACHE, predict
from backend.prediction.runner import PredictionError, run_structure, runtime_python

router = APIRouter(prefix="/api/tc-models", tags=["tc-models"])


@router.get("/catalog")
def catalog():
    return artifacts.catalog()


@router.get("/health")
def health():
    return {"status": "ok", "runtime_available": runtime_python().is_file(),
            "weights": sum((CACHE / "bete/CSO" / f"model_cso_{i}.pt").is_file() for i in range(100))}


@router.api_route("/datasets/{identifier}", methods=["GET", "HEAD"])
def download(identifier: str):
    item = artifacts.dataset(identifier)
    if item is None:
        raise HTTPException(404, "没有这个数据文件")
    error = artifacts.file_status(item)
    if error:
        raise HTTPException(503, error)
    path = CACHE / "datasets" / item["filename"]
    with path.open("rb") as stream:
        sha = item["sha256"] or hashlib.file_digest(stream, "sha256").hexdigest()
    return FileResponse(path, filename=item["filename"],
                        media_type="application/zip" if path.suffix == ".zip" else "application/octet-stream",
                        headers={"X-Content-SHA256": sha, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/examples/{identifier}")
def example(identifier: str):
    ids = {"nb": "305", "pb": "21", "al": "689"}
    if identifier not in ids:
        raise HTTPException(404, "未知结构样本")
    path = CACHE / "bete/structures" / f"{ids[identifier]}.cif"
    if not path.is_file() or path.is_symlink():
        raise HTTPException(503, "原始结构样本尚未准备完成")
    return {"structure": path.read_text(), "format": "cif", "note": "作者发布样本用于演示实际运行，不作为独立泛化评估。"}


@router.post("/predict")
async def prediction(request: Request):
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 300 * 1024:
            raise HTTPException(413, "预测输入超过大小限制")
        chunks.append(chunk)
    try:
        data = json.loads(b"".join(chunks))
        if not isinstance(data, dict) or data.get("model_id") not in ("bete-cso", "sisso-2019", "sisso-2022"):
            raise ValueError("请选择已接入的模型")
        if not isinstance(data.get("parameters", {}), dict) or not isinstance(data.get("structure", ""), str):
            raise ValueError("预测输入格式不正确")
        if data.get("format", "auto") not in ("auto", "cif", "vasp"):
            raise ValueError("请选择自动识别、CIF 或 POSCAR／CONTCAR")
        if data["model_id"] == "bete-cso":
            if not data.get("structure", "").strip() or len(data["structure"].encode()) > 256 * 1024:
                raise ValueError("请提供非空且不超过 256 KiB 的结构")
            return await run_structure(data)
        return predict(data)
    except PredictionError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    except (ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(400, str(exc)) from exc
