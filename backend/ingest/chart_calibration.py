"""#227：原图坐标/色标的确定性标定；精度是读图事实，不是物理测量误差。"""
from __future__ import annotations

import math
import numpy as np


class ChartReadingError(ValueError):
    pass


def axis_bounds(axis):
    """边界是图像位置；排序不改变刻度的物理值、方向或原始响应。"""
    bounds = axis.get('bounds')
    if bounds is None:
        positions = [tick['position'] for tick in axis['ticks']]
        if len(positions) < 2:
            raise ChartReadingError('坐标刻度不足，无法确定图像边界')
        bounds = [min(positions), max(positions)]
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
            or any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) for value in bounds)):
        raise ChartReadingError('坐标边界必须为两个有限的图像位置')
    low, high = sorted(bounds)
    if not 0 <= low < high <= 1000:
        raise ChartReadingError('坐标边界超出原图或宽度为零')
    return [low, high]


def align_value_ticks(image, axis, *, localization_error=1.0):
    """在实际轴线附近对齐刻度短线；没有唯一像素信号时保留原定位，不从科学值反推。"""
    from copy import deepcopy
    axis = {**axis, 'bounds': axis_bounds(axis)}
    rgb = np.asarray(image.convert('RGB'), dtype=float)
    height, width = rgb.shape[:2]
    bounds = axis['bounds']
    low, high = max(0, round(bounds[0] * (height - 1) / 1000)), min(height - 1, round(bounds[1] * (height - 1) / 1000))
    if high <= low: return axis, {'ticks_aligned': False}
    dark = (np.ptp(rgb, axis=2) < 8) & (np.mean(rgb, axis=2) < 128)
    continuity = dark[low:high + 1].sum(axis=0)
    spine = axis.get('spine_position')
    xs = np.arange(width)
    if spine is not None:
        radius = max(2, math.ceil(localization_error * width / 1000))
        xs = xs[np.abs(xs - spine * (width - 1) / 1000) <= radius]
    if not len(xs): return axis, {'ticks_aligned': False}
    best = continuity[xs].max()
    if best < (high - low) / 2: return axis, {'ticks_aligned': False}
    candidates = xs[continuity[xs] == best]; x = int(candidates[0])
    # 只取轴外窄条，避免柱顶/数据线冒充刻度短线。
    strip = dark[:, max(0, x - 6):max(0, x - 1)]
    if not strip.shape[1]: return axis, {'ticks_aligned': False}
    profile = strip.sum(axis=1)
    result = deepcopy(axis); changes = []
    radius = max(2, math.ceil(localization_error * height / 1000) + 1)
    for tick in result['ticks']:
        expected = tick['position'] * (height - 1) / 1000
        a, b = max(0, round(expected) - radius), min(height, round(expected) + radius + 1)
        levels = profile[a:b]
        if not len(levels) or levels.max() < 2 or levels.max() <= np.median(levels): continue
        rows = np.flatnonzero(levels == levels.max()) + a
        groups = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
        group = min(groups, key=lambda g: abs(float(np.mean(g)) - expected))
        position = float(np.mean(group)) * 1000 / (height - 1)
        if bounds[0] <= position <= bounds[1]:
            changes.append({'value': tick['value'], 'original_position': tick['position'], 'position': position})
            tick['position'] = position
    return result, {'ticks_aligned': bool(changes), 'axis_spine_pixel': x, 'tick_positions': changes}


