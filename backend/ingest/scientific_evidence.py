"""科学核对项、持久结果与来源身份。LLM 不负责权限或来源真实性。"""
from __future__ import annotations

import copy
import json
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert

from backend import models

PAPER_FIELDS = {
    'abstract': '摘要', 'summary': '论文总结', 'methodology': '研究方法',
    'key_finding': '主要发现', 'research_motivation': '研究动机',
    'keywords_tags': '科学关键词', 'paper_type': '论文类型',
    'theoretical_subtype': '理论子类型', 'superconductor_kind': '超导体类别',
    'material_families': '材料家族', 'research_materials': '研究材料',
    'material_relations': '材料关系', 'knowledge_graph_title': '图谱科学标题',
}
STATE_FIELDS = {
    'material_name': '材料名', 'material': '材料化学式', 'material_dimensionality': '材料维度',
    'pressure_value_gpa': '压力', 'pressure_min_gpa': '压力下界', 'pressure_max_gpa': '压力上界',
    'temperature_value_k': '温度', 'magnetic_field_t': '磁场',
    'reported_space_group_symbol': '报告空间群', 'reported_space_group_number': '空间群编号',
    'crystal_system': '晶系', 'state_kind': '材料状态类型',
    'structure_families': '结构家族', 'condition_note': '条件说明', 'note': '状态说明',
    'pressure_raw': '原始压力', 'pressure_unit_raw': '原始压力单位',
    'temperature_raw': '原始温度', 'temperature_unit_raw': '原始温度单位',
    'calculation_context': '计算条件', 'experimental_context': '实验条件',
}

COMPATIBLE_RULES = {'scientific-evidence-v2', 'scientific-evidence-v3', 'scientific-evidence-v4'}


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
        } and v is not None}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return format(Decimal(str(value)).normalize(), 'f')
    return value


def populated(value):
    return value is not None and value != '' and value != 'unknown' and value != [] and value != {}


def field_records(identity, path, data, fields, context=None):
    rows = []
    for name, label in fields.items():
        value = data.get(name)
        if name in {'calculation_context', 'experimental_context'} and isinstance(value, dict):
            value = {k: v for k, v in canonical(value).items() if populated(v)}
        if name in {'methodology', 'keywords_tags', 'research_materials', 'material_relations'} and isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                pass
        if name in {'material_families', 'structure_families'} and isinstance(value, list):
            value = sorted(str(x.get('name') or x.get('name_zh') or '') if isinstance(x, dict) else str(x) for x in value)
        if not populated(value):
            continue
        key = item_identity(identity, name)
        rows.append(dict(key=key, item_key=key, field=f'{path}.{name}', fields=[f'{path}.{name}'],
                         label=label, current_value=value, claim={'value': value, 'field': label, 'context': context or {}},
                         evidences=[], kind='field'))
    return rows


def record_identity(state_key, module_key, record_key):
    return item_identity('record', state_key, module_key, record_key)


def record_claim(record, state):
    from backend.services.scientific_draft_rewrite import _record_snapshot
    value = _record_snapshot(record, module_code=record.get('module_code', '') if isinstance(record, dict) else '')
    # 模块代码属于稳定定位，不是科学事实；数据库精度和默认值不改变断言。
    value.pop('module_code', None)
    return copy.deepcopy({'record': value, 'state': {k: state.get(k) for k in STATE_FIELDS if k != 'structure_families' and populated(state.get(k))}})


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
        name = row['field'].rsplit('.', 1)[-1]
        conversion = converted_state_value(state, name)
        if conversion:
            raw_field, expected, rule = conversion
            row.update(kind='derived', dependency=item_identity(item_identity('state', state_key), raw_field),
                       provenance={'kind': 'derived', 'rule': rule, 'input': state[raw_field],
                                   'expected': str(expected), 'verified': abs(Decimal(str(state[name])) - expected) <= Decimal('0.000001')})
    return rows


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


