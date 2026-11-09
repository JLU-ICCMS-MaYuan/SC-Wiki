"""只恢复v2读图生成的完全相同未读块；原缓存与每个重复项均留证。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .document_ir import DocumentIR


def load_document_ir(path):
    path = Path(path)
    raw = path.read_bytes()
    data = json.loads(raw)
    try:
        return DocumentIR.model_validate(data)
    except ValueError:
        # 通用唯一性保护保持；仅处理已经证明的v2派生重复写入。
        if data.get('coverage', {}).get('chart_reading', {}).get('version') != 'scientific-chart-reading-v2':
            raise
        seen, blocks, duplicates = {}, [], []
        from .chart_reading import unresolved_block
        for block in data.get('blocks', []):
            bid = block.get('block_id')
            if bid not in seen:
                seen[bid] = block; blocks.append(block)
                continue
            previous = seen[bid]
            metadata = block.get('metadata', {})
            issue = metadata.get('chart_unresolved')
            if not isinstance(issue, dict) or metadata.get('parser') != 'scientific-chart-reading-v2':
                raise ValueError('非v2机器派生未读块重复，拒绝恢复')
            expected = unresolved_block(data['source_sha256'], issue, block['reading_order'])
            equal = {k: v for k, v in block.items() if k != 'reading_order'} == {
                k: v for k, v in previous.items() if k != 'reading_order'}
            if (not equal or expected.block_id != bid or expected.text != block.get('text')
                    or expected.content_hash != block.get('content_hash')
                    or expected.pdf_page != block.get('pdf_page')
                    or metadata.get('source_kind') != 'vision'):
                raise ValueError('重复未读块的来源、内容或归属冲突，拒绝恢复')
            duplicates.append({'block_id': bid, 'retained_reading_order': previous['reading_order'],
                               'discarded_reading_order': block['reading_order']})
        if not duplicates:
            raise
        repaired = deepcopy(data); repaired['blocks'] = blocks
        ir = DocumentIR.model_validate(repaired)
    # 全量原IR校验通过后才写恢复结果；任何非重复错误都不会改动缓存。
    backup = path.with_name(path.name + '.before-chart-recovery')
    if backup.exists():
        if backup.read_bytes() != raw:
            raise ValueError('已有不同版本恢复备份，拒绝覆盖')
    else:
        with backup.open('xb') as handle:
            handle.write(raw)
    from .model_runtime import atomic_json
    atomic_json(path.with_name(path.name + '.chart-recovery.json'), {
        'source_sha256': data['source_sha256'], 'original_sha256': hashlib.sha256(raw).hexdigest(),
        'backup': backup.name, 'duplicates': duplicates,
        'scope': '仅合并语义完全相同的v2机器派生未读块，保留每次回执及原缓存；未授予科学通过'})
    atomic_json(path, ir.model_dump(mode='json'))
    return ir
