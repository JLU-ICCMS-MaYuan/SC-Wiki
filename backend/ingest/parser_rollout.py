"""解析方案和 Shadow/灰度/默认发布策略。"""

from __future__ import annotations

import hashlib
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
    allowlist_user_ids: frozenset[int] = frozenset()

    def __post_init__(self):
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
        enabled = user_id in config.allowlist_user_ids if user_id is not None and config.allowlist_user_ids else _stable_ratio(task_id) < config.gray_ratio
        return config.default_profile if enabled else "legacy"
    return "legacy"


def is_shadow(config: RolloutConfig) -> bool:
    return config.stage is RolloutStage.SHADOW


def configured_rollout() -> RolloutConfig:
    """从服务配置读取发布策略；未配置时保持旧链路。"""
    from backend.rag.config import settings

    try:
        stage = RolloutStage(settings.upload_parser_stage)
    except ValueError:
        stage = RolloutStage.LEGACY
    return RolloutConfig(
        stage=stage,
        default_profile=settings.upload_parser_default_profile,
        gray_ratio=settings.upload_parser_gray_ratio,
    )
