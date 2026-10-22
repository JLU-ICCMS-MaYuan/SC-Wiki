"""科学核对项、持久结果与来源身份。LLM 不负责权限或来源真实性。"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert

from backend import models

BIBLIOGRAPHY_FIELDS = {
    'title': '标题', 'authors': '作者', 'co_first_authors': '共同第一作者',
    'corresponding_authors': '通讯作者', 'journal': '期刊', 'year': '年份',
    'issue_number': '期号', 'volume': '卷号', 'pages': '页码', 'doi': 'DOI',
}
PAPER_FIELDS = {
    **BIBLIOGRAPHY_FIELDS,
    'abstract': '摘要', 'summary': '论文总结', 'methodology': '研究方法',
    'key_finding': '主要发现', 'research_motivation': '研究动机',
    'keywords_tags': '科学关键词', 'paper_type': '论文类型',
    'theoretical_subtype': '理论子类型', 'superconductor_kind': '超导体类别',
    'material_families': '材料家族', 'research_materials': '研究材料',
    'knowledge_graph_title': '图谱科学标题',
}
STATE_FIELDS = {
    'material_name': '材料名', 'material': '材料化学式', 'material_dimensionality': '材料维度',
    'pressure_value_gpa': '压力', 'pressure_min_gpa': '压力下界', 'pressure_max_gpa': '压力上界',
    'temperature_value_k': '温度', 'magnetic_field_t': '磁场',
    'reported_space_group_symbol': '报告空间群', 'reported_space_group_number': '空间群编号',
    'crystal_system': '晶系', 'state_kind': '材料状态类型', 'structure_optimization': '结构优化核处理',
    'structure_families': '结构家族', 'condition_note': '条件说明', 'note': '状态说明',
    'pressure_raw': '原始压力', 'pressure_unit_raw': '原始压力单位',
    'temperature_raw': '原始温度', 'temperature_unit_raw': '原始温度单位',
    'calculation_context': '计算条件', 'experimental_context': '实验条件',
}

# 概括/推测与分类枚举字段：summary 是 AI 概括；keywords_tags 可为作者原列或 AI 全文提炼。
# 核对按语义判断，但作者原列关键词另须能定位原文列表。
# 事实与数值字段不在其中，仍执行逐字定位（见 checked_result）。
SYNTHESIS_FIELDS = frozenset({
    'summary', 'key_finding', 'methodology', 'keywords_tags', 'research_motivation',
    'knowledge_graph_title', 'paper_type', 'research_materials', 'material_families',
    'theoretical_subtype', 'superconductor_kind',
    'state_kind', 'structure_optimization', 'crystal_system', 'material_dimensionality', 'structure_families',
    'condition_note', 'note',
})

COMPATIBLE_RULES = {'scientific-evidence-v2', 'scientific-evidence-v3', 'scientific-evidence-v4', 'scientific-evidence-v5', 'scientific-evidence-v6', 'scientific-evidence-v7'}


def adopted_suggestion(record):
    """已采用或自动填写的推断只能进入待审，不能授予管理员确认权限。"""
    decision = record.get('decision') or {}
    accepted = (decision.get('accepted') and decision.get('actor_user_id') and
                decision.get('basis_kind') in {'paper_inference', 'general_knowledge'} and
                decision.get('final_content_hash') == record.get('content_hash') and
                decision.get('source_hash') == record.get('source_hash'))
    automatic = (record.get('auto_filled') and record.get('adopted_basis') in {'paper_inference', 'general_knowledge'} and
                 record.get('auto_filled_content_hash') == record.get('content_hash') and
                 record.get('auto_filled_source_hash') == record.get('source_hash'))
    return bool((accepted or automatic) and not record.get('stale'))


def human_confirmed(record, decision=None):
    """只信任服务端保存并绑定当前内容的人工决定，不能凭请求中的理由放行。"""
    decision = decision if decision is not None else record.get('decision') or {}
    return bool(decision.get('human_confirmed') and decision.get('accepted') and
                decision.get('actor_user_id') and str(decision.get('reason') or '').strip() and
                decision.get('final_content_hash') == record.get('content_hash') and
                decision.get('source_hash') == record.get('source_hash') and not record.get('stale'))


def item_identity(*parts):
    from .property_evidence import digest
    return digest(list(parts))


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items()) if k not in {
            'id', 'paper_id', 'paper_revision', 'material_state_id', 'module_id',
            'superconductor_id', 'chemical_system_id', 'structure_id', 'created_at', 'updated_at',
            'evidence', 'evidences', 'display_order', 'is_representative',
            'record_checksum', 'source_fingerprint', 'record_key', 'module_key',
            'tc_group', 'tc_range_origin',
        } and v is not None}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return format(Decimal(str(value)).normalize(), 'f')
    return value


def populated(value):
    return value is not None and value != '' and value != 'unknown' and value != [] and value != {}


def field_records(identity, path, data, fields, context=None, assessment=None, keyword_assessment=None):
    rows = []
    for name, label in fields.items():
        value = data.get(name)
        if name in {'calculation_context', 'experimental_context'} and isinstance(value, dict):
            value = {k: v for k, v in canonical(value).items() if populated(v)}
        if name in {'authors', 'co_first_authors', 'corresponding_authors', 'methodology', 'keywords_tags', 'research_materials'} and isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                pass
        if name in {'material_families', 'structure_families'} and isinstance(value, list):
            value = sorted(str(x.get('name') or x.get('name_zh') or '') if isinstance(x, dict) else str(x) for x in value)
        key = item_identity(identity, name)
        row = dict(key=key, item_key=key, field=f'{path}.{name}', fields=[f'{path}.{name}'],
                         label=label, current_value=value, claim={'value': value, 'field': label, 'context': context or {}},
                         required=populated(value) and not (path == 'paper' and name in BIBLIOGRAPHY_FIELDS),
                         evidences=[], kind='field',
                         **({'check_mode': 'synthesis'} if name in SYNTHESIS_FIELDS else {}))
        row['evidences'] = copy.deepcopy((data.get('field_evidence') or {}).get(name) or [])
        if path == 'paper' and name == 'theoretical_subtype':
            from .theoretical_subtype import RULE_VERSION
            matched = assessment if isinstance(assessment, dict) and assessment.get('value') == value else None
            row['provenance'] = {'kind': 'paper_synthesis', 'rule_version': RULE_VERSION,
                                 **({'assessment': matched} if matched else {})}
            if matched and matched.get('status') == 'completed':
                row['evidences'] = copy.deepcopy(matched.get('evidences') or [])
        if path == 'paper' and name == 'keywords_tags':
            matched = keyword_assessment if isinstance(keyword_assessment, dict) and keyword_assessment.get('values') == value else None
            if matched and matched.get('status') == 'completed':
                row['provenance'] = {'kind': 'author_keywords' if matched.get('kind') == 'author_list' else 'paper_synthesis',
                                     'assessment': matched}
                row['evidences'] = copy.deepcopy(matched.get('evidences') or [])
        rows.append(row)
    return sorted(rows, key=lambda r: not r['required'])


def record_identity(state_key, module_key, record_key):
    return item_identity('record', state_key, module_key, record_key)


def record_claim(record, state):
    from backend.services.scientific_draft_rewrite import _record_snapshot
    value = copy.deepcopy(_record_snapshot(record, module_code=record.get('module_code', '') if isinstance(record, dict) else ''))
    # 模块代码属于稳定定位，不是科学事实；数据库精度和默认值不改变断言。
    value.pop('module_code', None)
    # 分组身份和范围历史是表示/来源元数据，不让模型把它们当作当前科学数值。
    if isinstance(value.get('payload'), dict):
        for key in ('tc_group', 'tc_range_origin'):
            value['payload'].pop(key, None)
    from .review_dependencies import state_inputs
    return copy.deepcopy({'record': value, 'state': state_inputs(state, (value.get('payload') or {}).get('source_associations') or [])})


def state_records(state, index):
    state_key = state.get('state_key') or f'state-{index + 1}'
    rows = field_records(item_identity('state', state_key), f'material_states[{index}]', state, STATE_FIELDS,
                         {k: state.get(k) for k in ('material_name', 'material', 'pressure_value_gpa', 'temperature_value_k', 'magnetic_field_t', 'state_kind') if populated(state.get(k))})
    count = state.get('element_count')
    if count is not None:
        from backend.ingest.scientific_drafts import count_formula_elements
        expected = count_formula_elements(str(state.get('material') or ''))
        key = item_identity('state', state_key, 'element_count')
        rows.append(dict(key=key, item_key=key, field=f'material_states[{index}].element_count',
                         fields=[f'material_states[{index}].element_count'], kind='derived', label='元素种类数',
                         current_value=count, claim={'value': count, 'formula': state.get('material'), **({'material_name': state['material_name']} if populated(state.get('material_name')) else {})}, evidences=[],
                         dependency=item_identity(item_identity('state', state_key), 'material'),
                         provenance={'kind': 'derived', 'rule': '化学式中不同元素的数量',
                                     'input': state.get('material'), 'expected': expected, 'verified': expected == count}))
        if not state.get('material'):
            # 无化学式时，人工提供的元素数量是独立断言，不能伪装成可计算结果。
            rows[-1].update(kind='field')
            rows[-1].pop('dependency', None)
            rows[-1].pop('provenance', None)
    for row in rows:
        row['state_key'] = state_key
        from .state_field_review import context as state_review_context
        if row.get('kind') == 'field':
            row['state_review_context'] = state_review_context(state)
        name = row['field'].rsplit('.', 1)[-1]
        symmetry = derived_symmetry_value(state, name)
        if symmetry and populated(state.get(name)):
            row.pop('state_review_context', None)
            # 群号与晶系由报告符号查表得到，核对依赖符号本身，不要求论文逐字写出。
            row.update(kind='derived', dependency=item_identity(item_identity('state', state_key), 'reported_space_group_symbol'),
                       claim={'value': row['current_value'], 'input': state['reported_space_group_symbol'],
                              'context': {k: state[k] for k in ('material_name', 'material') if populated(state.get(k))}},
                       provenance={'kind': 'derived', 'rule': symmetry, 'input': state.get('reported_space_group_symbol'),
                                   'expected': str(state.get(name)), 'verified': True})
            continue
        conversion = converted_state_value(state, name)
        if conversion and populated(state.get(name)):
            row.pop('state_review_context', None)
            raw_field, expected, rule = conversion
            row.update(kind='derived', dependency=item_identity(item_identity('state', state_key), raw_field),
                       claim={'value': row['current_value'], 'input': state[raw_field],
                              'unit': str(state.get(name.split('_')[0] + '_unit_raw') or '').strip().casefold(),
                              'context': {k: state[k] for k in ('material_name', 'material') if populated(state.get(k))}},
                       provenance={'kind': 'derived', 'rule': rule, 'input': state[raw_field],
                                   'expected': str(expected), 'verified': abs(Decimal(str(state[name])) - expected) <= Decimal('0.000001')})
    return rows


def derived_symmetry_value(state, name):
    """仅当群号/晶系与报告空间群符号的标准对应完全一致时视为派生值。"""
    if name not in {'reported_space_group_number', 'crystal_system'}:
        return None
    from backend.services.space_groups import crystal_system_for_number, lookup_number
    number = lookup_number(str(state.get('reported_space_group_symbol') or ''))
    if number is None:
        return None
    if name == 'reported_space_group_number':
        return '空间群符号查国际表得到群号' if str(state.get(name)) == str(number) else None
    return '空间群符号 → 群号 → 晶系' if state.get(name) == crystal_system_for_number(number) else None


def converted_state_value(state, name):
    """仅对明确原始数值及已知单位执行转换，不推测缺失单位或范围。"""
    if name not in {'pressure_value_gpa', 'temperature_value_k'}:
        return None
    prefix = 'pressure' if name == 'pressure_value_gpa' else 'temperature'
    raw_field = prefix + '_raw'
    unit = str(state.get(prefix + '_unit_raw') or '').strip().casefold()
    raw = str(state.get(raw_field) or '').strip()
    if not raw or not unit:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    if prefix == 'pressure':
        factor = {'pa': '0.000000001', 'kpa': '0.000001', 'mpa': '0.001', 'gpa': '1', 'bar': '0.0001', 'kbar': '0.1', 'atm': '0.000101325'}.get(unit)
        if factor is None:
            return None
        return raw_field, value * Decimal(factor), f'{unit} × {factor} = GPa'
    if unit in {'k', 'kelvin'}:
        return raw_field, value, 'K 原值保留'
    if unit in {'°c', 'c', 'celsius'}:
        return raw_field, value + Decimal('273.15'), '摄氏温度 + 273.15 = K'
    if unit in {'°f', 'f', 'fahrenheit'}:
        return raw_field, (value - 32) * 5 / 9 + Decimal('273.15'), '(华氏温度 − 32) × 5/9 + 273.15 = K'
    return None


def structure_record(structure, state_key, path, origin=None, state_context=None):
    from backend.services.structure_candidates import validate_structure_text
    data = dict(structure)
    provenance = dict(origin or {'kind': 'contributor_structure', 'paper_supported': False})
    try:
        parsed = validate_structure_text(data['structure_format'], data['structure_text'])
        structure_hash = parsed['structure_hash']
        provenance['verified'] = bool(provenance.get('submitted_by_user_id'))
        provenance['parsed'] = parsed
        # 上传候选与正式实体使用相同的科学断言，不混入数据库时间、ID 或展示元数据。
        data = {k: parsed[k] for k in ('cell_parameters', 'atom_count', 'volume', 'elements')}
        data['structure_hash'] = structure_hash
    except (ValueError, KeyError):
        structure_hash = item_identity(data.get('structure_text'))
        provenance['verified'] = False
    review_key = data.get('review_key') or structure.get('review_key') or (item_identity('structure-original-id', structure['id']) if structure.get('id') else item_identity('structure-candidate', structure['candidate_id']) if structure.get('candidate_id') else item_identity('inline-structure', state_key))
    key = item_identity('structure', state_key, review_key)
    return dict(key=key, item_key=key, field=path, fields=[path], label='晶体结构与晶格参数',
                current_value=data, kind='structure', claim=data, evidences=[], provenance=provenance, structure_hash=structure_hash, state_key=state_key,
                legacy_structure_item_key=item_identity('structure', state_key, structure_hash), _state_context=state_context or {})


def origins_for(session, target, target_id):
    return {r.structure_hash: r.provenance for r in session.scalars(select(models.ScientificStructureOrigin).where(
        models.ScientificStructureOrigin.target == target, models.ScientificStructureOrigin.target_id == str(target_id)))}


def register_structure_origin(session, target, target_id, candidate, user_id, username, filename, raw):
    from backend.ingest.scientific_drafts import _candidate_conventional_representation
    from backend.services.structure_candidates import validate_structure_text
    from .property_evidence import digest
    representation = _candidate_conventional_representation(candidate)
    if not representation:
        return
    text, metadata = representation
    parsed = validate_structure_text('cif', text)
    provenance = {'kind': 'contributor_structure', 'structure_hash': parsed['structure_hash'],
                  'submitted_by_user_id': user_id, 'submitted_by_name': username,
                  'filename': filename, 'original_hash': __import__('hashlib').sha256(raw).hexdigest(),
                  'original_text': raw.decode('utf-8'), 'method': metadata.get('standardization_method') or 'ASE / pymatgen',
                  'paper_supported': False, 'verified': True}
    stmt = insert(models.ScientificStructureOrigin).values(target=target, target_id=str(target_id),
        structure_hash=parsed['structure_hash'], provenance=provenance)
    # 同目标同结构保留首次可证明的提交者，不把后续保存者改写成原始提供者。
    session.execute(stmt.on_duplicate_key_update(structure_hash=stmt.inserted.structure_hash))


def augment_upload(draft, records, origins):
    from backend.ingest.scientific_drafts import _candidate_conventional_representation, _candidate_state_index
    from backend.services.structure_candidates import validate_structure_text
    records.extend(field_records('paper', 'paper', draft.get('paper') or {}, PAPER_FIELDS,
                                 assessment=draft.get('theoretical_subtype_assessment'),
                                 keyword_assessment=draft.get('keyword_assessment')))
    for index, state in enumerate(draft.get('material_states') or []):
        records.extend(state_records(state, index))
        structures = []
        if isinstance(state.get('structure'), dict):
            structures.append((state['structure'], f'material_states[{index}].structure'))
        for ci, candidate in enumerate(draft.get('structure_candidates') or []):
            if _candidate_state_index(candidate) != index or candidate.get('confirmation') != 'confirmed':
                continue
            representation = _candidate_conventional_representation(candidate)
            if representation:
                structures.append(({'structure_format': 'cif', 'structure_text': representation[0], 'candidate_id': candidate.get('candidate_id'), 'review_key': candidate.get('review_key')}, f'structure_candidates[{ci}]'))
        for structure, path in structures:
            try:
                hash_value = validate_structure_text(structure['structure_format'], structure['structure_text'])['structure_hash']
            except (ValueError, KeyError):
                hash_value = ''
            records.append(structure_record(structure, state.get('state_key') or f'state-{index+1}', path, origins.get(hash_value), {k: state.get(k) for k in ('material', 'material_name', 'pressure_value_gpa', 'reported_space_group_symbol', 'state_kind')}))


def ordered_check_rows(session, target, target_id, *, lock=False):
    """不在 MySQL filesort 中复制大 JSON；按同一 id 顺序解释历史与最新结果。"""
    query = select(models.ScientificEvidenceCheck).where(
        models.ScientificEvidenceCheck.target == target,
        models.ScientificEvidenceCheck.target_id == target_id)
    rows = session.scalars(query.with_for_update() if lock else query)
    return sorted(rows,key=lambda row:row.id)


def load_result_history(session, snapshot, actor_id=None, include_stale=False):
    current = {r['item_key']: r for r in snapshot['records']}
    found = {}
    histories = {}
    legacy = {}
    previous_fields = {}
    condition_history = {}
    for record in snapshot['records']:
        if record.get('legacy_item_key'):
            legacy.setdefault(record['legacy_item_key'], []).append(record)
        if record.get('previous_field_item_key'):
            previous_fields.setdefault(record['previous_field_item_key'], []).append(record)
    def remember_legacy(row):
        for leaf in legacy.get(row.item_key, []):
            entries = histories.setdefault(leaf['key'], [])
            entry = {k: copy.deepcopy(row.result.get(k)) for k in ('current_value', 'reason', 'evidences', 'audit_events')}
            value = entry.get('current_value')
            if isinstance(value, dict) and isinstance(value.get('record'), dict):
                original = value['record']
                entry['current_value'] = {k: original.get(k) for k in ('name_raw', 'method_code', 'value_raw', 'unit_raw') if original.get(k) is not None}
            entry.update(legacy_scope='record', content_hash=row.content_hash, source_hash=row.source_hash)
            if entry not in entries:
                entries.append(entry)
        for leaf in previous_fields.get(row.item_key, []):
            entries = histories.setdefault(leaf['key'], [])
            entry = {k: copy.deepcopy(row.result.get(k)) for k in ('current_value', 'reason', 'audit_events')}
            entry.update(content_hash=row.content_hash, source_hash=row.source_hash, prior_field_identity=True)
            if entry not in entries:
                entries.append(entry)
    def remember(row, record):
        items = histories.setdefault(record['key'], [])
        for entry in row.result.get('history') or []:
            if entry not in items:
                items.append(copy.deepcopy(entry))
        if row.content_hash == record['content_hash'] and row.source_hash == record['source_hash']:
            return
        entry = {name: copy.deepcopy(row.result.get(name)) for name in ('current_value', 'status', 'reason', 'ai_reason', 'evidences', 'proposal', 'decision', 'adopted_basis', 'audit_events')}
        entry.update(content_hash=row.content_hash, source_hash=row.source_hash)
        if entry not in items:
            items.append(entry)
    for row in ordered_check_rows(session,snapshot['target'],snapshot['target_id']):
        r = current.get(row.item_key)
        if not r:
            remember_legacy(row)
            continue
        remember(row, r)
        if r.get('condition_context'):
            condition_history.setdefault(r['key'], []).append(row.result)
        valid = row.content_hash == r['content_hash'] and row.source_hash == r['source_hash'] and row.rule_version in COMPATIBLE_RULES
        if not valid and row.source_hash == r['source_hash'] and row.rule_version in COMPATIBLE_RULES:
            from .review_dependencies import project_claim
            old_claim = row.result.get('claim')
            if isinstance(old_claim, dict) and r.get('kind') == 'property':
                valid = canonical(project_claim(old_claim)) == canonical(r['claim'])
            elif isinstance(old_claim, dict) and r.get('record_field') and r.get('validation_record'):
                from .review_dependencies import legacy_leaf_claim
                old_context = old_claim.get('context') or {}
                # 只尝试移除不属于直接依赖的核处理/派生展示字段；真实条件仍需逐项一致。
                state = {key: old_context[key] for key in STATE_FIELDS if key in old_context}
                current_context = r['claim'].get('context') or {}
                if all(canonical(state.get(key)) == canonical(current_context.get(key)) for key in r.get('state_dependencies') or []):
                    reconstructed = legacy_leaf_claim(r['validation_record'], state, r['record_field'], r['claim']['field'])
                    valid = canonical(reconstructed) == canonical(old_claim)

        if valid or (include_stale and (r['key'] not in found or found[r['key']].get('stale'))):
            result = copy.deepcopy(row.result)
            result['stale'] = not valid
            result['resolution'] = (row.resolutions or {}).get(str(actor_id), '') if valid else ''
            result['proposal_draft'] = copy.deepcopy((row.resolutions or {}).get('proposal:' + str(actor_id))) if valid else None
            if not valid:
                result['proposal'] = None
                result['decision'] = None
            if valid and result.get('decision') and result['decision'].get('actor_user_id') == actor_id:
                result['resolution'] = result['decision'].get('reason') or ('采纳经来源核对的 AI 建议' if result['decision'].get('supported') else '')
            found[r['key']] = result
    if snapshot['target'] == 'paper':
        for row in session.scalars(select(models.ScientificEvidenceSource).where(
                models.ScientificEvidenceSource.paper_id == int(snapshot['target_id']))):
            r = current.get(row.item_key)
            if r:
                remember(row, r)
            else:
                remember_legacy(row)
            if r and (r['key'] not in found or found[r['key']].get('stale')) and row.content_hash == r['content_hash'] and row.source_hash == r['source_hash'] and row.rule_version in COMPATIBLE_RULES:
                found[r['key']] = copy.deepcopy(row.result)
    for key, history in histories.items():
        if history and key not in found and next(r for r in snapshot['records'] if r['key'] == key).get('record_field'):
            found[key] = {'status': 'unchecked', 'reason': '当前版本的子项尚未独立核对；旧核对记录仅供历史参考', 'evidences': []}
        if history and key not in found and include_stale:
            found[key] = {'status': 'unchecked', 'reason': '内容或来源已变化，请重新核对', 'stale': True}
        elif history and key not in found and not next(r for r in snapshot['records'] if r['key'] == key).get('required', True):
            found[key] = {'status': 'unchecked', 'reason': '当前为空或可选字段；历史记录仅供参考'}
        if key in found:
            found[key]['history'] = history
    from .condition_lifecycle import effective_result
    for record in snapshot['records']:
        if record['key'] in condition_history:
            result = effective_result(record, found.get(record['key']), condition_history[record['key']], snapshot['chunks'])
            if result is not None:
                found[record['key']] = result
    from .evidence_audit import merge_events
    for record in snapshot['records']:
        events = [event for event in snapshot.get('_field_change_events') or [] if event.get('item_key') == record['item_key']]
        if events:
            result = found.setdefault(record['key'], {'status': 'unchecked', 'reason': '当前字段尚未核对'})
            result['audit_events'] = merge_events(result.get('audit_events'), events)
    return found


def load_results(session, snapshot, actor_id=None, include_stale=False):
    """先读取小型版本索引，只取当前需要的JSON；保存路径不调用历史恢复。"""
    table = models.ScientificEvidenceCheck
    current = {r['item_key']: r for r in snapshot['records']}
    if not current:
        return {}
    versions = session.execute(select(table.id, table.item_key, table.content_hash, table.source_hash).where(
        table.target == snapshot['target'], table.target_id == snapshot['target_id'],
        table.item_key.in_(current))).all()
    chosen, exact = {}, set()
    for row_id, key, content, source in sorted(versions):
        record = current[key]
        valid = (content, source) == (record['content_hash'], record['source_hash'])
        if valid or (include_stale and key not in exact):
            chosen[key] = row_id
            if valid:
                exact.add(key)
    found = {}
    rows = session.scalars(select(table).where(table.id.in_(chosen.values()))) if chosen else []
    for row in rows:
        record = current[row.item_key]
        result = copy.deepcopy(row.result)
        result.pop('history', None)
        result.pop('audit_events', None)
        result.update(content_hash=row.content_hash, source_hash=row.source_hash,
                      stale=row.item_key not in exact, stored_result=True)
        from .state_field_review import scope_matches
        if not scope_matches(record, result):
            result.update(stale=True, pending_review=True)
        result['resolution'] = (row.resolutions or {}).get(str(actor_id), '')
        result['proposal_draft'] = copy.deepcopy((row.resolutions or {}).get('proposal:' + str(actor_id)))
        if result['stale']:
            result['pending_review'] = True
        found[record['key']] = result
    if snapshot['target'] == 'paper':
        source_table = models.ScientificEvidenceSource
        for row in session.scalars(select(source_table).where(
                source_table.paper_id == int(snapshot['target_id']), source_table.item_key.in_(current))):
            record = current[row.item_key]
            if row.item_key in exact:
                continue
            if (row.content_hash, row.source_hash) == (record['content_hash'], record['source_hash']):
                result = copy.deepcopy(row.result)
                result.pop('history', None)
                result.pop('audit_events', None)
                result.update(content_hash=row.content_hash, source_hash=row.source_hash, stale=False, stored_result=True)
                from .state_field_review import scope_matches
                if not scope_matches(record, result):
                    result.update(stale=True, pending_review=True)
                found[record['key']] = result
    # 只按精确旧断言版本继承整项通过；旧失败不能复制到所有子字段。
    legacy = {r['legacy_item_key']: r['legacy_content_hash'] for r in current.values()
              if r.get('legacy_content_hash') and r['key'] not in found}
    if legacy:
        ids = session.execute(select(table.id, table.item_key, table.content_hash, table.source_hash).where(
            table.target == snapshot['target'], table.target_id == snapshot['target_id'], table.item_key.in_(legacy))).all()
        latest = {}
        for row_id, key, content, source in sorted(ids):
            if content == legacy[key]:
                latest[(key, source)] = row_id
        rows = session.scalars(select(table).where(table.id.in_(latest.values()))) if latest else []
        for row in rows:
            if row.result.get('status') != 'supported' or row.result.get('source_kind') == 'human_review':
                continue
            for record in current.values():
                if (record['key'] not in found and record.get('legacy_item_key') == row.item_key and
                        record.get('legacy_content_hash') == row.content_hash and record['source_hash'] == row.source_hash):
                    result = {**copy.deepcopy(row.result), **record, 'status': 'supported',
                              'stored_result': True, 'stale': False,
                              'inherited_from': {'item_key': row.item_key, 'content_hash': row.content_hash}}
                    result.pop('history', None)
                    result.pop('audit_events', None)
                    result['evidences'] = copy.deepcopy(row.result.get('evidences') or [])
                    found[record['key']] = result
    return found


def transfer_result(record, result, chunks, file_ids=None):
    """上传落库后重定位所有嵌套引句；文件 ID 变化不能抹掉候选或人工来源。"""
    from .property_evidence import digest, locate, normalized_text
    subtype = record.get('field') == 'paper.theoretical_subtype'
    if subtype and (result.get('provenance') or {}).get('assessment'):
        record['provenance'] = copy.deepcopy(result['provenance'])
        source_hash = digest(sorted(normalized_text(c['content']) for c in chunks))
        record['source_hash'] = digest([source_hash, record['provenance']])
    if result.get('content_hash') != record['content_hash'] or result.get('source_hash') != record['source_hash']:
        history = [{name: copy.deepcopy(result.get(name)) for name in ('current_value', 'status', 'reason', 'ai_reason', 'evidences', 'proposal', 'decision', 'adopted_basis', 'content_hash', 'source_hash', 'audit_events')}]
        return {**record, 'status': 'unchecked', 'reason': '上传值与保存后的内容或来源不同，请重新核对',
                'history': [*(result.get('history') or []), *history]}
    def relocate(source):
        mapped = (file_ids or {}).get(str(source.get('file_id')))
        locator = {k: source.get(k) for k in ('quote', 'page_start', 'page_end', 'origin_kind', 'locator_status')}
        if mapped is not None:
            locator.update(file_id=str(mapped), chunk_index=source.get('chunk_index'))
        return locate(locator, chunks)
    def rebind(value):
        if isinstance(value, list):
            return [rebind(item) for item in value]
        if not isinstance(value, dict):
            return value
        return {key: ([found for source in item if isinstance(source, dict) and
                       (found := relocate(source))]
                      if key in {'evidences', 'fact_evidences', 'scope_evidences', 'software_evidences'} and isinstance(item, list) else rebind(item)) for key, item in value.items()}
    rebound = rebind(copy.deepcopy(result))
    if rebound.get('association_review'):
        from .association_review import association_id
        rebound['association_review']['inputs'] = sorted(association_id(a) for a in record.get('source_associations') or [])
    if subtype and (rebound.get('provenance') or {}).get('assessment'):
        record['provenance'] = copy.deepcopy(rebound['provenance'])
        source_hash = digest(sorted(normalized_text(c['content']) for c in chunks))
        record['source_hash'] = digest([source_hash, record['provenance']])
        rebound['source_hash'] = record['source_hash']
        return {**rebound, **record, 'source_kind': rebound.get('source_kind', 'paper_synthesis'),
                'ai_reason': rebound.get('ai_reason'),
                'evidences': rebound.get('evidences') or record.get('evidences') or []}
    return {**rebound, **record, 'evidences': record.get('evidences') or rebound.get('evidences', [])}


def _review_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def save_results(session, snapshot, results, actor_id, *, update_decision=False):
    # 现有目标行串行化JSON事件追加；不创建新的审计表，也不覆盖并发事件。
    if snapshot['target'] == 'upload':
        session.scalar(select(models.ScientificUploadDraft).where(models.ScientificUploadDraft.task_id == snapshot['target_id']).with_for_update())
    elif snapshot['target'] == 'paper':
        session.scalar(select(models.Paper).where(models.Paper.id == int(snapshot['target_id'])).with_for_update())
    elif snapshot['target'] == 'revision':
        session.scalar(select(models.PaperRevisionDraft).where(models.PaperRevisionDraft.revision_id == snapshot['target_id']).with_for_update())
    for record in snapshot['records']:
        if record['key'] not in results:
            continue
        result = {**record, **results[record['key']]}
        existing_id = session.scalar(select(models.ScientificEvidenceCheck.id).where(
            models.ScientificEvidenceCheck.target == snapshot['target'], models.ScientificEvidenceCheck.target_id == snapshot['target_id'],
            models.ScientificEvidenceCheck.item_key == record['item_key'], models.ScientificEvidenceCheck.content_hash == record['content_hash'],
            models.ScientificEvidenceCheck.source_hash == record['source_hash'], models.ScientificEvidenceCheck.rule_version.in_(COMPATIBLE_RULES)).order_by(models.ScientificEvidenceCheck.id.desc()).limit(1).with_for_update())
        existing = session.get(models.ScientificEvidenceCheck,existing_id) if existing_id is not None else None
        if existing is not None and not update_decision:
            from .field_review import valid_field_decision
            previous_decision = (existing.result or {}).get('field_decision') or {}
            if valid_field_decision(record, existing.result):
                # 人工认可不能被同版本模型回答推翻；人工拒绝后旧任务不能迟到覆盖。
                if (previous_decision['action'] == 'approve' or
                        _review_time(result.get('review_started_at')) <= _review_time(previous_decision.get('occurred_at'))):
                    results[record['key']] = copy.deepcopy(existing.result)
                    continue
                result.pop('field_decision', None)
                result['human_confirmed'] = False
        if existing is not None and not update_decision and (result.get('model') or result.get('review_started_at')):
            # 同一内容版本的较早请求不能在迟到后覆盖较新核对；并非“支持优先”。
            previous_time = _review_time(existing.result.get('review_started_at'))
            if not existing.result.get('review_started_at'):
                previous_time = max((_review_time(e.get('occurred_at')) for e in existing.result.get('audit_events') or []
                                     if e.get('kind') in {'ai_review', 'auto_fill'}), default=previous_time)
            if _review_time(result.get('review_started_at')) < previous_time:
                results[record['key']] = {**copy.deepcopy(existing.result), 'superseded_review': {
                    'review_started_at': result.get('review_started_at'), 'status': result.get('status'), 'reason': result.get('reason')}}
                continue
        if existing is not None and not update_decision:
            from .field_review import retain_valid_pass
            prior = {**existing.result, 'content_hash': existing.content_hash, 'source_hash': existing.source_hash}
            result = retain_valid_pass(record, prior, result)
        if existing is not None and not update_decision and existing.result.get('decision'):
            result['decision'] = copy.deepcopy(existing.result['decision'])
            result['adopted_basis'] = existing.result.get('adopted_basis')
        if existing is not None and existing.result.get('history') and not result.get('history'):
            result['history'] = copy.deepcopy(existing.result['history'])
        if existing is not None and result.get('model') and any(
                existing.result.get(k) != result.get(k) for k in ('status', 'reason', 'evidences')):
            previous_check = {k: copy.deepcopy(existing.result.get(k)) for k in
                ('current_value', 'status', 'reason', 'ai_reason', 'evidences', 'content_hash',
                 'source_hash', 'state_review_context', 'model', 'review_started_at')}
            history = result.setdefault('history', [])
            if previous_check not in history:
                history.append(previous_check)
        if existing is not None and existing.result.get('association_review') != result.get('association_review') and existing.result.get('association_review'):
            previous_review = {name: copy.deepcopy(existing.result.get(name)) for name in
                               ('status', 'reason', 'ai_reason', 'evidences', 'association_review', 'content_hash', 'source_hash')}
            history = result.setdefault('history', [])
            if previous_review not in history:
                history.append(previous_review)
        from .evidence_audit import append_review_event
        append_review_event(session, record, result, existing.result if existing is not None else None, actor_id, human=update_decision)
        result.pop('validation_record', None)  # 服务端临时校验数据，不复制整张记录进每个子项。
        resolutions = copy.deepcopy((existing.resolutions or {}) if existing is not None else {})
        if not update_decision:
            from .evidence_proposals import editable_fields
            from .property_evidence import digest
            proposal = result.get('proposal') or {}
            for key, draft in resolutions.items():
                if not key.startswith('proposal:') or not isinstance(draft, dict) or not draft.get('accepted') or not draft.get('supported') or draft.get('human_confirmed'):
                    continue
                values = draft.get('values') or {}
                unchanged = all(canonical(f['value']) == canonical(values.get(f['path'], f['value'])) for f in editable_fields(record))
                matches_proposal = bool(proposal and digest(values) == digest(proposal.get('values')))
                still_supported = proposal.get('supported') if matches_proposal else unchanged and result.get('status') == 'supported'
                if not still_supported:
                    # 保留输入，但撤回尚未提交的旧通过资格；正式人工决定不受模型改写。
                    draft.update(accepted=False, supported=False, previous_review={'status': draft.get('ai_status'), 'reason': draft.get('ai_reason')})
        stmt = insert(models.ScientificEvidenceCheck).values(
            target=snapshot['target'], target_id=snapshot['target_id'], item_key=record['item_key'],
            content_hash=record['content_hash'], source_hash=record['source_hash'], rule_version=snapshot['rule_version'],
            result=json.loads(json.dumps(result, default=str)), resolutions={}, actor_user_id=actor_id)
        session.execute(stmt.on_duplicate_key_update(result=stmt.inserted.result, resolutions=resolutions, actor_user_id=actor_id))
        if existing is not None:
            session.expire(existing, ['result', 'resolutions'])


def save_resolutions(session, snapshot, actor_id, reasons):
    from .property_evidence import fail
    current = {r['key']: r for r in snapshot['records']}
    for key, reason in reasons.items():
        if key not in current or not isinstance(reason, str) or len(reason) > 4000:
            fail('evidence_resolution_invalid', '裁决项目或理由无效')
        r = current[key]
        row = session.scalar(select(models.ScientificEvidenceCheck).where(
            models.ScientificEvidenceCheck.target == snapshot['target'], models.ScientificEvidenceCheck.target_id == snapshot['target_id'],
            models.ScientificEvidenceCheck.item_key == r['item_key'], models.ScientificEvidenceCheck.content_hash == r['content_hash'],
            models.ScientificEvidenceCheck.source_hash == r['source_hash'], models.ScientificEvidenceCheck.rule_version == snapshot['rule_version'],
        ).with_for_update())
        if row is None:
            fail('evidence_stale', '核对结果已变化，请刷新后填写理由')
        row.resolutions = {**(row.resolutions or {}), str(actor_id): reason.strip()}


def has_upload_checks(session, task_id):
    return session.scalar(select(models.ScientificEvidenceCheck.id).where(
        models.ScientificEvidenceCheck.target == 'upload', models.ScientificEvidenceCheck.target_id == task_id).limit(1)) is not None


def delete_target(session, target, target_id):
    for model in (models.ScientificEvidenceCheck, models.ScientificStructureOrigin):
        session.execute(delete(model).where(model.target == target, model.target_id == str(target_id)))
    if target == 'upload':
        session.execute(delete(models.ScientificUploadDraft).where(models.ScientificUploadDraft.task_id == str(target_id)))


def persist_upload(session, task_id, state, draft):
    values = dict(task_id=task_id, owner_id=int(state['user_id']), state={**state, 'cleanup_at': None}, draft=draft)
    stmt = insert(models.ScientificUploadDraft).values(**values)
    session.execute(stmt.on_duplicate_key_update(state=stmt.inserted.state, draft=stmt.inserted.draft))


def restore_upload(task_id):
    from backend.database import SessionLocal
    from backend.ingest.upload_tasks import redis_client, task_key, draft_key, user_tasks_key
    with SessionLocal() as session:
        saved = session.get(models.ScientificUploadDraft, task_id)
        if saved is None:
            return None
        state = dict(saved.state)
        client = redis_client()
        with client.pipeline(transaction=True) as pipe:
            pipe.set(task_key(task_id), json.dumps(state))
            pipe.set(draft_key(task_id), json.dumps(saved.draft))
            pipe.zadd(user_tasks_key(saved.owner_id), {task_id: int(state.get('updated_at') or 0)})
            pipe.execute()
        return state


def persist_upload_state(task_id, state):
    """同步已受保护草稿的生命周期，防止缓存丢失后恢复旧的可提交状态。"""
    from backend.database import SessionLocal
    with SessionLocal.begin() as session:
        saved = session.get(models.ScientificUploadDraft, task_id, with_for_update=True)
        if saved is not None:
            saved.state = {**state, 'cleanup_at': None}


def restore_user_uploads(user_id):
    from backend.database import SessionLocal
    from backend.ingest.upload_tasks import redis_client, task_key
    with SessionLocal() as session:
        task_ids = list(session.scalars(select(models.ScientificUploadDraft.task_id).where(
            models.ScientificUploadDraft.owner_id == user_id)))
    client = redis_client()
    for task_id in task_ids:
        if not client.exists(task_key(task_id)):
            restore_upload(task_id)


def apply_derived(records):
    from .field_review import valid_field_decision
    by_item = {r['item_key']: r for r in records}
    for record in records:
        if valid_field_decision(record, record):
            continue
        if record.get('kind') != 'derived' or record.get('human_modified'):
            continue
        source = by_item.get(record.get('dependency'))
        if human_confirmed(record):
            continue
        if not record['provenance']['verified']:
            record.update(status='missing', reason='程序复核发现派生值与输入不一致，必须修改数据', suggestion='按以下依据重新计算：' + record['provenance']['rule'], evidences=[])
        elif source and human_confirmed(source):
            decision = copy.deepcopy(source['decision'])
            decision.update(final_content_hash=record['content_hash'], source_hash=record['source_hash'],
                            derived_from=source['item_key'], reason='由人工确认的输入计算：' + record['provenance']['rule'] + '；输入确认理由：' + decision['reason'])
            record.update(decision=decision, human_confirmed=True, source_kind='human_review',
                          adopted_basis=source.get('adopted_basis'),
                          resolution=decision['reason'] if source.get('resolution') else '',
                          reason='计算一致；输入依据为管理员人工确认', evidences=source.get('evidences', []))
        elif source and adopted_suggestion(source):
            decision = copy.deepcopy(source['decision'])
            decision.update(final_content_hash=record['content_hash'], source_hash=record['source_hash'],
                            derived_from=source['item_key'], human_confirmed=False)
            record.update(decision=decision, human_confirmed=False, adopted_basis=decision['basis_kind'],
                          status='uncertain', reason='计算一致；输入为已采用的建议，仍需管理员核验',
                          evidences=source.get('evidences', []))
        elif source and source['status'] == 'supported' and not source.get('stale'):
            record.update(status='supported', reason='由已核验输入确定性计算得到：' + record['provenance']['rule'],
                          suggestion='无需修改', evidences=source['evidences'])
        elif source and (source['status'] == 'unchecked' or source.get('stale')):
            record.update(status='unchecked', reason='计算一致；输入来源尚未核对，请继续核对或由管理员说明依据后确认', evidences=[])
        elif source:
            record.update(status='unchecked', pending_review=True,
                          reason='计算关系保留；问题归到尚未通过的输入字段', evidences=source.get('evidences', []))
    return records


def validate_review_classifications(session, paper_id, incoming):
    """批准请求不得捎带未核对的科学分类，先保存再核对。"""
    from .property_evidence import fail
    paper = session.get(models.Paper, paper_id)
    def stale():
        fail('evidence_stale', '审核分类与已保存数据不一致，请先保存修改并重新核对')
    if incoming.get('superconductor_kind') != paper.superconductor_kind:
        stale()
    expected = set(session.scalars(select(models.PaperMaterialFamily.material_family_id).where(models.PaperMaterialFamily.paper_id == paper_id)))
    actual = set()
    for value in incoming.get('material_families') or []:
        identifier = value.get('id') or session.scalar(select(models.MaterialFamily.id).where(models.MaterialFamily.name_zh == value.get('name')))
        actual.add(identifier)
    if expected != actual:
        stale()
    for value in incoming.get('material_states') or []:
        state = session.get(models.MaterialState, value.get('id'))
        if not state or state.paper_id != paper_id or value.get('material_dimensionality') != state.material_dimensionality:
            stale()
        expected = {(x.structure_family_id, bool(x.is_primary)) for x in session.scalars(select(models.MaterialStateStructureFamily).where(models.MaterialStateStructureFamily.material_state_id == state.id))}
        actual = set()
        for family in value.get('structure_families') or []:
            identifier = family.get('id') or session.scalar(select(models.StructureFamily.id).where(models.StructureFamily.name_zh == family.get('name')))
            actual.add((identifier, bool(family.get('is_primary'))))
        if expected != actual:
            stale()
