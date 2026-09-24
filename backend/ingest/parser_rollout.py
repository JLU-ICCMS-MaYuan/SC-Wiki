"""解析方案和 Shadow/灰度/默认发布策略。"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from dataclasses import dataclass
from enum import StrEnum

from .document_parsers import ParserProfile


class RolloutStage(StrEnum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    GRAY = "gray"
    DEFAULT = "default"


@dataclass(frozen=True)
class RolloutConfig:
    stage: RolloutStage = RolloutStage.LEGACY
    default_profile: str = ParserProfile.LAYOUT
    gray_ratio: float = 0.0
    quality_report: dict | None = None
    allowlist_user_ids: frozenset[int] = frozenset()

    def __post_init__(self):
        if self.stage == RolloutStage.DEFAULT and not quality_gate_passed(self.quality_report):
            raise ValueError("默认新链路需要通过 50 篇人工标注质量门")
        if not 0 <= self.gray_ratio <= 1:
            raise ValueError("gray_ratio 必须位于 0 到 1 之间")


def _stable_ratio(task_id: str) -> float:
    digest = hashlib.sha256(task_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def select_profile(config: RolloutConfig, *, task_id: str, user_id: int | None = None, requested_profile: str | None = None) -> str:
    """选择一次任务使用的方案；不会在解析器失败后隐式改变方案。"""
    if requested_profile:
        return requested_profile
    if config.stage is RolloutStage.DEFAULT:
        return config.default_profile
    if config.stage is RolloutStage.GRAY:
        enabled = user_id in config.allowlist_user_ids or _stable_ratio(task_id) < config.gray_ratio
        return config.default_profile if enabled else "legacy"
    return "legacy"


def is_shadow(config: RolloutConfig) -> bool:
    return config.stage is RolloutStage.SHADOW


def configured_rollout() -> RolloutConfig:
    """从服务配置读取发布策略；未配置时保持旧链路。"""
    from backend.rag.config import settings

    stage = RolloutStage(settings.upload_parser_stage)
    report = None
    if stage == RolloutStage.DEFAULT and settings.upload_parser_quality_report:
        report = json.loads(Path(settings.upload_parser_quality_report).read_text(encoding="utf-8"))
    return RolloutConfig(
        stage=stage,
        default_profile=settings.upload_parser_default_profile,
        gray_ratio=settings.upload_parser_gray_ratio,
        quality_report=report,
    )


def quality_gate_passed(report: dict | None) -> bool:
    """读取维护者提供的评测报告，缺项、非有限值或质量退步都拒绝默认上线。"""
    if not isinstance(report, dict):
        return False
    count = report.get("annotated_papers")
    if isinstance(count, bool) or not isinstance(count, int) or count < 50:
        return False
    numeric = ("new_f1", "legacy_f1", "new_complex_recall", "legacy_complex_recall", "evidence_location_rate")
    if any(isinstance(report.get(k), bool) or not isinstance(report.get(k), (float,int))
           or not math.isfinite(report[k]) or not 0 <= report[k] <= 1 for k in numeric):
        return False
    return (report["new_f1"] >= report["legacy_f1"]
            and report["new_complex_recall"] > report["legacy_complex_recall"]
            and report["evidence_location_rate"] >= .95
            and type(report.get("unsupported_writes")) is int and report["unsupported_writes"] == 0
            and report.get("failure_recovery_passed") is True
            and report.get("legacy_revision_review_passed") is True)
