"""原图的无标签几何观察；不识别材料、物理量、单位或科学数值。"""
from __future__ import annotations

import hashlib
import numpy as np
from PIL import Image
from scipy.ndimage import binary_closing, binary_opening, label, find_objects

VERSION = 'image-geometry-v2'


def axis_text_regions(image, spine_pixel, bounds):
    """只定位轴外文字像素行，不识别字符、数字值、单位或科学含义。"""
    rgb=np.asarray(image.convert('RGB'))
    height,width=rgb.shape[:2]
    left=rgb[:,:max(0,spine_pixel-6)]
    if not left.size:return []
    dark=(np.ptp(left.astype(float),axis=2)<8)&(left.mean(axis=2)<128)
    components,_=label(dark,structure=np.ones((3,3)))
    low,high=[v*(height-1)/1000 for v in sorted(bounds)]
    # 端点标签中心可能略在框外；只有原像素确有横向图框边线时承认跨界文字。
    # 没有边线的相邻面板文字仍不能借到当前轴上。
    frame_boundaries=[]
    for boundary in (low,high):
        strip=rgb[max(0,round(boundary)-1):min(height,round(boundary)+2),spine_pixel:]
        if strip.size:
            ink=(np.ptp(strip.astype(float),axis=2)<8)&(strip.mean(axis=2)<128)
            if np.any(ink.mean(axis=1)>.5):frame_boundaries.append(boundary)
    glyphs=[]
    for box in find_objects(components):
        if box is None:continue
        y,x=box;h,w=y.stop-y.start,x.stop-x.start
        if y.start>high or y.stop<low or h<3 or h>(high-low)/2 or w>2*h:continue
        glyphs.append((x.start,y.start,x.stop,y.stop))
    if not glyphs:return []
    text_height=float(np.percentile([b[3]-b[1]for b in glyphs],90))
    glyphs=[b for b in glyphs if b[3]-b[1]>=text_height/2]
    right=max(b[2]for b in glyphs)
    column=[b for b in glyphs if right-b[2]<=text_height]
    rows=[]
    for box in sorted(column,key=lambda b:b[1]):
        if rows and box[1]<=rows[-1][3]+1:
            old=rows[-1];rows[-1]=(min(old[0],box[0]),min(old[1],box[1]),max(old[2],box[2]),max(old[3],box[3]))
        else:rows.append(box)
    return [[x0*1000/(width-1),y0*1000/(height-1),x1*1000/(width-1),y1*1000/(height-1)]
            for x0,y0,x1,y1 in rows if low<=(y0+y1)/2<=high
            or any(y0<=boundary<=y1 for boundary in frame_boundaries)]


def horizontal_axis_text_regions(image, spine_pixel, bounds):
    """横轴外的同一行文字像素，按字高合并邻接字形；不OCR或分配科学值。"""
    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    top = min(height, spine_pixel+6)
    below = rgb[top:]
    if not below.size: return []
    dark = below.mean(axis=2)<128
    components, _ = label(dark, structure=np.ones((3,3)))
    low, high = [value*(width-1)/1000 for value in sorted(bounds)]
    glyphs = []
    for box in find_objects(components):
        if box is None: continue
        y, x = box; h, w = y.stop-y.start, x.stop-x.start
        if h<3 or h>(height-top)/2 or w>(high-low)/2 or x.stop<low-100 or x.start>high+100: continue
        glyphs.append((x.start,y.start+top,x.stop,y.stop+top))
    if not glyphs: return []
    text_height = float(np.percentile([box[3]-box[1] for box in glyphs],90))
    letters = [box for box in glyphs if box[3]-box[1]>=text_height/2]
    if not letters: return []
    row_top = min(box[1] for box in letters)
    # 确定数字行后保留该行的小点/负号，不因窄“1”或两位数间隙误拒绝真实刻度。
    row = [box for box in glyphs if row_top <= (box[1]+box[3])/2 <= row_top+text_height
           and box[2]>=low-text_height and box[0]<=high+text_height]
    words = []
    for box in sorted(row):
        if words and box[0]-words[-1][2]<=text_height/2:
            old=words[-1];words[-1]=(old[0],min(old[1],box[1]),max(old[2],box[2]),max(old[3],box[3]))
        else: words.append(box)
    return [[x0*1000/(width-1),y0*1000/(height-1),x1*1000/(width-1),y1*1000/(height-1)]
            for x0,y0,x1,y1 in words if x1>=low and x0<=high]


