"""只恢复v2读图生成的完全相同未读块；原缓存与每个重复项均留证。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .document_ir import DocumentIR


def bar_calibration_upgrade(ir, path, source):
    """v10柱几何及v11轴一致性升级；只重提失败面板，复用有效原来源。"""
    import io
    import pymupdf
    from PIL import Image
    from .chart_calibration import bar_edge, align_value_ticks, coordinate_value, verify_horizontal_tick_labels, ChartReadingError
    old = ir.coverage.get('chart_reading') or {}
    legacy = {'scientific-chart-reading-v10', 'scientific-chart-reading-v11', 'scientific-chart-reading-v12', 'scientific-chart-reading-v13'}
    if (old.get('version') not in legacy or old.get('status') != 'completed'
            or old.get('source_sha256') != source['sha256']
            or sorted(old.get('scanned_pages', [])) != sorted(p.pdf_page for p in ir.pages)):
        return None
    blocks = [b for b in ir.blocks if b.metadata.get('selected_for_reading') is not False
              and isinstance(b.metadata.get('chart_reading'), dict)]
    if len(blocks) != old.get('readings'):
        raise ValueError('原读图检查点数量与实际来源不一致，未复用不完整记录')
    images, failures = {}, set()
    def panel_key(fact):
        return (fact['pdf_page'], tuple(fact['crop_bbox']), fact['figure'], fact['panel'], fact['quantity'])
    with pymupdf.open(path) as pdf:
        for block in blocks:
            fact = block.metadata['chart_reading']
            inherited = (block.block_id in old.get('reused_reading_block_ids', []) and fact.get('version') in legacy)
            if (fact.get('source_sha256') != source['sha256'] or not (fact.get('version') == old['version'] or inherited)
                    or str(fact.get('source_file_id')) != str(source['file_id'])):
                raise ValueError('旧读图记录来源或版本冲突，未混入当前结果')
            image_key = (fact['pdf_page'], tuple(fact['crop_bbox']))
            if image_key not in images:
                png = pdf[fact['pdf_page']-1].get_pixmap(dpi=600,alpha=False,
                    clip=pymupdf.Rect(fact['crop_bbox'])).tobytes('png')
                images[image_key] = Image.open(io.BytesIO(png)).convert('RGB')
            image = images[image_key]
            try:
                if list(image.size) != fact['image_size']:
                    raise ChartReadingError('旧图像坐标系与原PDF渲染不一致')
                error=max(fact['point']['pixel_error'],1000/image.width,1000/image.height)
                crop=pymupdf.Rect(fact['crop_bbox'])
                for embedded in pdf[fact['pdf_page']-1].get_image_info():
                    box=pymupdf.Rect(embedded['bbox'])
                    if box.intersects(crop):
                        error=max(error,box.width/embedded['width']/crop.width*1000,
                                  box.height/embedded['height']/crop.height*1000)
                axes = [fact.get('calibrated_axis') or fact['axis']] if fact['point']['reading'] != 'label' else []
                if fact.get('x_reading', {}).get('axis'):
                    axes.append(fact['x_reading']['axis'])
                    verify_horizontal_tick_labels(image, fact['x_reading']['axis'], localization_error=error,
                        panel_bounds=fact['axis']['bounds'],point=fact['point'])
                for axis in axes:
                    coordinate_value(axis, axis['ticks'][0]['position'], pixel_error=2 * error)
                if (old['version'] != 'scientific-chart-reading-v10'
                        or fact['kind'] != 'bar' or fact['point']['reading'] != 'position'):
                    continue
                axis,_=align_value_ticks(image,fact['axis'],localization_error=error,verify_label_positions=True)
                previous_axis=fact.get('calibrated_axis') or fact['axis']
                previous_ticks={tick['value']:tick['position']for tick in previous_axis['ticks']}
                if (len(previous_ticks)!=len(axis['ticks']) or any(
                        tick['value'] not in previous_ticks
                        or abs(tick['position']-previous_ticks[tick['value']])>error
                        for tick in axis['ticks'])):
                    raise ChartReadingError('共享坐标轴修正超出原定位精度，需要重读依赖该轴的面板')
                edge, _ = bar_edge(image, fact['point'], axis)
                if abs(edge - fact['snapped_y']) > 1e-9:
                    raise ChartReadingError('柱几何观察已变化，需要重读当前面板')
            except ChartReadingError:
                failures.add(panel_key(fact))
    targets = old.get('targets') or []
    def owner(fact):
        page = ir.pages[fact['pdf_page']-1]
        crop = list(fact['crop_bbox'])
        options = [t for t in targets if t['page'] == fact['pdf_page']]
        exact = [t for t in options if all(abs(a-b)<1e-6 for a,b in zip(crop,[
            max(0,t['bbox'][0]-12), max(0,t['bbox'][1]-12),
            min(page.width,t['bbox'][2]+12), min(page.height,t['bbox'][3]+12)]))]
        matches = exact or [t for t in options if pymupdf.Rect(crop).intersects(pymupdf.Rect(t['bbox']))]
        if len(matches) != 1:
            raise ValueError('旧失败图读不能唯一归属原目标，未猜测或全篇重提')
        return matches[0]['region_id']
    repair_ids = {owner(b.metadata['chart_reading']) for b in blocks if panel_key(b.metadata['chart_reading']) in failures}
    # v13有些失败观察从未生成读数，不能只复核已经成功的读数而冻结失败轴。
    technical = {'TICK_LABEL_POSITION_UNSUPPORTED', 'TICK_OUTSIDE_AXIS_BOUNDS',
        'TICK_CALIBRATION_INCONSISTENT', 'HORIZONTAL_AXIS_SCOPE_AMBIGUOUS',
        'HORIZONTAL_TICK_LABEL_POSITION_UNSUPPORTED'}
    target_ids = {t['region_id'] for t in targets}
    for issue in old.get('unresolved', []):
        if issue.get('reason_code') not in technical:
            continue
        if issue.get('region_id') not in target_ids:
            raise ValueError('失败标定没有对应原图目标，未猜测恢复范围')
        repair_ids.add(issue['region_id'])
    kept = [b for b in blocks if panel_key(b.metadata['chart_reading']) not in failures]
    retained_panels = {}
    required = {}
    def require(rid, figure, panel, quantity, pair):
        entries = required.setdefault(rid, [])
        matches = [entry for entry in entries if entry['figure']==figure and entry['panel']==panel
                   and (quantity is None or entry['quantity']==quantity)]
        if len(matches)==1:
            entry=matches[0]
        else:
            entry={'figure':figure,'panel':panel,'quantity':quantity,'points':[]}
            entries.append(entry)
        if pair not in entry['points']:
            entry['points'].append(pair)
    for block in blocks:
        fact=block.metadata['chart_reading']
        if panel_key(fact) in failures:
            require(owner(fact),fact['figure'],fact['panel'],fact['quantity'],
                {key:fact['point'][key]for key in ('category','series')})
    for issue in old.get('unresolved',[]):
        if (issue.get('region_id')in repair_ids and all(issue.get(k) for k in ('figure','panel','category','series'))):
            require(issue['region_id'],issue['figure'],issue['panel'],issue.get('quantity'),
                {key:issue[key]for key in ('category','series')})
    for block in kept:
        fact = block.metadata['chart_reading']
        # 不修复的文件/目标不必为了面板展示重新定位；其中的原记录整体复用。
        if not any(t['page'] == fact['pdf_page'] and t['region_id'] in repair_ids for t in targets):
            continue
        rid = owner(fact)
        entry = {key:fact[key] for key in ('figure','panel','quantity')}
        if entry not in retained_panels.setdefault(rid, []):
            retained_panels[rid].append(entry)
    preserved_issues = [deepcopy(issue) for issue in old.get('unresolved', []) if issue.get('region_id') not in repair_ids]
    keep_ids = {b.block_id for b in kept}
    keep_ids.update(b.block_id for b in ir.blocks if b.metadata.get('selected_for_reading') is not False
        and isinstance(b.metadata.get('chart_unresolved'),dict)
        and b.metadata['chart_unresolved'].get('region_id') not in repair_ids)
    return {'targets':deepcopy(targets),'repair_targets':[deepcopy(t)for t in targets if t['region_id']in repair_ids],
        'excluded':deepcopy(old.get('excluded',[])),'regions':deepcopy(old.get('regions',[])),
        'unresolved':preserved_issues,'context_notes':deepcopy(old.get('context_notes',[])),
        'keep_block_ids':keep_ids,'reused_reading_block_ids':[b.block_id for b in kept],
        'retained_panels':retained_panels,'required_panels':required,'previous_version':old['version']}


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
