"""仅绑定服务器原图唯一几何区域的技术身份，不修补科学字段。"""
from copy import deepcopy
import hashlib
import json
import math


def bind(action, context):
    result = deepcopy(action)
    bindings = []
    if not context or context.get('version') != 'program-panel-id-v1' or not isinstance(result, dict):
        return result, bindings
    arguments = result.get('arguments')
    if not isinstance(arguments, dict):
        return result, bindings
    name = result.get('name')
    if name in {'digitize_image_elements', 'verify_image_reading'}:
        panels = [arguments.get('panel')]
        region = arguments.get('region_id')
    elif name == 'report_chart_reading':
        panels = arguments.get('panels') or []
        region = context['default_region_id']
    else:
        return result, bindings
    geometry = context.get('regions', {}).get(region)
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        missing = 'panel' not in panel
        if not missing and not isinstance(panel['panel'], str):
            continue  # 错类型不按缺省修补，仍由规范Schema拒绝。
        axis = panel.get('axis')
        bounds = axis.get('bounds') if isinstance(axis, dict) else None
        matched = []
        if (geometry and isinstance(bounds, list) and len(bounds) == 2
                and all(type(v) in (int, float) and math.isfinite(v) for v in bounds)):
            lo, hi = sorted(bounds)
            resolution = geometry.get('localization_resolution', 0)
            if type(resolution) in (int, float) and math.isfinite(resolution) and resolution > 0:
                matched = [band for band in geometry.get('band_candidates', [])
                    if max(abs(lo-band['bbox'][1]), abs(hi-band['bbox'][3])) <= resolution]
        if len(matched) != 1:
            if missing:
                from .structured_output import StructuredOutputError
                raise StructuredOutputError('面板技术身份无法由当前原图几何唯一定位，未补写或执行工具')
            continue  # 已有合法原标签的旧协议保持；不添加全站新的几何门禁。
        identity = 'panel-geometry-' + hashlib.sha256(json.dumps([
            geometry['source_sha256'], geometry['pdf_page'], region, matched[0]['bbox']],
            sort_keys=True).encode()).hexdigest()[:16]
        preferred = context.get('preferred', {}).get(json.dumps([identity, panel.get('figure'), panel.get('quantity')]))
        if not missing and preferred is None:
            continue  # 无需分配新身份的已合法标签保留原协议。
        identity = preferred or identity
        if panel.get('panel') == identity:
            continue
        bindings.append({'program_panel_id': identity, 'model_original_label': panel.get('panel'),
            'region_id': region, 'bbox': deepcopy(matched[0]['bbox']),
            'source_sha256': geometry['source_sha256'], 'pdf_page': geometry['pdf_page']})
        panel['panel'] = identity
    return result, bindings


def remember(context, panels, region):
    """服务器将已见标签固定到唯一几何身份；后续缺键不改动已有记录身份。"""
    for panel in panels:
        if not isinstance(panel, dict) or not isinstance(panel.get('panel'), str):
            continue
        candidate = deepcopy(panel); label = candidate.pop('panel')
        try:
            _, bindings = bind({'name': 'digitize_image_elements', 'arguments': {
                'region_id': region, 'panel': candidate}}, {**context, 'preferred': {}})
        except ValueError:
            continue
        if bindings:
            key = json.dumps([bindings[0]['program_panel_id'], panel.get('figure'), panel.get('quantity')])
            context.setdefault('preferred', {}).setdefault(key, label)
