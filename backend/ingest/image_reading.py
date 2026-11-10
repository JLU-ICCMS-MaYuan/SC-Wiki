"""#233：一个主模型使用的六类只读图片动作，回执与实际像素分开传输。"""
from __future__ import annotations

import base64
from copy import deepcopy
import io
from pathlib import Path

from PIL import Image
import pymupdf

from .document_ir import content_hash
from .pdf_regions import complete_figure, object_region, region_locator, render_region_image
from .image_catalog import original_source_blocks, SOURCE_CONTEXT_VERSION

VERSION = 'image-reading-v1'
ACTIONS = frozenset({'read_image_context', 'read_complete_object', 'adjust_image_region',
    'recognize_image_text', 'digitize_image_elements', 'verify_image_reading'})


def image_receipt(locator, rendered, *, action, observations=(), parent_receipt_id=None):
    """可持久化回执不含base64；实际图片只能通过本次模型images参数发送。"""
    metadata = {k: deepcopy(v) for k, v in rendered.items() if k not in {'png', 'cache_hit'}}
    result = {'version': VERSION, 'action': action, 'file_id': locator['file_id'],
        'source_sha256': locator['source_sha256'], 'pdf_page': locator['pdf_page'],
        'locator': deepcopy(locator), 'images': [metadata], 'text_observations': list(observations),
        'parent_receipt_id': parent_receipt_id, 'reader': {'method': 'pdf_text_and_registered_ocr', 'version': VERSION,
            'source_context_version': SOURCE_CONTEXT_VERSION}}
    result['receipt_id'] = 'image-receipt-' + content_hash(result)
    return result


