"""自动与人工标定共用的谱合同；质量报告只由服务器生成。"""
from __future__ import annotations
from typing import Literal
import hashlib
import json
import math
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALGORITHM_VERSION = "spectra-production-v4"
FREQUENCY_FACTORS = {"THz": 1., "cm-1": .0299792458, "meV": .2417989242084918}


def conventional_structure_text(candidate):
    representations=candidate.get("representations") or {}
    conventional=representations.get("conventional") or {}
    cif=conventional.get("cif") or {}
    return cif.get("text")


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def panel_identity(panel: dict) -> str:
    """模型标签、图框微调及频率范围不是同一来源谱的稳定身份。"""
    return "spectrum-" + fingerprint({"state": panel.get("state_key"),
        "curves": sorted((c["kind"], c.get("projection") or "") for c in panel["curves"])})[:48]


class CurveCalibration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=96)
    kind: Literal["phonon_dos", "alpha2f", "cumulative_lambda"]
    projection: str | None = None
    color: Literal["red", "blue", "green", "magenta", "olive"]
    roi: tuple[int, int, int, int]
    display_bbox: tuple[int, int, int, int] | None = None
    frequency_direction: Literal["x", "y"]
    frequency_ticks: list[tuple[float, float]] = Field(min_length=2)
    amplitude_ticks: list[tuple[float, float]] = Field(min_length=2)
    frequency_unit: Literal["THz", "cm-1", "meV"] = "THz"
    frequency_scale: Literal["linear"] = "linear"
    amplitude_scale: Literal["linear"] = "linear"
    unit: str
    physical_definition_confirmed: bool = False
    amplitude_evidence: str | None = None
    exclude: list[tuple[int, int, int, int]] = Field(default_factory=list)
    zero_boundaries_thz: tuple[float | None, float | None] = (None, None)
    zero_reference_band_thz: tuple[float, float] | None = None

    @field_validator("zero_boundaries_thz", "zero_reference_band_thz", mode="before")
    @classmethod
    def empty_zero_evidence(cls, value, info):
        # 供应商可能用 []/null 表示未提供；未知不能转成物理零值。
        if value is None or value == []:
            return (None, None) if info.field_name == "zero_boundaries_thz" else None
        return value

    @model_validator(mode="after")
    def validate_axes(self):
        if self.display_bbox is not None:
            x0, y0, x1, y1 = self.display_bbox
            rx0, ry0, rx1, ry1 = self.roi
            if not (0 <= x0 < x1 and 0 <= y0 < y1 and x0 <= rx0 < rx1 <= x1 and y0 <= ry0 < ry1 <= y1):
                raise ValueError("显示裁切框必须完整包含当前曲线提取框")
        for ticks in (self.frequency_ticks, self.amplitude_ticks):
            if not all(math.isfinite(v) for pair in ticks for v in pair):
                raise ValueError("坐标刻度必须为有限数值")
            if len({p for p, _ in ticks}) < 2 or len({v for _, v in ticks}) < 2:
                raise ValueError("坐标刻度不能退化")
        if self.kind != "phonon_dos" and self.unit not in {"dimensionless", "unknown"}:
            raise ValueError("首版 α²F/累计λ 要求无量纲规范，未知单位不得伪积分")
        return self


class PanelCalibration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    panel_id: str = Field(min_length=1, max_length=96)
    state_key: str | None = None
    caption: str = ""
    curves: list[CurveCalibration] = Field(min_length=1, max_length=32)
    projection_scale_confirmed: bool = False
    projection_complete: bool = False

    @model_validator(mode="after")
    def unique_curves(self):
        if len({c.id for c in self.curves}) != len(self.curves):
            raise ValueError("曲线身份不能重复")
        for kind in ("alpha2f", "cumulative_lambda"):
            if sum(c.kind == kind for c in self.curves) > 1:
                raise ValueError("同一条件多条 α²F/累计λ 须拆分为独立谱集合，避免错误配对")
        return self


class SpectrumTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Literal["upload", "paper", "revision"]
    target_id: str = Field(min_length=1, max_length=64)


def state_signature(state: dict | None) -> str:
    if state is None:
        return fingerprint(None)
    # 状态条件和参考物性变化使核验失效；不把展示折叠状态等 UI 信息加入签名。
    keys = ("state_key", "material", "material_name", "reported_space_group_symbol",
            "reported_space_group_number", "pressure_value_gpa", "pressure_min_gpa",
            "pressure_max_gpa", "temperature_value_k", "magnetic_field_t", "state_kind", "structure_optimization",
            "calculation_context", "property_modules", "structure", "_spectrum_structure_hashes")
    from decimal import Decimal
    def canonical(value):
        if isinstance(value, dict):
            return {k: canonical(v) for k, v in value.items() if v is not None and k not in
                    {"id", "paper_id", "paper_revision", "material_state_id", "module_id", "definition_id",
                     "created_at", "updated_at", "record_checksum", "source_fingerprint", "record_key", "module_key",
                     "evidence", "evidences", "display_order", "is_representative", "deleted_record_keys", "deleted_module_keys"}}
        if isinstance(value, list):
            return [canonical(v) for v in value]
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            return str(Decimal(str(value)).normalize())
        return value
    values={k: state.get(k) for k in keys}
    if not values.get("_spectrum_structure_hashes"):
        values.pop("_spectrum_structure_hashes",None)
    return fingerprint(canonical(values))