def coordinate_value(axis, position, *, pixel_error=1.0):
    ticks = axis['ticks']
    if len(ticks) < 2 or axis['scale'] not in {'linear', 'log10'}:
        raise ChartReadingError('坐标刻度不足或不是可标定的线性/对数轴')
    x = np.asarray([tick['position'] for tick in ticks], dtype=float)
    y = np.asarray([tick['value'] for tick in ticks], dtype=float)
    if not np.isfinite([*x, *y, position, pixel_error]).all() or pixel_error <= 0:
        raise ChartReadingError('坐标与读图精度必须为有限数值')
    if np.any(x < 0) or np.any(x > 1000):
        raise ChartReadingError('刻度位置超出原图')
    order = np.argsort(x); x, y = x[order], y[order]
    if len(set(x)) != len(x) or not (np.all(np.diff(y) > 0) or np.all(np.diff(y) < 0)):
        raise ChartReadingError('坐标刻度重复或不单调，不能猜测轴变换')
    bounds = axis_bounds(axis)
    if not bounds[0] <= x[0] <= x[-1] <= bounds[1]:
        raise ChartReadingError('坐标刻度超出声明的图像边界')
    if not bounds[0] <= position <= bounds[1]:
        raise ChartReadingError('数据位置超出已标定坐标，未外推')
    logarithmic = axis['scale'] == 'log10'
    if logarithmic and np.any(y <= 0):
        raise ChartReadingError('对数刻度必须为正值')
    transformed = np.log10(y) if logarithmic else y
    slope, intercept = np.polyfit(x, transformed, 1)
    residual = float(np.max(np.abs(slope * x + intercept - transformed)))
    middle = float(slope * position + intercept)
    spread = abs(float(slope)) * pixel_error + residual
    convert = (lambda v: 10.0 ** v) if logarithmic else (lambda v: v)
    value = convert(middle)
    precision = max(abs(value - convert(middle - spread)), abs(convert(middle + spread) - value))
    if not math.isfinite(value) or not math.isfinite(precision) or precision <= 0:
        raise ChartReadingError('坐标标定未得到有限读数与精度')
    return value, precision, {'slope': float(slope), 'intercept': float(intercept),
                              'residual': residual, 'scale': axis['scale']}


