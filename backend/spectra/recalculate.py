"""对当前保存谱重算；受限修正微小回折，不重新读图、不授予科学采纳。"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone

from backend import models
from . import manual
from .context import primitive_for, reference_choices, composition_for
from .contracts import fingerprint
from .topology import diagnose
from .preflight import prepare_repairs
from .frequency_repair import repair_frequencies
from .samples import connected_samples
from .relative import calculate_alpha, pixel_curve
from .dos import calculate_dos, dos_integrals, apply_dos

VERSION = "spectra-recalculate-sampled-range-v1"


def alpha_integrals(payload, references=None):
    """兼容调用入口；λ仅发布论文参考归一化结果。"""
    return calculate_alpha(payload,references or {})["raw"]


def save(session, ctx, row, run, state, kind, user):
    manual.assert_latest(session, ctx, row, kind)
    payload = copy.deepcopy(run.result_json)
    manual.require(any(c["kind"] == kind for c in payload["curves"]), "当前谱类型没有可计算数据")
    now = datetime.now(timezone.utc)
    repairs = prepare_repairs(payload,kind,now.isoformat())
    quality = payload.setdefault("quality", {})
    quality.setdefault("automatic_repairs",{})[kind]=repairs
    quality.setdefault("frequency_repairs",{})[kind]=repair_frequencies(payload,kind,now.isoformat())
    diagnostic_payload=payload
    if kind=="alpha2f":
        try:
            diagnostic_payload={**payload,"curves":[pixel_curve(payload,c)[0] if c["kind"]=="alpha2f" else c for c in payload["curves"]]}
        except (ValueError,ZeroDivisionError):
            pass
    quality.setdefault("trace_diagnostics", {})[kind] = diagnose(diagnostic_payload, kind)
    if kind == "alpha2f":
        references, reasons = reference_choices(state)
        computed = calculate_alpha(payload,references,reasons)
        quality["integrals"] = {"raw": computed["raw"]}
        quality["comparisons"] = {"raw": {"omega_log": computed["comparison"]}}
        payload.setdefault("candidates",{}).pop("alpha2f_lambda_normalized",None)
        if computed["candidate"] is not None:
            computed["candidate"]["base_run_id"]=run.id
            payload["candidates"]["alpha2f_lambda_normalized"]=computed["candidate"]
    else:
        apply_dos(payload, calculate_dos(payload, primitive_for(state, ctx.get("draft", {})), composition_for(state)), run.id)
    quality.setdefault("recalculations", {})[kind] = dict(base_run_id=run.id, calculated_at=now.isoformat(),
                                                         author_id=user.id, algorithm_version=VERSION)
    payload["status"] = "needs_review"
    payload["algorithm_version"] = VERSION
    fresh = models.SpectrumRun(id=uuid.uuid4().hex, collection_id=row.id,
        input_hash=fingerprint(dict(parent=run.id, kind=kind, actor=user.id, algorithm=VERSION)),
        algorithm_version=VERSION, status="succeeded", calibration_json=copy.deepcopy(run.calibration_json),
        result_json=payload, completed_at=now)
    session.add(fresh)
    session.flush()
    row.current_run_id = fresh.id
    row.version += 1
    row.review_json = {}
    return fresh
