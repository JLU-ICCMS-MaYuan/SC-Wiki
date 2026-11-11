"""#227：原图坐标/色标的确定性标定；精度是读图事实，不是物理测量误差。"""
from __future__ import annotations

import math
import numpy as np


class ChartReadingError(ValueError):
    def __init__(self,message,details=None):
        super().__init__(message)
        self.details=details or {}


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


def align_value_ticks(image, axis, *, localization_error=1.0, verify_label_positions=False):
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
    # 同一粗轴线的抗锯齿边缘可能少几个像素；先定位完整轴宽，再观察两侧短线。
    # 刻度可朝内或朝外，不能只在轴外找。窄条不进入远处的数据柱。
    left, right = x, x
    while left > 0 and continuity[left - 1] >= best * .99: left -= 1
    while right + 1 < width and continuity[right + 1] >= best * .99: right += 1
    strip = np.concatenate((dark[:, max(0, left - 6):max(0, left - 1)],
                            dark[:, min(width, right + 2):min(width, right + 7)]), axis=1)
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
    facts = {'ticks_aligned': bool(changes), 'axis_spine_pixel': x, 'tick_positions': changes}
    if verify_label_positions:
        from .image_geometry import axis_text_regions
        regions = axis_text_regions(image,x,bounds)
        facts['axis_text_regions'] = regions
        for tick in result['ticks']:
            matches=[box for box in regions if box[1]-localization_error<=tick['position']<=box[3]+localization_error]
            if len(matches)!=1:continue
            box=matches[0]
            a=max(0,math.floor(box[1]*(height-1)/1000));b=min(height,math.ceil(box[3]*(height-1)/1000)+1)
            levels=profile[a:b]
            if not len(levels)or levels.max()<2 or levels.max()<=np.median(levels):continue
            rows=np.flatnonzero(levels==levels.max())+a
            groups=np.split(rows,np.flatnonzero(np.diff(rows)>1)+1)
            if len(groups)!=1:continue  # 文字附近多条刻度时不猜配对。
            position=float(np.mean(groups[0]))*1000/(height-1)
            if bounds[0]<=position<=bounds[1]:
                changes.append({'value':tick['value'],'original_position':tick['position'],'position':position,
                                'method':'unique_tick_within_printed_text_row'})
                tick['position']=position
        facts['ticks_aligned']=bool(changes)
        supported = [any(box[1]-localization_error <= tick['position'] <= box[3]+localization_error
                         for box in regions) for tick in result['ticks']]
        # 只在原图确有多行相邻轴外文字且至少一条声明刻度与文字对应时检出错配。
        # 此处不识字、不赋数字值；不能把无字短刻度声明成原文的数值标签。
        if len(regions)>=2 and any(supported) and not all(supported):
            unsupported = [round(tick['position']*(height-1)/1000)
                           for tick,ok in zip(result['ticks'],supported) if not ok]
            detail = {'reason_code':'TICK_LABEL_POSITION_UNSUPPORTED','axis_text_regions':regions,
                'unsupported_tick_rows':unsupported,
                'suggested_crop_bbox_normalized':[0,max(0,bounds[0]-2*localization_error),
                    min(1000,(x+max(2,math.ceil(localization_error*width/1000)))*1000/(width-1)),
                    min(1000,bounds[1]+2*localization_error)]}
            raise ChartReadingError('所声明刻度没有对应的印刷文字行，可能把无字短刻度当成数字标签；'
                f'未对应的原图像素行{unsupported}，请精读实际轴外文字，不删除标签来猜标定。',detail)
    return result, facts


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
        raise ChartReadingError('坐标刻度超出声明的图像边界', {
            'reason_code': 'TICK_OUTSIDE_AXIS_BOUNDS', 'axis_bounds': bounds,
            'outside_ticks': [dict(tick) for tick in ticks
                              if not bounds[0] <= tick['position'] <= bounds[1]],
            'correction': '对照当前原图核对这几条刻度位置及轴边界；保持实际标签数值，不能删除刻度或从目标数据反推。'})
    if not bounds[0] <= position <= bounds[1]:
        raise ChartReadingError('数据位置超出已标定坐标，未外推')
    logarithmic = axis['scale'] == 'log10'
    if logarithmic and np.any(y <= 0):
        raise ChartReadingError('对数刻度必须为正值')
    transformed = np.log10(y) if logarithmic else y
    # 各刻度的真实位置须能落在同一条仿射轴的定位带内。反向写成x=a*y+b，
    # 每对刻度给a一个区间；所有区间相交等价于存在共同截距的定位带。
    # 不能用错误刻度本身造成的拟合残差无限放大精度；两点仍不独立证明标签正确。
    direction = 1 if transformed[-1] > transformed[0] else -1
    increasing = direction * transformed
    minimum, maximum = 0.0, math.inf
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            dy, dx = float(increasing[j] - increasing[i]), float(x[j] - x[i])
            if not math.isfinite(dy) or dy <= 0:
                raise ChartReadingError('坐标刻度的物理范围无效')
            minimum = max(minimum, (dx - 2 * pixel_error) / dy)
            maximum = min(maximum, (dx + 2 * pixel_error) / dy)
    if minimum > np.nextafter(maximum, math.inf):
        raise ChartReadingError('所读刻度不能在当前定位精度内共用同一条轴；请补读实际印刷标签，不能用拟合残差放大误差或删除刻度。', {
            'reason_code': 'TICK_CALIBRATION_INCONSISTENT', 'ticks': [dict(tick) for tick in ticks],
            'localization_error': pixel_error,
            'correction': '在同一原图核对刻度数字、位置及线性/对数类型；保留未解决项，不从目标数据反推。'})
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