class ImageReadingTools:
    def __init__(self, documents, paths, *, cache_dir=None, state=None, cancelled=lambda: False):
        self.documents = documents
        self.paths = dict(paths)
        self.cache_dir = cache_dir
        self.cancelled = cancelled
        saved = state or {}
        if saved and saved.get('version') != VERSION: raise ValueError('图片工具状态版本不兼容')
        self.receipts = deepcopy(saved.get('receipts', {}))
        self.regions = deepcopy(saved.get('regions', {}))
        self.actions = deepcopy(saved.get('actions', {}))
        for ir in documents.values():
            for locator in (ir.coverage.get('visual_regions') or {}).values():
                self.regions.setdefault(locator['region_id'], deepcopy(locator))

    def state(self):
        return {'version': VERSION, 'regions': deepcopy(self.regions),
                'receipts': deepcopy(self.receipts), 'actions': deepcopy(self.actions)}

    def _document(self, file_id):
        if file_id not in self.documents or file_id not in self.paths:
            raise ValueError('图片来源不属于当前授权文件')
        value = self.paths[file_id]
        return self.documents[file_id], Path(value() if callable(value) else value)

    def _locate(self, region_id):
        locator = self.regions.get(region_id)
        if not locator: raise ValueError('区域编号不存在，请先读取当前来源完整对象')
        ir, path = self._document(locator['file_id'])
        if locator['source_sha256'] != ir.source_sha256: raise ValueError('区域原件版本已变化')
        return locator, ir, path

    def _observations(self, ir, path, locator):
        observations = []
        with pymupdf.open(path) as pdf:
            page = pdf[locator['pdf_page'] - 1]; area = pymupdf.Rect(locator['bbox_page'])
            for word in page.get_text('words'):
                rect = pymupdf.Rect(word[:4]) * page.rotation_matrix
                if area.contains(rect):
                    observations.append({'text': word[4], 'bbox_page': list(rect), 'method': 'pdf_text_layer'})
        # OCR块仍声明自身来源，不伪造逐字坐标或新OCR置信度。
        for b in original_source_blocks(ir, page=locator['pdf_page']):
            if (b.pdf_page == locator['pdf_page'] and b.bbox and b.text.strip()
                    and b.metadata.get('source_kind') in {'ocr', 'vision'}
                    and area.contains(pymupdf.Rect(b.bbox))):
                observations.append({'text': b.text, 'bbox_page': list(b.bbox),
                    'method': 'registered_parser_block', 'block_id': b.block_id})
        return observations

    def call(self, name, arguments):
        if self.cancelled(): raise InterruptedError('图片工具已取消')
        if name not in ACTIONS: raise ValueError('图片工具动作不在封闭目录')
        fields = {'read_complete_object': {'file_id', 'block_id'},
            'read_image_context': {'region_id'}, 'recognize_image_text': {'region_id'},
            'adjust_image_region': {'region_id', 'bbox_page', 'reason', 'dpi'},
            'digitize_image_elements': {'region_id', 'panel'}, 'verify_image_reading': {'region_id', 'panel'}}[name]
        if set(arguments) != fields: raise ValueError('图片工具参数不完整或含未知字段')
        identity = content_hash(SOURCE_CONTEXT_VERSION, name, arguments)
        if identity in self.actions:
            receipt = deepcopy(self.receipts[self.actions[identity]])
            locator, ir, path = self._locate(receipt['locator']['region_id'])
            rendered = render_region_image(path, locator, cache_dir=self.cache_dir)
            receipt.update(reused=True, progress='no_new_evidence')
            return receipt, ['data:image/png;base64,' + base64.b64encode(rendered['png']).decode()]
        parent_receipt = None
        if name == 'read_complete_object':
            ir, path = self._document(arguments['file_id'])
            locator = object_region(ir, path, arguments['block_id'])
        else:
            old, ir, path = self._locate(arguments['region_id'])
            parent_receipt = next((r['receipt_id'] for r in reversed(list(self.receipts.values()))
                                   if r['locator']['region_id'] == old['region_id']), None)
            locator = old
            if name == 'adjust_image_region':
                if not arguments['reason'].strip(): raise ValueError('调整区域必须说明具体问题')
                if list(arguments['bbox_page']) != old['bbox_page'] or arguments['dpi'] != old['dpi']:
                    locator = region_locator(path, ir.source_file_id, ir.source_sha256,
                        old['pdf_page'], arguments['bbox_page'], kind=old['kind'], dpi=arguments['dpi'],
                        parent_region_id=old['region_id'])
        rendered = render_region_image(path, locator, cache_dir=self.cache_dir)
        if not rendered['visible_content'] and locator['kind']!='page':
            raise ValueError('裁剪区域没有可见内容，请重新定位，未把空白图当作已读')
        receipt = image_receipt(locator, rendered, action=name,
            observations=self._observations(ir, path, locator), parent_receipt_id=parent_receipt)
        if name == 'read_image_context':
            context_blocks = original_source_blocks(ir, page=locator['pdf_page'])
            receipt['context'] = [{'block_id': b.block_id, 'pdf_page': b.pdf_page, 'text': b.text}
                for b in context_blocks if b.text.strip()]
            receipt['blocks'] = [b.model_dump(mode='json') for b in context_blocks if b.text.strip()]
        if name in {'digitize_image_elements', 'verify_image_reading'}:
            from .chart_reading import calibrate_panel
            from .chart_reading import reading_schema
            from backend.rag.structured_output import validate_output
            schema = reading_schema()['properties']['panels']['items']
            validate_output(arguments['panel'], schema)
            readings, missing = calibrate_panel(arguments['panel'], Image.open(io.BytesIO(rendered['png'])),
                {'file_id': ir.source_file_id, 'sha256': ir.source_sha256, 'page': locator['pdf_page']}, locator['bbox_page'])
            receipt.update(readings=readings, unresolved=missing)
        receipt['receipt_id'] = 'image-receipt-' + content_hash({k:v for k,v in receipt.items() if k!='receipt_id'})
        self.regions[locator['region_id']] = deepcopy(locator)
        self.receipts[receipt['receipt_id']] = deepcopy(receipt)
        self.actions[identity] = receipt['receipt_id']
        ir.coverage.setdefault('visual_regions', {})[locator['region_id']] = deepcopy(locator)
        if name == 'read_complete_object':
            ir.coverage.setdefault('visual_source_regions', {})[arguments['block_id']] = locator['region_id']
        elif name == 'adjust_image_region':
            for block_id, registered in list((ir.coverage.get('visual_source_regions') or {}).items()):
                if registered == old['region_id']:
                    ir.coverage['visual_source_regions'][block_id] = locator['region_id']
        return deepcopy(receipt), ['data:image/png;base64,' + base64.b64encode(rendered['png']).decode()]

    def bind_evidences(self, evidences):
        """服务端补入本轮实际采用的定位；不依赖模型复制定位或创建来源身份。"""
        for evidence in evidences:
            ir=self.documents.get(evidence.get('file_id'))
            if ir is None:continue
            region_id=(ir.coverage.get('visual_source_regions') or {}).get(evidence.get('block_id'))
            locator=self.regions.get(region_id)
            if locator:
                evidence['region_locator']=deepcopy(locator)
                evidence['source_sha256']=ir.source_sha256
                parent=locator
                while parent.get('parent_region_id') in self.regions:
                    parent=self.regions[parent['parent_region_id']]
                if parent['region_id']!=locator['region_id']:
                    evidence['complete_figure']=deepcopy(parent)
        return evidences


def registered_regions(ir):
    """只抽取可重建来源，不把整包IR/图片带入快照。"""
    regions = deepcopy(ir.coverage.get('visual_regions') or {})
    for block in ir.blocks:
        reading = block.metadata.get('chart_reading') or {}
        for key in ('complete_figure', 'region_locator'):
            locator = reading.get(key)
            if locator and locator.get('region_id'):
                regions.setdefault(locator['region_id'], deepcopy(locator))
    return regions


def manifest_tools(documents, manifest, *, cancelled=lambda: False):
    """文件仅在实际动作时解析；沿现有存储层校验授权manifest中的大小/摘要。"""
    from backend.rag.config import settings
    from backend.storage.paths import resolve_file
    paths = {}
    for row in manifest:
        if row.get('kind') != 'pdf' or row.get('file_id') not in documents or not row.get('stored_path'): continue
        def resolve(item=deepcopy(row)):
            return resolve_file(item['stored_path'], size=int(item.get('size') or 0),
                sha256=item['sha256'], media_type='application/pdf')
        paths[row['file_id']] = resolve
    return ImageReadingTools(documents, paths, cache_dir=settings.sc_wiki_data_dir / 'visual_region_cache', cancelled=cancelled)
