"""统一文档中间表示（Document IR）。

该模块只描述解析结果，不负责调用解析器、模型或数据库。所有坐标和页码
在进入 IR 时完成规范化，后续 Claim/Evidence 只引用这里的稳定块身份。
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BlockType(StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    FIGURE = "figure"
    FORMULA = "formula"
    CAPTION = "caption"
    OCR_TEXT = "ocr_text"


class ParseMode(StrEnum):
    TEXT = "text"
    OCR = "ocr"
    VLM = "vlm"


def content_hash(*parts: Any) -> str:
    """对可 JSON 化的规范内容生成稳定 SHA-256。"""
    encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PageGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pdf_page: int = Field(ge=1)
    printed_page: int | None = None
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class DocumentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(min_length=1, max_length=255)
    block_type: BlockType
    pdf_page: int = Field(ge=1)
    printed_page: int | None = None
    reading_order: int = Field(ge=0)
    text: str = ""
    bbox: tuple[float, float, float, float] | None = None
    polygon: list[tuple[float, float]] | None = None
    page_width: float | None = Field(default=None, gt=0)
    page_height: float | None = Field(default=None, gt=0)
    parent_block_id: str | None = None
    table_id: str | None = None
    figure_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    content_hash: str = Field(min_length=64, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("bbox")
    @classmethod
    def validate_bbox_order(cls, value: tuple[float, float, float, float] | None):
        if value is not None and (value[0] > value[2] or value[1] > value[3]):
            raise ValueError("bbox 必须满足 x0<=x1 且 y0<=y1")
        return value

    @field_validator("polygon")
    @classmethod
    def validate_polygon_points(cls, value: list[tuple[float, float]] | None):
        if value is not None and len(value) < 4:
            raise ValueError("polygon 至少需要 4 个点")
        return value

    @model_validator(mode="after")
    def validate_geometry(self):
        if self.bbox is not None and self.page_width and self.page_height:
            x0, y0, x1, y1 = self.bbox
            if x0 < 0 or y0 < 0 or x1 > self.page_width or y1 > self.page_height:
                raise ValueError("bbox 超出页面边界")
        if self.polygon is not None and self.page_width and self.page_height:
            if any(x < 0 or y < 0 or x > self.page_width or y > self.page_height for x, y in self.polygon):
                raise ValueError("polygon 超出页面边界")
        return self


class TableCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str = Field(min_length=1)
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    text: str = ""
    block_id: str | None = None
    bbox: tuple[float, float, float, float] | None = None


class DocumentTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: str = Field(min_length=1)
    pdf_page: int = Field(ge=1)
    block_id: str | None = None
    cells: list[TableCell] = Field(default_factory=list)
    row_count: int = Field(default=0, ge=0)
    column_count: int = Field(default=0, ge=0)


class DocumentIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    source_file_id: str = Field(min_length=1)
    source_sha256: str = Field(min_length=64, max_length=64)
    source_version: int = Field(default=1, ge=1)
    parse_profile: str = Field(min_length=1)
    parser: dict[str, Any] = Field(default_factory=dict)
    pages: list[PageGeometry] = Field(default_factory=list)
    blocks: list[DocumentBlock] = Field(default_factory=list)
    tables: list[DocumentTable] = Field(default_factory=list)
    figures: list[dict[str, Any]] = Field(default_factory=list)
    formulas: list[dict[str, Any]] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_blocks(self):
        page_map = {page.pdf_page: page for page in self.pages}
        block_ids: set[str] = set()
        for block in self.blocks:
            if block.block_id in block_ids:
                raise ValueError(f"重复 block_id：{block.block_id}")
            block_ids.add(block.block_id)
            page = page_map.get(block.pdf_page)
            if page is not None:
                if block.printed_page is None:
                    block.printed_page = page.printed_page
                if block.page_width is None:
                    block.page_width = page.width
                if block.page_height is None:
                    block.page_height = page.height
        return self

    def block(self, block_id: str) -> DocumentBlock | None:
        return next((block for block in self.blocks if block.block_id == block_id), None)

    def model_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))