def structure_record(structure, state_key, path, origin=None):
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
    key = item_identity('structure', state_key, structure_hash)
    return dict(key=key, item_key=key, field=path, fields=[path], label='晶体结构与晶格参数',
                current_value=data, kind='structure', claim=data, evidences=[], provenance=provenance, structure_hash=structure_hash, state_key=state_key)


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
    records.extend(field_records('paper', 'paper', draft.get('paper') or {}, PAPER_FIELDS))
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
                structures.append(({'structure_format': 'cif', 'structure_text': representation[0]}, f'structure_candidates[{ci}]'))
        for structure, path in structures:
            try:
                hash_value = validate_structure_text(structure['structure_format'], structure['structure_text'])['structure_hash']
            except (ValueError, KeyError):
                hash_value = ''
            records.append(structure_record(structure, state.get('state_key') or f'state-{index+1}', path, origins.get(hash_value)))


def load_results(session, snapshot, actor_id=None, include_stale=False):
    current = {r['item_key']: r for r in snapshot['records']}
    found = {}
    query = select(models.ScientificEvidenceCheck).where(
        models.ScientificEvidenceCheck.target == snapshot['target'],
        models.ScientificEvidenceCheck.target_id == snapshot['target_id'],
    ).order_by(models.ScientificEvidenceCheck.id)
    for row in session.scalars(query):
        r = current.get(row.item_key)
        if not r:
            continue
        valid = row.content_hash == r['content_hash'] and row.source_hash == r['source_hash'] and row.rule_version in COMPATIBLE_RULES
        if valid or (include_stale and r['key'] not in found):
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
            if r and r['key'] not in found and row.content_hash == r['content_hash'] and row.source_hash == r['source_hash'] and row.rule_version in COMPATIBLE_RULES:
                found[r['key']] = copy.deepcopy(row.result)
    return found


def save_results(session, snapshot, results, actor_id):
    for record in snapshot['records']:
        if record['key'] not in results:
            continue
        result = {**record, **results[record['key']]}
        existing = session.scalar(select(models.ScientificEvidenceCheck).where(
            models.ScientificEvidenceCheck.target == snapshot['target'], models.ScientificEvidenceCheck.target_id == snapshot['target_id'],
            models.ScientificEvidenceCheck.item_key == record['item_key'], models.ScientificEvidenceCheck.content_hash == record['content_hash'],
            models.ScientificEvidenceCheck.source_hash == record['source_hash'], models.ScientificEvidenceCheck.rule_version.in_(COMPATIBLE_RULES)).order_by(models.ScientificEvidenceCheck.id.desc()).limit(1).with_for_update())
        if existing is not None and not result.get('decision') and existing.result.get('decision'):
            continue
        stmt = insert(models.ScientificEvidenceCheck).values(
            target=snapshot['target'], target_id=snapshot['target_id'], item_key=record['item_key'],
            content_hash=record['content_hash'], source_hash=record['source_hash'], rule_version=snapshot['rule_version'],
            result=json.loads(json.dumps(result, default=str)), resolutions={}, actor_user_id=actor_id)
        session.execute(stmt.on_duplicate_key_update(result=stmt.inserted.result, resolutions=(existing.resolutions or {}) if existing is not None else {}, actor_user_id=actor_id))
        if existing is not None:
            session.expire(existing, ['result'])


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
    by_item = {r['item_key']: r for r in records}
    for record in records:
        if record.get('kind') != 'derived':
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
                          resolution=decision['reason'] if source.get('resolution') else '',
                          reason='计算一致；输入依据为管理员人工确认', evidences=source.get('evidences', []))
        elif source and source['status'] == 'supported' and not source.get('stale'):
            record.update(status='supported', reason='由已核验输入确定性计算得到：' + record['provenance']['rule'],
                          suggestion='无需修改', evidences=source['evidences'])
        elif source and (source['status'] == 'unchecked' or source.get('stale')):
            record.update(status='unchecked', reason='计算一致；输入来源尚未核对，请继续核对或由管理员说明依据后确认', evidences=[])
        elif source:
            record.update(status='uncertain' if source.get('evidences') else 'missing',
                          reason='派生值的输入来源尚未通过核对', evidences=source.get('evidences', []))
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