def verify_horizontal_tick_labels(image, axis, *, localization_error=1.0, panel_bounds=None, point=None):
    """用原像素核实横轴声明位置有印刷文字；不识字、不分配刻度值。"""
    from .image_geometry import horizontal_axis_text_regions, closed_plot_frames
    bounds = axis_bounds(axis)
    rgb = np.asarray(image.convert('RGB'), dtype=float)
    height, width = rgb.shape[:2]
    owner = None
    if panel_bounds and point:
        low_y,high_y=sorted(panel_bounds)
        owners=[frame['bbox'] for frame in closed_plot_frames(image)
            if frame['bbox'][1]<=(low_y+high_y)/2<=frame['bbox'][3]
            and frame['bbox'][0]-localization_error<=point['x']<=frame['bbox'][2]+localization_error]
        if len(owners)==1:
            owner=owners[0];bounds=[owner[0],owner[2]]
    left, right = max(0, round(bounds[0]*(width-1)/1000)), min(width-1, round(bounds[1]*(width-1)/1000))
    if right <= left: return {'checked': False}
    dark = np.mean(rgb, axis=2) < 128
    profile = dark[:, left:right+1].sum(axis=1)
    rows = np.flatnonzero(profile > (right-left)/2)
    if not len(rows): return {'checked': False}
    groups = np.split(rows, np.flatnonzero(np.diff(rows) > 1)+1)
    candidates = [];rows_with_text=[];panel_annotations=[]
    for group in groups:
        spine = round(float(np.mean(group)))
        regions = horizontal_axis_text_regions(image, spine, bounds)
        # 堆叠图下一幅的标题/曲线位于持续向下的双侧图框内，不是本幅轴外刻度。
        # 只判断墨迹几何，不识字或替模型分配数值；真正的轴外数字仍走原位置检查。
        band=dark[max(0,int(group[0])-2):min(height,int(group[-1])+3),left:right+1]
        xs=np.flatnonzero(np.any(band,axis=0))+left
        runs=np.split(xs,np.flatnonzero(np.diff(xs)>1)+1) if len(xs) else []
        span=max(runs,key=len) if runs else []
        margin=max(2,math.ceil(localization_error*width/1000))
        filtered=[]
        for box in regions:
            center=round((box[1]+box[3])/2*(height-1)/1000)
            inside=False
            if len(span) and center>spine+8:
                continuity=[]
                for start,end in ((int(span[0])-2,int(span[0])+3*margin+3),
                                  (int(span[-1])-3*margin-2,int(span[-1])+3)):
                    strip=dark[spine+6:center+1,max(0,start):min(width,end)]
                    continuity.append(bool(strip.size and float(np.max(np.mean(strip,axis=0)))>.8))
                inside=all(continuity)
            if inside:panel_annotations.append({'spine_pixel':spine,'bbox':box,'role':'inside_following_plot_not_axis_labels'})
            else:filtered.append(box)
        regions=filtered
        supported = [any(box[0]-localization_error <= tick['position'] <= box[2]+localization_error
                         for box in regions) for tick in axis['ticks']]
        entry=(len(regions),sum(supported),spine,regions,supported)
        candidates.append(entry)
        if len(regions)>=2:rows_with_text.append(entry)
    if not rows_with_text:
        if panel_annotations:
            raise ChartReadingError('当前可见文字位于下一绘图区内部，未找到可归属的轴外刻度。',
                {'reason_code':'HORIZONTAL_AXIS_SCOPE_AMBIGUOUS','panel_annotations':panel_annotations})
        return {'checked':False}
    chosen=None
    if panel_bounds:
        expected=max(panel_bounds)*(height-1)/1000
        own=min(candidates,key=lambda item:abs(item[2]-expected))
        if own[0]>=2:chosen=own
    if chosen is None:
        # 对齐的复合图可共用唯一印刷轴；多套标签不能按“更匹配”从别的材料借用。
        unique={tuple(tuple(box)for box in item[3]):item for item in rows_with_text}
        if len(unique)==1:chosen=next(iter(unique.values()))
        else:
            raise ChartReadingError('当前面板横轴归属尚未唯一定位，不能借用其他面板的多套刻度。',{
                'reason_code':'HORIZONTAL_AXIS_SCOPE_AMBIGUOUS','panel_bounds':panel_bounds})
    _, _, spine, regions, supported = chosen
    original_boxes = regions
    facts = {'checked': True, 'horizontal_spine_pixel': spine, 'axis_text_regions': original_boxes,
             'panel_bounds':panel_bounds,'owner_frame':owner,'excluded_panel_annotations':panel_annotations}
    if not all(supported):
        raise ChartReadingError('横轴声明的刻度位置没有对应印刷文字；请在当前原图补读数字和位置，不能把数学上自洽的坐标当成已看见的标签。', {
            'reason_code': 'HORIZONTAL_TICK_LABEL_POSITION_UNSUPPORTED', **facts,
            'unsupported_ticks': [dict(tick) for tick, ok in zip(axis['ticks'], supported) if not ok],
            'suggested_crop_bbox_normalized': [max(0,bounds[0]-2*localization_error),
                max(0,spine*1000/(height-1)-2*localization_error), min(1000,bounds[1]+2*localization_error),
                min(1000,max(box[3] for box in original_boxes)+2*localization_error)]})
    return facts


