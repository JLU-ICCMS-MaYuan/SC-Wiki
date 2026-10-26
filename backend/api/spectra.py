"""正式谱提取、标定、独立审核、私有图片与带质量导出。"""
from typing import Literal
import csv
import io
import json
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.security import get_current_user, get_current_user_optional
from backend.rag.llm_context import request_llm_config, get_llm_config
from backend.services import spectra as service
from backend.spectra import jobs
from backend.spectra.contracts import SpectrumTarget, PanelCalibration

router = APIRouter(prefix="/api/rag/spectra", tags=["spectra"])


class ExtractRequest(SpectrumTarget):
    expected_version: str


class CalibrationRequest(ExtractRequest):
    expected_collection_version: int = Field(ge=1)
    calibration: PanelCalibration


class ReviewRequest(ExtractRequest):
    expected_collection_version: int = Field(ge=1)
    curve_id: str
    status: Literal["needs_review", "accepted", "accepted_limited", "excluded"]
    frequency_intervals_thz: list[tuple[float, float]] = Field(default_factory=list)
    reason: str = ""


class ManualRequest(ExtractRequest):
    expected_collection_version: int = Field(ge=1)
    base_run_id: str = Field(min_length=1, max_length=64)
    document: dict


@router.get("/{collection_id}/manual")
def manual_document(collection_id: str, target: Literal["upload", "paper", "revision"], target_id: str,
                    kind: Literal["alpha2f", "phonon_dos"], collection_version: int, run_id: str,
                    user=Depends(get_current_user), session: Session=Depends(get_db)):
    from backend.spectra import manual
    ctx = service.context(session, target, target_id, user, write=True)
    row, run, _ = manual.current(session, ctx, collection_id, collection_version, run_id)
    return manual.documents(session, ctx, row, run, kind)


@router.post("/{collection_id}/manual")
def save_manual(collection_id: str, body: ManualRequest, user=Depends(get_current_user), session: Session=Depends(get_db)):
    from backend.spectra import manual
    ctx = service.context(session, body.target, body.target_id, user, write=True)
    service.assert_version(ctx["version"], body.expected_version)
    row, run, _ = manual.current(session, ctx, collection_id, body.expected_collection_version, body.base_run_id)
    manual.save(session, ctx, row, run, body.document, user)
    session.commit()
    return service.listing(session, ctx)


@router.get("")
def list_spectra(target: Literal["upload", "paper", "revision"], target_id: str,
                 user=Depends(get_current_user_optional), session: Session=Depends(get_db)):
    ctx = service.context(session, target, target_id, user)
    return service.listing(session, ctx)


@router.post("/extract", dependencies=[Depends(request_llm_config)], status_code=202)
def extract(body: ExtractRequest, user=Depends(get_current_user), session: Session=Depends(get_db)):
    ctx = service.context(session, body.target, body.target_id, user, write=True)
    job = jobs.enqueue(session, ctx, expected_version=body.expected_version, config=get_llm_config())
    session.commit()
    jobs.dispatch(job, user.id)
    return {k:v for k,v in job.items() if k in {"job_id", "cached"}}


@router.put("/{collection_id}/calibration", dependencies=[Depends(request_llm_config)], status_code=202)
def correct_calibration(collection_id: str, body: CalibrationRequest, user=Depends(get_current_user),
                        session: Session=Depends(get_db)):
    ctx = service.context(session, body.target, body.target_id, user, write=True)
    row = service.checked_row(session, ctx, collection_id, body.expected_collection_version)
    job = jobs.enqueue(session, ctx, expected_version=body.expected_version, config=get_llm_config(), row=row,
        calibration=body.calibration.model_dump(), expected_collection_version=body.expected_collection_version)
    session.commit()
    jobs.dispatch(job, user.id)
    return dict(job_id=job["job_id"], cached=job.get("cached", False))


@router.post("/{collection_id}/review")
def review(collection_id: str, body: ReviewRequest, user=Depends(get_current_user), session: Session=Depends(get_db)):
    ctx = service.context(session, body.target, body.target_id, user, write=True)
    service.assert_version(ctx["version"], body.expected_version)
    row = service.checked_row(session, ctx, collection_id, body.expected_collection_version)
    service.review_curve(session, ctx, row, body.curve_id, body.status,
                         body.frequency_intervals_thz, body.reason, user)
    session.commit()
    return dict(version=row.version)


def visible_item(session, target, target_id, collection_id, user, run_id=None):
    ctx = service.context(session, target, target_id, user)
    if run_id:
        allowed = service.history(session, ctx, collection_id)
        if not any(run["id"] == run_id for run in allowed):
            service.fail("spectra_run_missing", "历史运行不存在", 404)
    item = next((i for i in service.listing(session, ctx, run_override=(collection_id, run_id) if run_id else None)["items"] if i["id"] == collection_id), None)
    if item is None:
        service.fail("spectra_collection_missing", "该谱不存在或尚未公开", 404)
    return item


@router.get("/{collection_id}/history")
def history(collection_id: str, target: Literal["upload", "paper", "revision"], target_id: str,
            user=Depends(get_current_user_optional), session: Session=Depends(get_db)):
    ctx = service.context(session, target, target_id, user)
    return dict(items=service.history(session, ctx, collection_id))


@router.get("/{collection_id}/runs/{run_id}")
def historical_run(collection_id: str, run_id: str, target: Literal["upload", "paper", "revision"], target_id: str,
                   user=Depends(get_current_user_optional), session: Session=Depends(get_db)):
    return visible_item(session, target, target_id, collection_id, user, run_id)