def bar_edge(image, point, axis):
    """模型定位柱与系列，程序从柱内部像素跟踪到真实边缘，不用正文值定高度。"""
    rgb = np.asarray(image.convert('RGB'), dtype=float)
    height, width = rgb.shape[:2]
    ticks = axis['ticks']
    if not ticks: raise ChartReadingError('柱状图缺少标定轴')
    bounds = axis_bounds(axis)
    low = max(0, int(math.floor(bounds[0] * (height - 1) / 1000)))
    high = min(height - 1, int(math.ceil(bounds[1] * (height - 1) / 1000)))
    area = rgb[low:high + 1].reshape(-1, 3)
    quantized = (area // 8).astype(int)
    codes = quantized[:, 0] * 1024 + quantized[:, 1] * 32 + quantized[:, 2]
    background = np.median(area[codes == np.bincount(codes, minlength=32768).argmax()], axis=0)
    baseline = min(ticks, key=lambda t: abs(t['value']))['position']
    x = int(round(point['x'] * (width - 1) / 1000))
    probe = int(round((point['y'] + baseline) / 2 * (height - 1) / 1000))
    if not 1 <= x < width - 1 or not 1 <= probe < height - 1:
        raise ChartReadingError('柱内部位置超出原图')
    patch = rgb[max(0, probe - 3):probe + 4, x - 1:x + 2].reshape(-1, 3)
    chroma = np.ptp(patch, axis=1)
    if chroma.max() > 2 * math.sqrt(3):
        interior = patch[chroma >= chroma.max() - 2 * math.sqrt(3)]
    else:
        interior = patch[np.linalg.norm(patch - 255, axis=1) > 2 * math.sqrt(3)]
    if not len(interior): raise ChartReadingError('柱内部只有背景，未猜测零值或柱高')
    color = np.median(interior, axis=0)
    if np.linalg.norm(color - background) <= 2 * math.sqrt(3):
        raise ChartReadingError('柱内部只有背景，未猜测零值或柱高')
    tolerance = max(2 * math.sqrt(3), 3 * float(np.median(np.linalg.norm(interior - color, axis=1))))
    column = np.median(rgb[:, x - 1:x + 2], axis=1)
    mask = np.linalg.norm(column - color, axis=1) <= tolerance
    gap_limit = max(2, math.ceil(point.get('pixel_error', 0) * height / 1000) + 2)
    def ink(value):
        if np.linalg.norm(value - background) <= 2 * math.sqrt(3): return False
        centered = color - np.mean(color); shade = value - np.mean(value)
        denominator = float(np.dot(centered, centered))
        if denominator <= tolerance ** 2: return float(np.ptp(value)) <= tolerance
        alpha = float(np.dot(shade, centered)) / denominator
        return 0 <= alpha <= 1 and np.linalg.norm(shade - alpha * centered) <= tolerance
    if not mask[probe]:
        candidates = [y for y in range(max(low, probe - 3), min(high, probe + 3) + 1) if mask[y]]
        if not candidates: raise ChartReadingError('无法识别柱内部的稳定像素')
        probe = min(candidates, key=lambda y: abs(y - probe))
    def end(direction):
        position = probe
        while low <= position + direction <= high:
            next_position = position + direction
            if mask[next_position]:
                position = next_position; continue
            gap = []
            while (low <= next_position <= high and not mask[next_position] and ink(column[next_position])
                   and (np.ptp(column[next_position]) > tolerance or len(gap) < gap_limit)):
                gap.append(next_position); next_position += direction
            if low <= next_position <= high and mask[next_position] and all(ink(column[y]) for y in gap):
                position = next_position; continue
            break
        return position
    a, b = end(-1), end(1)
    initial = point['y'] * (height - 1) / 1000
    inner = min((a, b), key=lambda y: abs(y - initial)); outer = inner
    direction = -1 if inner == a else 1
    while (low <= outer + direction <= high and ink(column[outer + direction])
           and (np.ptp(column[outer + direction]) > tolerance or abs(outer - inner) < gap_limit)):
        outer += direction
    if abs(outer - inner) > b - a + 1:
        raise ChartReadingError('柱边界与贯穿线无法区分')
    edge = (inner + outer) / 2
    edge_error = (abs(outer - inner) / 2 + 1) * 1000 / (height - 1)
    return edge * 1000 / (height - 1), {'bar_rgb': color.tolist(), 'background_rgb': background.tolist(), 'bar_pixel_span': [a, b],
        'bar_edge_error': edge_error, 'bar_edge_interval': [inner, outer],
        'initial_model_y': point['y'], 'snapped_y': edge * 1000 / (height - 1)}


def approximate(value, precision):
    """按可解释分辨率舍入，原始计算值仍由调用方保留。"""
    if not math.isfinite(value) or not math.isfinite(precision) or precision <= 0:
        raise ChartReadingError('估读缺少有效精度')
    quantum = 10.0 ** math.floor(math.log10(precision))
    rounded = round(value / quantum) * quantum
    bound = math.ceil((precision + abs(rounded - value)) / quantum) * quantum
    return float(f'{rounded:.12g}'), float(f'{bound:.12g}')


def heatmap_position(image, point, colorbar):
    """从真实像素反查色标位置；颜色多解、未出现在色标上的颜色不伪造读数。"""
    width, height = image.size
    x0, y0, x1, y1 = colorbar['bbox']
    if not (0 <= x0 < x1 <= 1000 and 0 <= y0 < y1 <= 1000):
        raise ChartReadingError('色标框超出原图')
    px, py = [int(round(v * size / 1000)) for v, size in zip(point, (width - 1, height - 1))]
    if not (0 <= px < width and 0 <= py < height):
        raise ChartReadingError('热力格位置超出原图')
    rgb = np.asarray(image.convert('RGB'), dtype=float)
    if colorbar['orientation'] == 'vertical':
        sample = rgb[max(0, round(y0 * height / 1000)):min(height, round(y1 * height / 1000)),
                     min(width - 1, round((x0 + x1) / 2 * width / 1000))]
        positions = np.arange(len(sample)) * 1000 / height + y0
    elif colorbar['orientation'] == 'horizontal':
        sample = rgb[min(height - 1, round((y0 + y1) / 2 * height / 1000)),
                     max(0, round(x0 * width / 1000)):min(width, round(x1 * width / 1000))]
        positions = np.arange(len(sample)) * 1000 / width + x0
    else:
        raise ChartReadingError('色标方向无效')
    if len(sample) < 2:
        raise ChartReadingError('色标没有足够像素')
    distances = np.linalg.norm(sample - rgb[py, px], axis=1)
    closest = float(distances.min())
    palette_step = float(np.max(np.linalg.norm(np.diff(sample, axis=0), axis=1)))
    if closest > palette_step + 2 * math.sqrt(3):
        raise ChartReadingError('格点颜色不能由原色标解释')
    matches = np.flatnonzero(distances <= closest + math.sqrt(3))
    if np.any(np.diff(matches) > 2):
        raise ChartReadingError('同一颜色对应不连续的多个色标位置')
    selected = positions[matches]
    position = float((selected[0] + selected[-1]) / 2)
    error = max(float((selected[-1] - selected[0]) / 2), 1000 / max(width, height))
    return position, error, {'pixel_rgb': rgb[py, px].tolist(), 'color_distance': closest,
                             'colorbar_position_range': [float(selected[0]), float(selected[-1])]}
