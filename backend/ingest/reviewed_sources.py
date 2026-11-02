"""审核后的来源存在性检查；不再比较引句或字段的科学内容。"""
from copy import deepcopy


class SourceReferenceError(ValueError):
    pass


def external_source(source):
    return source.get('origin_kind') == 'external_bibliography'


def source_reference(source, chunks):
    """用已有身份解析可读来源，原始引句与依据类型保持不变。"""
    file_id = source.get('file_id', source.get('paper_file_id'))
    candidates = chunks
    if file_id is not None:
        candidates = [c for c in candidates if str(c['file_id']) == str(file_id)]
    chunk_id = source.get('chunk_id', source.get('paper_chunk_id'))
    if chunk_id is not None:
        candidates = [c for c in candidates if c.get('chunk_id') == chunk_id]
    elif source.get('chunk_index') is not None and file_id is not None:
        candidates = [c for c in candidates if c['chunk_index'] == source['chunk_index']]
    elif source.get('block_id'):
        block = source['block_id']
        candidates = [c for c in candidates if c.get('block_id') == block
                      or f'<!-- block: {block} -->' in c['content']]
    elif file_id is not None and source.get('page_start', source.get('page')) is not None:
        page = source.get('page_start', source.get('page'))
        candidates = [c for c in candidates if c.get('page_start') is not None
                      and c['page_start'] <= page <= (c.get('page_end') or c['page_start'])]
    elif file_id is None:
        raise SourceReferenceError('已审核依据缺少来源位置身份，请补齐资料关联')
    if len(candidates) != 1:
        raise SourceReferenceError('引用的来源不存在或位置身份不唯一，请检查资料关联')
    chunk = candidates[0]
    if not isinstance(chunk.get('content'), str) or not chunk['content'].strip():
        raise SourceReferenceError('引用的来源没有可读取文本，请检查文件解析结果')
    located = {**deepcopy(source), **{k: chunk[k] for k in (
        'file_id', 'chunk_id', 'chunk_index', 'section', 'section_role', 'source_name') if k in chunk}}
    for key in ('page_start', 'page_end'):
        if located.get(key) is None and chunk.get(key) is not None:
            located[key] = chunk[key]
    return located


def rebind_references(value, chunks, file_ids):
    """转接当前采用的来源，不扫描引句；历史材料原样保留。"""
    if isinstance(value, list):
        return [rebind_references(item, chunks, file_ids) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)
    result = {}
    for key, item in value.items():
        if key in {'history', 'legacy_evidences', 'legacy_source_history', 'validation_record', 'audit_events'}:
            result[key] = deepcopy(item)
        elif key in {'evidences', 'fact_evidences', 'scope_evidences', 'software_evidences'} and isinstance(item, list):
            sources = []
            for source in item:
                if not isinstance(source, dict):
                    raise SourceReferenceError('已审核来源记录格式不完整')
                if external_source(source):
                    sources.append(deepcopy(source))
                    continue
                mapped = deepcopy(source)
                old_file = str(source.get('file_id', source.get('paper_file_id')))
                if old_file in file_ids:
                    mapped['file_id'] = str(file_ids[old_file])
                    # 新论文文件/片段ID由持久化生成，原片段序号仍对应同一资料。
                    mapped.pop('chunk_id', None)
                    mapped.pop('paper_chunk_id', None)
                    mapped.pop('paper_file_id', None)
                sources.append(source_reference(mapped, chunks))
            result[key] = sources
        else:
            result[key] = rebind_references(item, chunks, file_ids)
    return result


def checked_references(records, chunks):
    """复用科学结论，仅确认当前采用资料可达；人工历史不冒充原文。"""
    from .field_review import valid_field_decision
    for record in records:
        if record.get('status') != 'supported':
            continue
        sources = []
        for source in record.get('evidences') or []:
            if external_source(source):
                sources.append(deepcopy(source))
                continue
            try:
                sources.append(source_reference(source, chunks))
            except SourceReferenceError as exc:
                if not valid_field_decision(record, record, 'approve'):
                    exc.field = record['field']
                    raise
                record.setdefault('legacy_source_history', []).append({
                    'field': record['field'], 'evidence': deepcopy(source),
                    'status': 'historical_unlocated', 'reason': '人工决定保留；原引用缺少有效来源身份'})
        record['evidences'] = sources
    return records


def apply_property_sources(draft, checks):
    """正式物性关系使用刚通过门禁的字段依据，沿用稳定记录身份。"""
    from .scientific_drafts import _property_modules_for_state
    for state in draft.get('material_states') or []:
        state['property_modules'] = _property_modules_for_state(state)
    for result in checks:
        if result.get('kind') != 'property' and not result.get('record_field'):
            continue
        state = draft['material_states'][result['state_index']]
        module = next(m for m in state['property_modules'] if m['module_key'] == result['module_key'])
        record = next(r for r in module['records'] if r['record_key'] == result['record_key'])
        record.pop('evidence', None)
        if result.get('record_field'):
            record['evidences'] = [e for e in record.get('evidences') or [] if e.get('field_path') != result['record_field']]
            record['evidences'].extend({**deepcopy(e), 'field_path': result['record_field']} for e in result['evidences'])
        else:
            record['evidences'] = deepcopy(result['evidences'])
