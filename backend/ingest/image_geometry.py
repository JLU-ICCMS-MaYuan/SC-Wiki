"""原图的无标签几何观察；不识别材料、物理量、单位或科学数值。"""
from __future__ import annotations

import hashlib
import numpy as np
from PIL import Image
from scipy.ndimage import binary_closing, label, find_objects

VERSION = 'image-geometry-v1'


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
