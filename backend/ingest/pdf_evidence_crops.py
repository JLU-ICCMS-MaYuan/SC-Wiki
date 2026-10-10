"""从原 PDF 渲染可核验的 300 DPI 局部证据，不持久化图片。"""

from __future__ import annotations

import base64
import math

import pymupdf


DPI = 300
CONTEXT_LINES = 3
MAX_CROP_PIXELS = 8_000_000


def _lines(page):
    result = []
    for block_number, block in enumerate(page.get_text("dict")["blocks"]):
        for line in block.get("lines", []):
            if any(span.get("text", "").strip() for span in line.get("spans", [])):
                result.append((block_number, pymupdf.Rect(line["bbox"])))
    return result


def _overlaps_column(line, band):
    overlap = max(0, min(line.x1, band.x1) - max(line.x0, band.x0))
    return overlap >= 0.4 * min(line.width, band.width)


def _clip_for_group(page, boxes, lines, context_lines):
    region = pymupdf.Rect(boxes[0])
    for box in boxes[1:]:
        region |= box
    relevant = [(block, rect) for block, rect in lines if rect.intersects(region)]
    top_pad = bottom_pad = 2
    if relevant:
        band = pymupdf.Rect(region)
        candidates = [rect for _, rect in lines if _overlaps_column(rect, band)]
        candidates.sort(key=lambda rect: (rect.y0, rect.x0))
        indexes = [i for i, rect in enumerate(candidates) if rect.intersects(region)]
        if indexes:
            start = max(0, min(indexes) - context_lines)
            end = min(len(candidates), max(indexes) + context_lines + 1)
            for rect in candidates[start:end]:
                region |= rect
            if start and candidates[start - 1].y1 < region.y0:
                top_pad = min(top_pad, (region.y0 - candidates[start - 1].y1) / 2)
            if end < len(candidates) and candidates[end].y0 > region.y1:
                bottom_pad = min(bottom_pad, (candidates[end].y0 - region.y1) / 2)
    else:
        # 没有文本行的可信图像区域只围绕已有坐标，不猜测段落位置。
        region += (-12, -12, 12, 12)
    return (region + (-8, -top_pad, 8, bottom_pad)) & page.rect


def _tiles(clip):
    pixels_per_point = DPI / 72
    max_height = MAX_CROP_PIXELS / (clip.width * pixels_per_point ** 2)
    count = max(1, math.ceil(clip.height / max_height))
    for index in range(count):
        yield pymupdf.Rect(clip.x0, clip.y0 + clip.height * index / count,
                           clip.x1, clip.y0 + clip.height * (index + 1) / count)


def _render(page, clip, boxes):
    pix = page.get_pixmap(dpi=DPI, clip=clip, alpha=False)
    highlights = []
    for box in boxes:
        visible = box & clip
        if not visible.is_empty:
            highlights.append([max(0, (visible.x0 - clip.x0) / clip.width),
                               max(0, (visible.y0 - clip.y0) / clip.height),
                               visible.width / clip.width, visible.height / clip.height])
    raster_dpi = None
    for info in page.get_image_info():
        area = pymupdf.Rect(info["bbox"])
        if area.is_empty or (area & clip).get_area() < clip.get_area() * 0.8:
            continue
        resolution = min(info["width"] * 72 / area.width, info["height"] * 72 / area.height)
        raster_dpi = round(resolution) if raster_dpi is None else min(raster_dpi, round(resolution))
    return {"image": "data:image/png;base64," + base64.b64encode(pix.tobytes("png")).decode(),
            "pdf_page": page.number + 1, "clip_bbox_pdf": list(clip), "highlights": highlights,
            "width": pix.width, "height": pix.height,
            "source_raster_dpi": raster_dpi if raster_dpi is not None and raster_dpi < DPI else None}


def render_evidence_crops(page, boxes, *, keep_together=False, context_lines=CONTEXT_LINES):
    """不连续的正文块分别显示；超大局部图继续按原分辨率分片。"""
    if not boxes:
        return []
    lines = _lines(page)
    grouped = {}
    for box in boxes:
        rect = pymupdf.Rect(box)
        block = None if keep_together else next((number for number, line in lines if line.intersects(rect)), None)
        grouped.setdefault(block, []).append(rect)
    crops = []
    for _, group in sorted(grouped.items(), key=lambda entry: (min(box.y0 for box in entry[1]), min(box.x0 for box in entry[1]))):
        clip = _clip_for_group(page, group, lines, context_lines)
        for tile in _tiles(clip):
            rendered = _render(page, tile, group)
            if rendered["highlights"]:
                crops.append(rendered)
    return crops
