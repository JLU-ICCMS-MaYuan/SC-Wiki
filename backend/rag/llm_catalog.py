"""部署者提供的编号模型目录；公开表示永远不含端点或密钥。"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import os
import re
from typing import Mapping
from urllib.parse import urlparse

from dotenv import dotenv_values


class CatalogConfigError(ValueError):
    """只包含编号及字段名的配置错误。"""


@dataclass(frozen=True)
class CatalogModel:
    id: str
    name: str
    base_url: str
    model: str
    api_key: str = field(repr=False)

    def public(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name, "model": self.model}


@dataclass(frozen=True)
class LlmCatalog:
    items: tuple[CatalogModel, ...] = ()
    default_id: str = ""

    def find(self, identifier: str) -> CatalogModel | None:
        return next((item for item in self.items if item.id == identifier), None)


def parse_catalog(values: Mapping[str, str | None]) -> LlmCatalog:
    fields = {"NAME", "BASE_URL", "MODEL", "API_KEY"}
    groups: dict[int, dict[str, str]] = {}
    for key, raw in values.items():
        match = re.fullmatch(r"LLM(\d+)_(.+)", key)
        if not match:
            continue
        number, attribute = match.groups()
        if not re.fullmatch(r"[1-9]\d*", number) or attribute not in fields:
            raise CatalogConfigError("编号 LLM 配置含非法编号或未知字段")
        groups.setdefault(int(number), {})[attribute] = str(raw or "").strip()
    items = []
    for number, group in sorted(groups.items()):
        if not any(group.values()):
            continue
        missing = sorted(key for key in fields if not group.get(key))
        if missing:
            raise CatalogConfigError(f"LLM{number} 缺少字段：{', '.join(missing)}")
        if any("\n" in value or "\r" in value for value in group.values()):
            raise CatalogConfigError(f"LLM{number} 配置不得含换行")
        try:
            url = urlparse(group["BASE_URL"])
            # urllib 的异常可能包含原始端点；统一换成不含值的配置错误。
            port = url.port
        except ValueError:
            raise CatalogConfigError(f"LLM{number} BASE_URL 格式无效") from None
        if (url.scheme not in {"http", "https"} or not url.hostname
                or url.username or url.password or url.query or url.fragment or port == 0):
            raise CatalogConfigError(f"LLM{number} BASE_URL 格式无效")
        items.append(CatalogModel(f"LLM{number}", group["NAME"], group["BASE_URL"].rstrip("/"),
                                  group["MODEL"], group["API_KEY"]))
    default = str(values.get("LLM_DEFAULT") or "").strip()
    if default and default not in {item.id for item in items}:
        raise CatalogConfigError("LLM_DEFAULT 必须指向完整的编号配置")
    return LlmCatalog(tuple(items), default or (items[0].id if items else ""))


@lru_cache(maxsize=1)
def get_catalog() -> LlmCatalog:
    # 与 RagSettings 一样读取工作目录的 .env；容器环境覆盖文件值。
    return parse_catalog({**dotenv_values(".env"), **os.environ})
