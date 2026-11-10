"""将超出已观察单图容量的图片无损分片；原图编号与坐标保持不变。"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math

from PIL import Image

VERSION = 'lossless-image-tiles-v1'
# 本机上游实际拒绝33120个32px块并报告30000上限；不是对所有模型容量的声明。
PATCH_SIZE = 32
MAX_PATCHES = 30000
OVERLAP = 64


def _patches(width, height):
    return math.ceil(width / PATCH_SIZE) * math.ceil(height / PATCH_SIZE)


def _boxes(width, height):
    pending = [(0, 0, width, height)]
    output = []
    while pending:
        left, top, right, bottom = pending.pop(0)
        w, h = right - left, bottom - top
        if _patches(w, h) <= MAX_PATCHES:
            output.append([left, top, right, bottom])
            continue
        # 沿长边分割；相邻片重叠，轴、文字和曲线跨边界时仍有共同上下文。
        if h >= w:
            middle = (top + bottom) // 2
            overlap = min(OVERLAP, (h - 2) // 4)
            pending.extend([(left, top, right, middle + overlap),
                            (left, middle - overlap, right, bottom)])
        else:
            middle = (left + right) // 2
            overlap = min(OVERLAP, (w - 2) // 4)
            pending.extend([(left, top, middle + overlap, bottom),
                            (middle - overlap, top, right, bottom)])
    return sorted(output, key=lambda box: (box[1], box[0]))


def prepare_image_inputs(system_prompt, options):
    """归档/预算/缓存前处理本次直接图片；不抓取URL、不改变历史工具消息。"""
    images = options.get('images') or []
    prepared, manifest = [], []
    changed = False
    for number, url in enumerate(images, 1):
        if not isinstance(url, str) or not url.startswith('data:image/') or ';base64,' not in url:
            prepared.append(url)
            manifest.append({'original_image': number, 'attachment': len(prepared), 'unchanged': True})
            continue
        raw = base64.b64decode(url.split(',', 1)[1], validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            boxes = _boxes(width, height)
            source_hash = hashlib.sha256(raw).hexdigest()
            for box in boxes:
                if len(boxes) == 1:
                    tile_url, tile_hash = url, source_hash
                else:
                    changed = True
                    tile = image.crop(box)
                    stream = io.BytesIO()
                    tile.save(stream, format='PNG', **({'dpi': image.info['dpi']} if 'dpi' in image.info else {}))
                    content = stream.getvalue()
                    tile_hash = hashlib.sha256(content).hexdigest()
                    tile_url = 'data:image/png;base64,' + base64.b64encode(content).decode()
                prepared.append(tile_url)
                manifest.append({'original_image': number, 'original_size': [width, height],
                    'original_sha256': source_hash, 'attachment': len(prepared), 'bbox_pixels': box,
                    'image_sha256': tile_hash, 'resized': False})
    if not changed:
        return system_prompt, options
    instruction = (
        '\nImage transport: ' + VERSION + '. Some original images are sent as ordered overlapping '
        'lossless tiles, with NO resizing. The following trusted manifest maps the actual attachments '
        'to the ORIGINAL image numbers used by the task. Read every tile as part of its original image; '
        'do not treat tiles as separate figures or materials. All requested coordinates and image sizes '
        'still refer to the FULL ORIGINAL image, never an individual tile. For normalized tile '
        'coordinates (u,v), original normalized x=1000*(left+u*tile_width/1000)/original_width, '
        'y=1000*(top+v*tile_height/1000)/original_height. bbox_pixels uses exclusive right/bottom. '
        'Do not duplicate observations in overlaps or invent missing details. Report true unreadable '
        'content using the existing output schema.\nIMAGE_TILE_MANIFEST='
        + json.dumps(manifest, ensure_ascii=False, separators=(',', ':')) + '\n'
    )
    return system_prompt + instruction, {**options, 'images': prepared}