def closed_plot_frames(image):
    """闭合墨迹图框的几何候选，包含窄列和有色轴；不识别其科学用途。"""
    rgb=np.asarray(image.convert('RGB'));height,width=rgb.shape[:2]
    ink=rgb.mean(axis=2)<180
    minimum=max(4,min(width,height)//25)
    def segments(structure):
        components,_=label(binary_opening(ink,structure=structure),structure=np.ones((3,3)))
        return [(box[1].start,box[0].start,box[1].stop-1,box[0].stop-1)
                for box in find_objects(components) if box is not None]
    horizontal=segments(np.ones((1,minimum)));vertical=segments(np.ones((minimum,1)))
    boxes=[]
    for first in vertical:
        for second in vertical:
            left=(first[0]+first[2])/2;right=(second[0]+second[2])/2
            if right-left<minimum:continue
            top=max(first[1],second[1]);bottom=min(first[3],second[3])
            if bottom-top<minimum:continue
            tolerance=max(2,first[2]-first[0]+1,second[2]-second[0]+1)
            upper=[row for row in horizontal if abs((row[1]+row[3])/2-top)<=tolerance
                   and row[0]<=left+tolerance and row[2]>=right-tolerance]
            lower=[row for row in horizontal if abs((row[1]+row[3])/2-bottom)<=tolerance
                   and row[0]<=left+tolerance and row[2]>=right-tolerance]
            if upper and lower:
                box=[left,min((r[1]+r[3])/2 for r in upper),right,max((r[1]+r[3])/2 for r in lower)]
                if box not in boxes:boxes.append(box)
    # 图内竖网格也形成小矩形；有同上下边的完整外框时不把网格单元冒充面板。
    boxes=[box for box in boxes if not any(other!=box and other[0]<=box[0] and other[2]>=box[2]
        and abs(other[1]-box[1])<=2 and abs(other[3]-box[3])<=2 for other in boxes)]
    return [{'bbox':[x0*1000/(width-1),y0*1000/(height-1),x1*1000/(width-1),y1*1000/(height-1)],
             'source':'closed_ink_frame'}for x0,y0,x1,y1 in boxes]


def horizontal_tick_anchors(image, spine_pixel, boxes):
    """原像素中数字文字框对应的唯一竖短线位置；不识别或返回任何刻度数字。"""
    import math
    rgb=np.asarray(image.convert('RGB'));height,width=rgb.shape[:2];dark=rgb.mean(axis=2)<128
    result=[]
    for box in boxes:
        left=max(0,math.floor(box[0]*(width-1)/1000));right=min(width-1,math.ceil(box[2]*(width-1)/1000))
        bottom=min(height,math.floor(box[1]*(height-1)/1000)-2)
        groups=[]
        if bottom>spine_pixel+4:
            counts=dark[spine_pixel+2:bottom,left:right+1].sum(axis=0)
            columns=np.flatnonzero(counts>=3)+left
            groups=np.split(columns,np.flatnonzero(np.diff(columns)>1)+1) if len(columns) else []
            groups=[g for g in groups if int(np.max(counts[g-left]))>=len(g)]
        result.append({'label_bbox':box,'unique':len(groups)==1,
            **({'position':float(np.mean(groups[0]))*1000/(width-1),
                'tick_pixels':[int(groups[0][0]),int(groups[0][-1])]} if len(groups)==1 else {})})
    return result


def geometry_observations(image):
    original_size = image.size
    view = image.convert('RGB').copy()
    view.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
    rgb = np.asarray(view)
    height, width = rgb.shape[:2]
    result = {'version': VERSION, 'role': 'unlabelled_geometry_candidates_not_scientific_results',
        'coordinate_space': 'current_image_normalized_0_1000', 'image_size': list(original_size),
        'analysis_image_size': [width, height], 'localization_resolution': max(1000/max(1,width-1),1000/max(1,height-1)),
        'pixel_sha256': hashlib.sha256(rgb.tobytes()).hexdigest(),
        'horizontal_frames': [], 'band_candidates': [], 'spines': [], 'rectangles': [],
        'limitations': ['色块观察只提供彩色近矩形候选，图例也可能在列；缺少候选不代表没有数据。']}
    if width < 3 or height < 3:
        return result
    result['panel_frames']=closed_plot_frames(view)
    def norm_box(x0,y0,x1,y1):
        return [round(x0*1000/(width-1),3),round(y0*1000/(height-1),3),
                round((x1-1)*1000/(width-1),3),round((y1-1)*1000/(height-1),3)]
    chroma=np.ptp(rgb.astype(np.float32),axis=2)
    dark=(chroma<30)&(rgb.mean(axis=2)<100)
    lines=[]
    for y in range(height):
        xs=np.flatnonzero(dark[y])
        if not len(xs):continue
        groups=np.split(xs,np.flatnonzero(np.diff(xs)>1)+1)
        span=max(groups,key=len)
        if len(span)<width*.5:continue
        if lines and y-lines[-1][-1][2]<=1:
            lines[-1].append((int(span[0]),int(span[-1]),y))
        else:lines.append([(int(span[0]),int(span[-1]),y)])
    frames=[(int(np.median([r[0] for r in line])),int(np.median([r[1] for r in line])),float(np.mean([r[2] for r in line]))) for line in lines]
    result['horizontal_frames']=[{'x0':x0*1000/(width-1),'x1':x1*1000/(width-1),'y':y*1000/(height-1)} for x0,x1,y in frames]
    result['horizontal_axis_text_regions'] = []
    label_frames=[*frames,*[(box['bbox'][0]*(width-1)/1000,box['bbox'][2]*(width-1)/1000,
        box['bbox'][edge]*(height-1)/1000) for box in result['panel_frames'] for edge in (1,3)]]
    for x0, x1, y in label_frames:
        bounds = [x0*1000/(width-1), x1*1000/(width-1)]
        regions = horizontal_axis_text_regions(view, round(y), bounds)
        if len(regions) >= 2:
            result['horizontal_axis_text_regions'].append({'frame_y': y*1000/(height-1),
                'bounds': bounds, 'regions': regions,
                'label_tick_anchors':horizontal_tick_anchors(view,round(y),regions),
                'role': 'printed_text_geometry_only_not_tick_values'})
    for first,second in zip(frames,frames[1:]):
        if (abs(first[0]-second[0])<=width*.025 and abs(first[1]-second[1])<=width*.025
                and second[2]-first[2]>=max(8,height*.025)):
            result['band_candidates'].append({'bbox':norm_box(0,first[2],width,second[2]+1),
                'basis':'相邻长水平线的跨度一致；是否为独立面板仍须看图判断'})
    if len(frames)>=2:
        guess=max(row[0] for row in frames)
        radius=max(3,round(width*.015));lo=max(0,guess-radius);hi=min(width,guess+radius+1)
        top,bottom=round(frames[0][2]),round(frames[-1][2])
        counts=dark[top:bottom+1,lo:hi].sum(axis=0)
        x=int(np.median(np.flatnonzero(counts==counts.max())))+lo
        strip=dark[:,max(0,x-max(5,round(width*.014))):max(0,x-max(2,round(width*.002)))]
        if strip.shape[1] and counts.max() >= max(1,bottom-top)*.5:
            ys=np.flatnonzero(strip.mean(axis=1)>.3)
            groups=np.split(ys,np.flatnonzero(np.diff(ys)>1)+1) if len(ys) else []
            result['spines']=[{'x':x*1000/(width-1),'tick_candidates':[
                {'y':float(np.mean(group))*1000/(height-1)} for group in groups if len(group)]}]
    # 色相而非亮度分组，保留原像素的明暗差异；只跨越短暗线，不填白色缺口。
    delta=rgb.astype(np.float32)-rgb.min(axis=2)[...,None]
    hue=np.rint(delta/np.maximum(chroma[...,None],1)*4).astype(np.uint8)
    codes=hue[...,0]*25+hue[...,1]*5+hue[...,2]
    coloured=chroma>35
    histogram=np.bincount(codes[coloured].ravel(),minlength=125)
    for code in np.flatnonzero(histogram>=max(8,width*height*.00003)):
        mask=coloured&(codes==code)
        closed=binary_closing(mask,structure=np.ones((max(3,round(height*.004)),1)))
        components,count=label(mask|(closed&dark),structure=np.ones((3,3)))
        for index,box in enumerate(find_objects(components),1):
            if box is None:continue
            y,x=box;area=(y.stop-y.start)*(x.stop-x.start)
            if min(y.stop-y.start,x.stop-x.start)<3 or area<max(8,width*height*.00003):continue
            component=components[box]==index
            if component.mean()<.6:continue
            pixels=rgb[box][mask[box]&component]
            if not len(pixels):continue
            result['rectangles'].append({'bbox':norm_box(x.start,y.start,x.stop,y.stop),
                'center_x':(x.start+x.stop-1)*500/(width-1),
                'rgb':np.median(pixels,axis=0).tolist(),'fill_fraction':float(component.mean())})
    for rectangle in result['rectangles']:
        box=rectangle['bbox'];middle=(box[1]+box[3])/2
        band=next((i for i,b in enumerate(result['band_candidates']) if b['bbox'][1]<=middle<=b['bbox'][3]),None)
        rectangle['band_index']=band
        rectangle['touches_lower_frame']=(band is not None and
            abs(box[3]-result['band_candidates'][band]['bbox'][3])<=result['localization_resolution']*4)
    result['rectangles'].sort(key=lambda r:(r['band_index'] if r['band_index'] is not None else -1,r['center_x'],r['bbox'][1]))
    if len(result['rectangles'])>64:
        result['rectangles']=result['rectangles'][:64]
        result['limitations'].append('几何预览超过64个候选；可按实际疑点局部裁剪继续观察，原图不删减。')
    return result
