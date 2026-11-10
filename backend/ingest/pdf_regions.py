"""#232/#235：不可变PDF区域、完整图注和可清理的内容寻址渲染缓存。"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import uuid

import pymupdf

VERSION = 'pdf-region-v2'
DISCOVERY_DPI = 300
READING_DPI = 600


class RegionError(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def image_cache_key(locator):
    """文件/父区域的业务身份变化不重复生成相同物理像素。"""
    keys=('source_sha256','pdf_page','bbox_page','page_size','cropbox','rotation','dpi','renderer')
    data={k:locator[k] for k in keys}
    data['parts']=[image_cache_key(child) for child in locator.get('related_regions',[])]
    return 'pdf-image-'+_digest(data)


def _source(path, expected):
    path = Path(path)
    if not expected or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RegionError('原PDF摘要与区域来源不一致')
    return path


def _box(value, rect):
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value)
            or not rect.x0 <= value[0] < value[2] <= rect.x1
            or not rect.y0 <= value[1] < value[3] <= rect.y1):
        raise RegionError('区域坐标无效、为空或超出原页')
    return list(value)


def region_locator(path, file_id, source_sha256, page, bbox, *, kind='figure', dpi=READING_DPI,
                   parent_region_id=None, caption_boxes=(), caption_text='', caption_status='not_requested', related_regions=()):
    path = _source(path, source_sha256)
    if type(page) is not int or page < 1 or kind not in {'figure', 'table', 'formula', 'text', 'page'}:
        raise RegionError('区域页码或对象类型无效')
    if type(dpi) is not int or dpi < (DISCOVERY_DPI if kind == 'page' else READING_DPI):
        raise RegionError('区域渲染分辨率不足')
    with pymupdf.open(path) as pdf:
        if page > len(pdf): raise RegionError('原PDF不存在该页')
        original = pdf[page - 1]
        value = {'version': VERSION, 'file_id': str(file_id), 'source_sha256': source_sha256,
            'pdf_page': page, 'kind': kind, 'bbox_page': _box(bbox, original.rect),
            'page_size': [original.rect.width, original.rect.height], 'cropbox': list(original.cropbox),
            'rotation': original.rotation, 'dpi': dpi, 'renderer': 'pymupdf-' + pymupdf.VersionBind,
            'parent_region_id': parent_region_id,
            'caption_boxes': [_box(list(b), original.rect) for b in caption_boxes],
            'caption_text': caption_text, 'caption_status': caption_status,
            'related_regions': deepcopy(list(related_regions))}
    value['region_id'] = 'pdf-region-' + _digest(value)
    return value


def _number(text):
    match = re.search(r'\b(fig(?:ure)?\.?|table)\s*([A-Za-z]?\s*\d+[A-Za-z]?)', text, re.I)
    return ('table:' if match.group(1).casefold()=='table' else 'figure:') + re.sub(r'\s+','',match.group(2)).casefold() if match else None


def caption_candidates(ir, page, label=''):
    """保留完整图注块；原文字层补找时按段落而非单行截取。"""
    number = _number(label)
    output = []
    for block in ir.blocks:
        if (block.pdf_page == page.number + 1 and block.bbox and block.text.strip()
                and (block.block_type == 'caption' or re.match(r'^\s*(?:fig(?:ure)?\.?|table)\s*\w', block.text, re.I))
                and (number is None or _number(block.text) == number)):
            output.append({'bbox': list(block.bbox), 'text': block.text, 'block_id': block.block_id})
    for paragraph in page.get_text('blocks'):
        text = paragraph[4]
        if not isinstance(text, str) or not re.match(r'^\s*(?:fig(?:ure)?\.?|table)\s*\w', text, re.I):
            continue
        if number is not None and _number(text) != number: continue
        rect = (pymupdf.Rect(paragraph[:4]) * page.rotation_matrix) & page.rect
        normalized=' '.join(text.split())
        matched=False
        for existing in output:
            before=' '.join(existing['text'].split());old_box=pymupdf.Rect(existing['bbox'])
            if (_number(existing['text'])==_number(text) and rect.intersects(old_box)
                    and (normalized.startswith(before) or before.startswith(normalized))):
                existing['bbox']=list(rect | old_box)
                if len(normalized)>len(before):existing['text']=text
                matched=True;break
        if not matched:output.append({'bbox':list(rect),'text':text,'block_id':None})
    return output


def complete_figure(ir, path, target, *, related_targets=()):
    """整图含图注后才精读；无法证明配对时保留整页并明确未定位。"""
    path = _source(path, ir.source_sha256)
    with pymupdf.open(path) as pdf:
        page = pdf[target['page'] - 1]
        body = pymupdf.Rect(_box(target['bbox'], page.rect))
        number = _number(target.get('label', ''))
        if number:
            for peer in related_targets:
                if peer['page'] == target['page'] and _number(peer.get('label', '')) == number:
                    body |= pymupdf.Rect(_box(peer['bbox'], page.rect))
        # 目标面板位于一幅完整内嵌图或解析器整图区内时，恢复其父图上下文。
        parents = [pymupdf.Rect(b.bbox) for b in ir.blocks if b.pdf_page == target['page']
            and b.block_type == 'figure' and b.bbox and pymupdf.Rect(b.bbox).contains(body)]
        parents += [pymupdf.Rect(i['bbox']) * page.rotation_matrix for i in page.get_image_info()
            if (pymupdf.Rect(i['bbox']) * page.rotation_matrix).contains(body)]
        if parents: body = max(parents, key=lambda r: r.get_area()) & page.rect
        captions = caption_candidates(ir, page, target.get('label', ''))
        candidates = []
        for caption in captions:
            rect = pymupdf.Rect(caption['bbox'])
            overlap = max(0., min(body.x1, rect.x1) - max(body.x0, rect.x0))
            gap = max(0., rect.y0 - body.y1, body.y0 - rect.y1)
            if overlap > 0 and gap <= page.rect.height / 3:
                candidates.append((gap, caption))
        # 多个候选同编号也不能随意挑一个；完整文字相同可视为同源重复检测。
        unique = {}
        for gap, caption in candidates:
            key = (' '.join(caption['text'].split()), tuple(caption['bbox']))
            unique[key] = (gap, caption)
        related = []
        if not unique and number:
            elsewhere = [(p.number+1,c) for p in pdf if p.number != page.number
                for c in caption_candidates(ir,p,target.get('label',''))]
            if len(elsewhere)==1:
                other_page,caption=elsewhere[0]
                related=[region_locator(path,ir.source_file_id,ir.source_sha256,other_page,
                    caption['bbox'],kind='text',caption_text=caption['text'])]
        if len(unique) == 1:
            caption = next(iter(unique.values()))[1]
            rect = (body | pymupdf.Rect(caption['bbox'])) + (-2, -2, 2, 2)
            bbox = list(rect & page.rect)
            boxes, text, status = [caption['bbox']], caption['text'], 'located'
        elif related:
            bbox,boxes,text,status=list(body),[],caption['text'],'located_across_pages'
        else:
            bbox, boxes, text, status = list(page.rect), [], '', 'ambiguous' if unique else 'unlocated'
    return region_locator(path, ir.source_file_id, ir.source_sha256, target['page'], bbox,
        caption_boxes=boxes, caption_text=text, caption_status=status,related_regions=related)


def object_region(ir, path, block_id):
    """表格保留表头/表注，公式/文字保留上下文；不伪造缺失单元格坐标。"""
    block = ir.block(block_id)
    if block is None or block.bbox is None:
        raise RegionError('来源块不存在或没有可靠坐标')
    if block.block_type == 'figure':
        return complete_figure(ir, path, {'page': block.pdf_page, 'bbox': list(block.bbox), 'label': block.text})
    kind = 'table' if block.block_type in {'table', 'table_cell'} else 'formula' if block.block_type == 'formula' else 'text'
    with pymupdf.open(_source(path, ir.source_sha256)) as pdf:
        page = pdf[block.pdf_page - 1]
        box = pymupdf.Rect(block.bbox)
        if kind == 'table' and block.parent_block_id:
            parent = ir.block(block.parent_block_id)
            if parent and parent.bbox: box |= pymupdf.Rect(parent.bbox)
        if kind == 'table':
            table = next((t for t in ir.tables if t.pdf_page == block.pdf_page and
                (t.table_id == block.table_id or any(c.block_id == block_id for c in t.cells))),None)
            parent = ir.block(table.block_id) if table else None
            if parent and parent.bbox: box |= pymupdf.Rect(parent.bbox)
        related = []
        for other in ir.blocks:
            if other.pdf_page != block.pdf_page or not other.bbox or other.block_id == block_id: continue
            rect = pymupdf.Rect(other.bbox)
            gap = max(0, rect.y0 - box.y1, box.y0 - rect.y1)
            overlap = min(rect.x1, box.x1) - max(rect.x0, box.x0)
            if overlap <= 0: continue
            if (kind == 'table' and other.block_type == 'caption' and gap <= 24
                    and re.match(r'^\s*(?:table|note|表)', other.text, re.I)):
                related.append(other)
            elif kind != 'table' and other.block_type in {'paragraph', 'formula'} and gap <= 16:
                related.append(other)
        for other in related: box |= pymupdf.Rect(other.bbox)
        box = (box + (-2, -2, 2, 2)) & page.rect
    continuations = []
    if kind == 'table' and block.table_id:
        # 仅复用解析器明确登记的同表关联，不按相邻页或相似数值猜跨页表。
        for other in sorted(ir.blocks,key=lambda b:(b.pdf_page,b.reading_order)):
            if other.block_type == 'table' and other.table_id == block.table_id and other.pdf_page != block.pdf_page and other.bbox:
                continuations.append(region_locator(path,ir.source_file_id,ir.source_sha256,
                    other.pdf_page,list(other.bbox),kind='table'))
    return region_locator(path, ir.source_file_id, ir.source_sha256, block.pdf_page, list(box), kind=kind,
        caption_boxes=[b.bbox for b in related if b.block_type == 'caption'],
        caption_text='\n'.join(b.text for b in related if b.block_type == 'caption'),related_regions=continuations)


def clear_region_cache(cache_dir, locators):
    """只清理明确传入定位的可重建派生文件，不扫描或删除原件/快照。"""
    cache = Path(cache_dir)
    removed = []
    for locator in locators:
        value = deepcopy(locator)
        identity = value.pop('region_id',None)
        if identity != 'pdf-region-'+_digest(value):raise RegionError('清理区域定位无效')
        key = image_cache_key(locator)
        for suffix in ('.png','.json'):
            target = cache / (key+suffix)
            if target.is_file():
                target.unlink(); removed.append(target.name)
    return removed


def render_region_image(path, locator, *, cache_dir=None):
    """仅按固定来源定位渲染，不调用模型；缓存缺失或损坏可重建。"""
    value = deepcopy(locator)
    key = value.pop('region_id', None)
    if value.get('version') != VERSION or key != 'pdf-region-' + _digest(value):
        raise RegionError('区域定位被修改或协议版本不支持')
    path = _source(path, value['source_sha256'])
    cache = Path(cache_dir) if cache_dir is not None else None
    cache_key=image_cache_key(locator)
    image_path = cache / (cache_key + '.png') if cache else None
    receipt_path = cache / (cache_key + '.json') if cache else None
    with pymupdf.open(path) as pdf:
        page = pdf[value['pdf_page'] - 1]
        if (value['page_size'] != [page.rect.width, page.rect.height]
                or value['rotation'] != page.rotation or value['cropbox'] != list(page.cropbox)
                or value['renderer'] != 'pymupdf-' + pymupdf.VersionBind):
            raise RegionError('区域页面几何或渲染版本已变化')
        bbox = _box(value['bbox_page'], page.rect)
        hit = False
        png = None
        receipt = None
        if image_path and image_path.is_file() and receipt_path.is_file():
            try:
                candidate = image_path.read_bytes(); receipt = json.loads(receipt_path.read_text())
                from PIL import Image
                import io
                with Image.open(io.BytesIO(candidate)) as cached_image:
                    dimensions = list(cached_image.size)
                if (hashlib.sha256(candidate).hexdigest() == receipt['image_sha256']
                        and receipt.get('cache_key') == cache_key and receipt.get('source_sha256') == value['source_sha256']
                        and receipt.get('dpi') == value['dpi']
                        and isinstance(receipt.get('visible_content'),bool)
                        and dimensions == [receipt.get('width'), receipt.get('height')]):
                    png = candidate; hit = True
            except (OSError, ValueError, KeyError):
                pass
        if png is None:
            pix = page.get_pixmap(dpi=value['dpi'], clip=pymupdf.Rect(bbox), alpha=False)
            if pix.width < 1 or pix.height < 1: raise RegionError('区域渲染为空')
            png = pix.tobytes('png')
            import io
            from PIL import Image
            raw_image=Image.open(io.BytesIO(png)).convert('RGB')
            visible_content=any(low<255 for low,_ in raw_image.getextrema())
            raw_image.close()
            parts=[]
            if value.get('related_regions'):
                import io
                from PIL import Image
                pieces=[(png,{'pdf_page':value['pdf_page'],'bbox_page':bbox,
                    'pixel_to_page':[72/value['dpi'],72/value['dpi'],pix.x*72/value['dpi'],pix.y*72/value['dpi']]})]
                for other in value['related_regions']:
                    if other['source_sha256']!=value['source_sha256']:raise RegionError('跨页关联原件不一致')
                    image=render_region_image(path,other,cache_dir=cache_dir)
                    pieces.append((image['png'],{'pdf_page':other['pdf_page'],'bbox_page':other['bbox_page'],
                        'pixel_to_page':image['pixel_to_page']}))
                opened=[Image.open(io.BytesIO(raw)).convert('RGB') for raw,_ in pieces]
                canvas=Image.new('RGB',(max(i.width for i in opened),sum(i.height for i in opened)+8*(len(opened)-1)),'white')
                offset=0
                for im,(_,metadata) in zip(opened,pieces):
                    canvas.paste(im,(0,offset));parts.append({**metadata,'bbox_pixels':[0,offset,im.width,offset+im.height]})
                    offset+=im.height+8
                out=io.BytesIO();canvas.save(out,format='PNG');png=out.getvalue()
            original_dpi = []
            for image in page.get_image_info():
                rect = pymupdf.Rect(image['bbox']) * page.rotation_matrix
                if rect.intersects(pymupdf.Rect(bbox)) and rect.width > 0 and rect.height > 0:
                    original_dpi.append(min(image['width'] * 72 / rect.width, image['height'] * 72 / rect.height))
            receipt = {'region_id': key, 'source_sha256': value['source_sha256'],
                'cache_key':cache_key,
                'image_sha256': hashlib.sha256(png).hexdigest(), 'width': pix.width, 'height': pix.height,
                'dpi': value['dpi'], 'source_raster_dpi': min(original_dpi) if original_dpi else None,
                'visible_content':visible_content,
                'pixel_to_page': [72 / value['dpi'], 72 / value['dpi'],
                                  pix.x * 72 / value['dpi'], pix.y * 72 / value['dpi']]}
            if parts:
                receipt.update(width=canvas.width,height=canvas.height,pixel_to_page=None,parts=parts)
            if cache:
                cache.mkdir(parents=True, exist_ok=True)
                temporary = cache / (uuid.uuid4().hex + '.part')
                temporary.write_bytes(png); temporary.replace(image_path)
                temporary = cache / (uuid.uuid4().hex + '.part')
                temporary.write_text(json.dumps(receipt)); temporary.replace(receipt_path)
    return {**receipt, 'region_id':key, 'png': png, 'cache_hit': hit}


def render_page_image(path, source_sha256, page, *, file_id='page', dpi=DISCOVERY_DPI, cache_dir=None):
    with pymupdf.open(_source(path, source_sha256)) as pdf:
        if type(page) is not int or not 1 <= page <= len(pdf): raise RegionError('页码无效')
        bbox = list(pdf[page - 1].rect)
    return render_region_image(path, region_locator(path, file_id, source_sha256, page, bbox,
        kind='page', dpi=dpi), cache_dir=cache_dir)