def align_horizontal_ticks(image, axis, *, localization_error, panel_bounds=None, point=None):
    """将已读数字所属的唯一原像素短刻度作为技术位置，不更改数字。"""
    from copy import deepcopy
    facts=verify_horizontal_tick_labels(image,axis,localization_error=localization_error,
        panel_bounds=panel_bounds,point=point)
    if not facts.get('checked'):return deepcopy(axis),facts
    from .image_geometry import horizontal_tick_anchors
    candidates=horizontal_tick_anchors(image,facts['horizontal_spine_pixel'],facts['axis_text_regions'])
    anchored=[];anchors=[]
    for tick in axis['ticks']:
        boxes=[b for b in facts['axis_text_regions'] if b[0]-localization_error<=tick['position']<=b[2]+localization_error]
        if len(boxes)!=1:return deepcopy(axis),{**facts,'tick_alignment':'not_unique_label'}
        box=boxes[0];anchor=next(c for c in candidates if c['label_bbox']==box)
        if not anchor['unique']:return deepcopy(axis),{**facts,'tick_alignment':'not_unique_visible_tick'}
        position=anchor['position']
        anchored.append({'position':position,'value':tick['value']})
        anchors.append({'label_bbox':box,'tick_pixels':anchor['tick_pixels'],
            'raw_position':tick['position'],'position':position})
    if len({t['position'] for t in anchored})!=len(anchored):
        raise ChartReadingError('多个数字指向同一刻度，未猜测对应关系')
    result=deepcopy(axis);result['ticks']=anchored
    return result,{**facts,'tick_alignment':'unique_original_tick_pixels','raw_axis':deepcopy(axis),'anchors':anchors}