@router.get("/material-state/{paper_id}/{state_key}")
def state_spectra(paper_id: int, state_key: str, expected_revision: int,
                  user=Depends(get_current_user_optional), session: Session=Depends(get_db)):
    ctx = service.context(session, "paper", str(paper_id), user)
    service.assert_version(ctx["paper_revision"], expected_revision)
    return dict(paper_revision=ctx["paper_revision"],
                spectra=[i for i in service.listing(session, ctx)["items"] if i["state_key"] == state_key])


@router.get("/{collection_id}/image")
def image(collection_id: str, target: Literal["upload", "paper", "revision"], target_id: str,
          user=Depends(get_current_user_optional), session: Session=Depends(get_db)):
    from backend.storage import FileRef, create_storage
    from backend.storage.files import FileIntegrityError, FileStorageUnavailable
    item = visible_item(session, target, target_id, collection_id, user)
    try:
        storage = create_storage()
        ref = FileRef(**item["source"]["image"])
        storage.head(ref)
        with storage.open(ref) as source:
            return Response(source.read(), media_type="image/png", headers={"Cache-Control": "private, no-store"})
    except (FileIntegrityError, FileStorageUnavailable, FileNotFoundError):
        service.fail("spectra_image_unavailable", "谱原图暂不可读取；数值结果已保留，请检查文件存储", 503)


def csv_export(item):
    output = io.StringIO(newline="")
    fields = ["collection_id", "run_id", "algorithm_version", "state_key", "curve_id", "kind", "projection",
              "frequency_thz", "observed_amplitude", "reconstructed_amplitude", "status", "detection_mode",
              "pixel_low", "pixel_high", "unit", "frequency_unit", "source_frequency_unit",
              "normalized_dos_candidate", "normalized_dos_unit", "zero_baseline_candidate", "joint_candidate",
              "joint_cumulative_lambda", "boundary_mask", "review_status", "review_reason", "pdf_page", "source_sha256",
              "rejected_chromatic_pixels", "candidate_components", "reconstruction_blocked",
              "point_id", "frequency_pixel", "amplitude_pixel", "manual", "segment", "break_before",
              "revision_author_id", "base_run_id"]
    writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader()
    payload = item["result"]
    candidates = payload.get("candidates") or {}
    base = candidates.get("zero_baseline") or {}
    joint = candidates.get("joint") or {}
    bmap = dict(zip(base.get("frequency_thz") or [], base.get("amplitude") or []))
    jmap = dict(zip(joint.get("frequency_thz") or [], joint.get("alpha2f") or []))
    cmap = dict(zip(joint.get("frequency_thz") or [], joint.get("cumulative_lambda") or []))
    norm=candidates.get("dos_normalization") or {}
    for c in payload.get("curves") or []:
        normalized=dict(zip(norm.get("frequency_thz") or [], norm.get("components",{}).get(c["projection"] or c["id"],[])))
        decision = item["review"].get(c["id"], {})
        for p in c["points"]:
            freq = p["frequency_thz"]; alpha = c["kind"] == "alpha2f"
            writer.writerow(dict(collection_id=item["id"], run_id=item["run"]["id"],
                algorithm_version=item["run"]["algorithm_version"], state_key=item["state_key"], curve_id=c["id"],
                kind=c["kind"], projection=c["projection"], **{k:p.get(k) for k in ("frequency_thz",
                "observed_amplitude", "reconstructed_amplitude", "status", "detection_mode", "pixel_low", "pixel_high",
                "rejected_chromatic_pixels", "candidate_components", "reconstruction_blocked")},
                unit=c["unit"], frequency_unit="THz", source_frequency_unit=c.get("source_frequency_unit"),
                normalized_dos_candidate=normalized.get(freq), normalized_dos_unit=norm.get("unit") if normalized else None,
                zero_baseline_candidate=bmap.get(freq) if alpha else None,
                joint_candidate=jmap.get(freq) if alpha else None, joint_cumulative_lambda=cmap.get(freq) if alpha else None,
                boundary_mask=freq in c["clipped_frequencies_thz"], review_status=decision.get("status", "needs_review"),
                review_reason=decision.get("reason"), pdf_page=item["source"]["pdf_page"],
                source_sha256=item["source"]["source_sha256"],point_id=p.get("id"),
                frequency_pixel=p.get("frequency_pixel"),amplitude_pixel=p.get("amplitude_pixel"),
                manual=p.get("manual",False),segment=p.get("segment"),break_before=p.get("breakBefore"),
                revision_author_id=(payload.get("manual_provenance") or {}).get("author_id"),
                base_run_id=(payload.get("manual_provenance") or {}).get("base_run_id")))
    return output.getvalue()


@router.get("/{collection_id}/export")
def export(collection_id: str, target: Literal["upload", "paper", "revision"], target_id: str,
           format: Literal["json", "csv"]="json", run_id: str | None = None,
           user=Depends(get_current_user_optional), session: Session=Depends(get_db)):
    item = visible_item(session, target, target_id, collection_id, user, run_id)
    data = csv_export(item) if format == "csv" else json.dumps(item, ensure_ascii=False, allow_nan=False)
    return Response(data, media_type="text/csv; charset=utf-8" if format == "csv" else "application/json",
                    headers={"Content-Disposition": f'attachment; filename="spectrum-{collection_id}.{format}"'})