def verify_line_point_support(image, point, frame, *, localization_error):
    """图框本身不证明曲线数据点；只验证附近有非图框像素，不替AI判科学含义。"""
    height,width=image.height,image.width
    if not any(abs(point['x']-x)<=localization_error for x in (frame[0],frame[2])) and not any(
            abs(point['y']-y)<=localization_error for y in (frame[1],frame[3])):
        return {'checked':False}
    rgb=np.asarray(image.convert('RGB'));ink=rgb.mean(axis=2)<128
    left,top,right,bottom=[round(v*(width-1 if i%2==0 else height-1)/1000)for i,v in enumerate(frame)]
    interior=ink.copy()
    interior[:top]=False;interior[bottom+1:]=False;interior[:,:left]=False;interior[:,right+1:]=False
    def remove_spine(profile,center,radius,vertical):
        start,end=max(0,center-radius),min(len(profile),center+radius+1)
        index=start+int(np.argmax(profile[start:end]));strength=profile[index]
        if strength<=0:return
        a,b=index,index
        while a>0 and profile[a-1]>=strength*.9:a-=1
        while b+1<len(profile) and profile[b+1]>=strength*.9:b+=1
        if vertical:interior[:,max(0,a-1):b+2]=False
        else:interior[max(0,a-1):b+2]=False
    dx=max(3,math.ceil(localization_error*width/1000));dy=max(3,math.ceil(localization_error*height/1000))
    columns=ink[top:bottom+1].sum(axis=0);rows=ink[:,left:right+1].sum(axis=1)
    for x in (left,right):remove_spine(columns,x,dx,True)
    for y in (top,bottom):remove_spine(rows,y,dy,False)
    x,y=round(point['x']*(width-1)/1000),round(point['y']*(height-1)/1000)
    if interior[max(0,y-dy):y+dy+1,max(0,x-dx):x+dx+1].any():
        return {'checked':True,'supported':True,'role':'non_frame_pixel_support_only'}
    from scipy.ndimage import label,find_objects
    candidates=[]
    for channel in range(3):
        other=np.max(np.delete(rgb.astype(float),channel,axis=2),axis=2)
        mask=interior & (rgb[:,:,channel].astype(float)>other+30)
        components,_=label(mask,structure=np.ones((3,3)))
        for number,box in enumerate(find_objects(components),1):
            if box is None:continue
            yy,xx=np.nonzero(components[box]==number)
            if len(xx)<4:continue
            xx=xx+box[1].start;yy=yy+box[0].start
            at_top=yy==yy.min()
            candidates.append({'dominant_channel':channel,'pixel_count':len(xx),
                'top_ink':[float(np.mean(xx[at_top]))*1000/(width-1),float(yy.min())*1000/(height-1)],
                'bbox':[float(xx.min())*1000/(width-1),float(yy.min())*1000/(height-1),
                        float(xx.max())*1000/(width-1),float(yy.max())*1000/(height-1)]})
    raise ChartReadingError('声明的曲线点只有图框墨迹支持，附近未见非图框数据；请选择实际曲线，不能用图框端点代替饱和终点。',{
        'reason_code':'LINE_POINT_ONLY_FRAME_INK','point':dict(point),'frame_bbox':frame,
        'stroke_geometry_candidates':sorted(candidates,key=lambda c:c['pixel_count'],reverse=True),
        'geometry_role':'unlabelled_pixel_candidates_not_scientific_values'})


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
    if not len(interior):
        raise ChartReadingError('柱内部只有背景，未猜测零值或柱高',
                                {'reason_code':'BAR_INTERIOR_UNREADABLE'})
    color = np.median(interior, axis=0)
    if np.linalg.norm(color - background) <= 2 * math.sqrt(3):
        raise ChartReadingError('柱内部只有背景，未猜测零值或柱高',
                                {'reason_code':'BAR_INTERIOR_UNREADABLE'})
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
        # 原图压缩/网格叠加可使同色像素比内部采样更亮，alpha并不以1为上界。
        # 仍按色相残差检查；白色背景及不同色相不能借此连接。
        return 0 <= alpha and np.linalg.norm(shade - alpha * centered) <= tolerance
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
    edge_resolution = 2 * max(point.get('pixel_error', 0), 1000 / (height - 1))
    if np.ptp(color)<=tolerance and (b-a)*1000/(height-1)<=edge_resolution:
        raise ChartReadingError('柱基线附近仅有黑灰图框/刻度宽度的像素，没有可分辨的独立柱高，未填零值',
                                {'reason_code':'BAR_HEIGHT_BELOW_IMAGE_RESOLUTION'})
    zero = next((tick for tick in ticks if tick['value'] == 0), None)
    if zero is not None:
        endpoints = [value * 1000 / (height - 1) for value in (a, b)]
        # 现有算法按零基线取柱；零线穿过连续填色内部时不能据此标定柱高。
        # 轴线会遮住柱末端，不能要求填色必须精确触及零刻度中心。
        other = next((tick for tick in ticks if tick['value'] != 0 and tick['position'] != zero['position']), None)
        positive_direction = (1 if other['value'] / (other['position'] - zero['position']) > 0 else -1) if other else 0
        baseline_end = endpoints[0] if positive_direction > 0 else endpoints[1]
        if positive_direction * (zero['position'] - baseline_end) > edge_resolution:
            raise ChartReadingError(f"柱基线与声明零刻度不一致：柱端位置{endpoints[0]:.3f}/{endpoints[1]:.3f}，"
                f"零刻度位置{zero['position']:.3f}（均为当前图0—1000坐标）；请核对原刻度或柱类型，未改轴或猜值")
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
