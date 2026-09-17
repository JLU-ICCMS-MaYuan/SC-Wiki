"""类型化建议、按用户草稿及保存后的精确绑定；不写科学实体，不调用模型。"""
from __future__ import annotations

import copy
import json
import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from backend.services.classification_catalog import MATERIAL_DIMENSIONALITIES
from backend.services.space_groups import CRYSTAL_SYSTEMS

from fastapi import HTTPException
from sqlalchemy import select
from backend import models
from . import property_evidence as ev
from . import scientific_evidence as science

PREFIX = 'proposal:'
NUMBERS = {'value_number', 'value_min', 'value_max', 'uncertainty', 'pressure_value_gpa',
           'pressure_min_gpa', 'pressure_max_gpa', 'temperature_value_k', 'magnetic_field_t'}
INTEGERS = {'element_count', 'reported_space_group_number'}
ENUMS = {'superconductor_kind': ['conventional', 'unconventional', 'unknown'],
         'material_dimensionality': sorted(MATERIAL_DIMENSIONALITIES), 'crystal_system': sorted(CRYSTAL_SYSTEMS),
         'state_kind': ['theoretical', 'experimental', 'mixed', 'unknown'],
         'paper_type': ['theoretical', 'experimental', 'review'],
         'theoretical_subtype': ['calculation', 'method', 'theory']}
IMMUTABLE = {'is_representative', 'record_key', 'record_type', 'property_code', 'custom_property_key', 'definition_key',
             'definition_version', 'structure_key', 'value_kind'}


def schema_for(value, name=''):
    schema = {'type': 'string'}
    if name in ENUMS:
        schema['enum'] = ENUMS[name]
    elif name in INTEGERS:
        schema = {'type': 'integer'}
    elif name in NUMBERS or isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        schema = {'type': 'number'}
    elif isinstance(value, bool):
        schema = {'type': 'boolean'}
    elif isinstance(value, list):
        schema = {'type': 'array', 'items': schema_for(value[0]) if value else {'type': 'string'}}
    elif isinstance(value, dict):
        schema = {'type': 'object', 'properties': {k: schema_for(v, k) for k, v in value.items()}, 'additionalProperties': False}
    return schema


def editable_fields(record):
    if record.get('kind') in {'structure', 'derived'}:
        return []
    if record.get('kind') == 'property':
        current = record['claim']['record']
        derived = {'value_raw', 'unit_raw', 'canonical_unit'} if current.get('record_type') in {'measured_tc', 'predicted_tc'} else set()
        return [{'path': name, 'label': name, 'value': value, 'schema': schema_for(value, name)}
                for name, value in current.items() if name not in IMMUTABLE and name not in derived]
    value = record.get('current_value', record['claim'].get('value'))
    return [{'path': '', 'label': record.get('label', record['field']), 'value': value,
             'schema': schema_for(value, record['field'].rsplit('.', 1)[-1])}]


def valid_value(value, schema):
    kind = schema['type']
    if value is None:
        return False
    if 'enum' in schema and value not in schema['enum']:
        return False
    if kind in {'number', 'integer'}:
        # SQL 定点值在快照中为字符串；提交候选必须是有限数值。
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) and math.isfinite(value) and (kind != 'integer' or int(value) == value)
    if kind == 'string':
        return isinstance(value, str) and len(value) <= 100000
    if kind == 'boolean':
        return isinstance(value, bool)
    if kind == 'array':
        return isinstance(value, list) and len(value) <= 1000 and all(valid_value(v, schema['items']) for v in value)
    if kind == 'object':
        return isinstance(value, dict) and set(value) == set(schema['properties']) and all(valid_value(v, schema['properties'][k]) for k, v in value.items())
    return False


def validate_values(record, values):
    fields = {f['path']: f for f in editable_fields(record)}
    if not isinstance(values, dict) or set(values) - set(fields):
        ev.fail('evidence_proposal_invalid', '建议包含不可修改的字段')
    for path, value in values.items():
        if not valid_value(value, fields[path]['schema']):
            ev.fail('evidence_proposal_invalid', '建议值类型或选项无效：' + fields[path]['label'])
    return values


def checked_proposal(record, raw, chunks):
    if not isinstance(raw, dict) or not raw.get('values') or not editable_fields(record):
        return None
    try:
        values = validate_values(record, raw['values'])
    except HTTPException:
        return None
    sources = [ev.locate(e, chunks) for e in raw.get('evidences', [])]
    if not sources or not all(sources):
        return None
    return {'version': ev.RULE_VERSION, 'values': values, 'evidences': sources,
            'supported': raw.get('supported') is True, 'content_hash': record['content_hash'],
            'source_hash': record['source_hash']}


def check_source(record, result, chunks, human_draft=None):
    evidence = list(result.get('evidences') or [])
    proposal = result.get('proposal') or {}
    evidence.extend(proposal.get('evidences') or [])
    located = []
    for raw in evidence:
        found = ev.locate(raw, chunks)
        if found and found not in located:
            located.append(found)
    origin = record.get('provenance') or {}
    if human_draft and human_draft.get('human_confirmed') and human_draft.get('accepted') and human_draft.get('actor_user_id') and str(human_draft.get('reason') or '').strip():
        return located
    if not located and not (record.get('kind') == 'structure' and origin.get('verified') and origin.get('submitted_by_user_id')):
        ev.fail('evidence_missing', '没有可核验来源，不能接受或批准；请重新查找或返回补充来源')
    return located


def rows_for(session, snapshot, lock=False):
    query = select(models.ScientificEvidenceCheck).where(
        models.ScientificEvidenceCheck.target == snapshot['target'],
        models.ScientificEvidenceCheck.target_id == snapshot['target_id']).order_by(models.ScientificEvidenceCheck.id)
    return list(session.scalars(query.with_for_update() if lock else query))


def row_matches(row, record):
    return row.item_key == record['item_key'] and row.content_hash == record['content_hash'] and row.source_hash == record['source_hash'] and row.rule_version in science.COMPATIBLE_RULES


def save_draft(session, snapshot, actor, key, values, accepted, reason):
    record = next((r for r in snapshot['records'] if r['key'] == key), None)
    if not record or len(reason) > 4000:
        ev.fail('evidence_proposal_invalid', '建议项目或人工理由无效')
    rows = rows_for(session, snapshot, True)
    row = next((r for r in reversed(rows) if row_matches(r, record)), None)
    previous = next((r for r in reversed(rows) if r.item_key == record['item_key']), None)
    if row is None:
        # 理由草稿不依赖模型完成；占位结果明确保持未核对，不进入模型缓存。
        science.save_results(session, snapshot, {key: {'status': 'unchecked', 'reason': '尚未核对科学数据与原文', 'evidences': []}}, actor)
        session.flush()
        row = next(r for r in reversed(rows_for(session, snapshot, True)) if row_matches(r, record))
    validate_values(record, values)
    result = ev.checked_result(record, row.result, snapshot['chunks'])
    proposal = result.get('proposal') or {}
    supported = bool(proposal.get('supported') and ev.digest(values) == ev.digest(proposal.get('values')))
    unchanged = all(science.canonical(f['value']) == science.canonical(values.get(f['path'], f['value'])) for f in editable_fields(record))
    supported = supported or (unchanged and result['status'] == 'supported')
    human = bool(accepted and snapshot['target'] == 'paper' and not supported and reason.strip())
    if accepted:
        validate_domain_values(session, record, values)
        if snapshot['target'] == 'paper' and not supported and not reason.strip():
            ev.fail('evidence_review_required', '保留存疑内容或人工改写时，请说明判断依据')
        if not human:
            if result['status'] == 'unchecked':
                ev.fail('evidence_check_required', '该项目尚未核对，请先完成来源核对')
            check_source(record, result, snapshot['chunks'])
    prior = (row.resolutions or {}).get(PREFIX + str(actor), {})
    draft = {'values': copy.deepcopy(values), 'accepted': accepted, 'reason': reason.strip(),
             'supported': supported, 'human_confirmed': human, 'actor_user_id': actor, 'updated_at': datetime.now(timezone.utc).isoformat(),
             'base_version': snapshot['version'], 'original_value': record.get('current_value'),
             'ai_proposal': copy.deepcopy(proposal), 'ai_status': result['status'], 'ai_reason': result['reason'],
             'history': [*(prior.get('history') or []), *([{k: prior.get(k) for k in ('values', 'accepted', 'reason', 'updated_at', 'actor_user_id')}] if prior and (prior.get('accepted') or accepted) else [])]}
    # 旧模型结论留作审计，不能成为新值的支持资格或自动候选。
    previous_review = prior.get('previous_review')
    if previous is not None and not row_matches(previous, record):
        previous_review = {key: copy.deepcopy(previous.result.get(key)) for key in ('status', 'reason', 'model', 'proposal')}
        previous_review.update(content_hash=previous.content_hash, source_hash=previous.source_hash)
    if previous_review:
        draft['previous_review'] = previous_review
    draft = json.loads(json.dumps(draft, default=str))
    row.resolutions = {**(row.resolutions or {}), PREFIX + str(actor): draft}
    return draft


def expected_claim(record, values):
    claim = copy.deepcopy(record['claim'])
    if record.get('kind') == 'property':
        from backend.ingest.property_modules import normalize_current_tc_value
        claim['record'].update(values)
        claim['record'] = normalize_current_tc_value(claim['record'])
    elif '' in values:
        claim['value'] = sorted(values['']) if record['field'].endswith(('.material_families', '.structure_families')) else values['']
        # 字段值本身也是核对上下文时同步；其他依赖变化仍使结果失效。
        name = record['field'].rsplit('.', 1)[-1]
        if name in claim.get('context', {}):
            claim['context'][name] = values['']
    return claim


def prepare(session, snapshot, actor):
    prepared_id = uuid.uuid4().hex
    records = {r['item_key']: r for r in snapshot['records']}
    patches = []
    selected = {}
    for row in rows_for(session, snapshot, True):
        draft = (row.resolutions or {}).get(PREFIX + str(actor))
        if draft and draft.get('accepted'):
            record = records.get(row.item_key)
            if not record or (not row_matches(row, record) and not draft.get('preparation')):
                continue
            selected[row.item_key] = (row, draft)
    current = {r['item_key']: [r['content_hash'], r['source_hash']] for r in snapshot['records']}
    if selected:
        previous = [d.get('preparation') for _, d in selected.values()]
        if all(previous) and len({p['id'] for p in previous}) == 1:
            stage = None
            if all(k in records and science.canonical(records[k]['claim']) == science.canonical(d['preparation']['expected_claim']) and records[k]['source_hash'] == d['preparation']['source_hash'] for k, (_, d) in selected.items()):
                stage = 'finalize'
            elif current == previous[0]['after_paper'] and current != previous[0]['before']:
                stage = 'scientific'
            if stage:
                return {'preparation_id': previous[0]['id'], 'resume_stage': stage, 'version': snapshot['version'], 'patches': [
                    {key: records[k].get(key) for key in ('key', 'item_key', 'field', 'state_key', 'module_key', 'record_key')} | {'values': d['values']}
                    for k, (_, d) in selected.items()]}
    def projected_claim(record, values):
        claim = expected_claim(record, values)
        for item_key, (_, draft) in selected.items():
            other = records.get(item_key)
            if not other or not record.get('state_key') or other.get('state_key') != record['state_key'] or '' not in draft['values']:
                continue
            name = other['field'].rsplit('.', 1)[-1]
            context = claim.get('state') if record.get('kind') == 'property' else claim.get('context')
            if context is not None and name in context:
                context[name] = draft['values']['']
        return claim
    before = {r['item_key']: [r['content_hash'], r['source_hash']] for r in snapshot['records']}
    after_paper = copy.deepcopy(before)
    for item_key, (_, draft) in selected.items():
        record = records.get(item_key)
        if record and record['field'].startswith('paper.') and record['field'] != 'paper.material_families':
            after_paper[item_key][0] = ev.digest(science.canonical(expected_claim(record, draft['values'])))
    for item_key, (row, draft) in selected.items():
        record = records.get(item_key)
        if not record or not row_matches(row, record):
            # 已应用且精确一致的草稿由 finalize 重试，不重新覆盖新版本。
            ev.fail('evidence_stale', '接受建议后数据已变化，请刷新核对结果后重试')
        validate_values(record, draft['values'])
        validate_domain_values(session, record, draft['values'])
        check_source(record, row.result, snapshot['chunks'], draft if snapshot['target'] == 'paper' else None)
        updated = copy.deepcopy(draft)
        updated['preparation'] = {'id': prepared_id, 'expected_claim': science.canonical(projected_claim(record, draft['values'])),
                                  'source_hash': record['source_hash'], 'before': before, 'after_paper': after_paper}
        row.resolutions = json.loads(json.dumps({**row.resolutions, PREFIX + str(actor): updated}, default=str))
        patches.append({k: record.get(k) for k in ('key', 'item_key', 'field', 'state_key', 'module_key', 'record_key')} | {'values': draft['values']})
    return {'preparation_id': prepared_id if patches else None, 'patches': patches, 'version': snapshot['version']}


def finalize(session, snapshot, actor, preparation_id):
    records = {r['item_key']: r for r in snapshot['records']}
    matched = []
    for row in rows_for(session, snapshot, True):
        draft = (row.resolutions or {}).get(PREFIX + str(actor), {})
        preparation = draft.get('preparation') or {}
        if preparation.get('id') != preparation_id:
            continue
        record = records.get(row.item_key)
        if not draft.get('accepted') or not record or record['source_hash'] != preparation['source_hash'] or science.canonical(record['claim']) != science.canonical(preparation['expected_claim']):
            ev.fail('evidence_stale', '保存内容与接受建议不一致，未绑定人工决定；已保存修改保留待审')
        sources = check_source(record, row.result, snapshot['chunks'], draft if snapshot['target'] == 'paper' else None)
        decision = {k: copy.deepcopy(v) for k, v in draft.items() if k != 'preparation'}
        decision.update(final_value=record.get('current_value'), final_content_hash=record['content_hash'],
                        source_hash=record['source_hash'], preparation_id=preparation_id)
        result = {**record, **{k: row.result.get(k) for k in ('status', 'reason', 'suggestion', 'model')},
                  'evidences': sources, 'decision': decision, 'proposal': row.result.get('proposal'),
                  'status': 'supported' if draft['supported'] else draft.get('ai_status') or row.result.get('status'),
                  'source_kind': 'human_review' if draft.get('human_confirmed') else row.result.get('source_kind')}
        # 明确保留 AI 原判断，放行资格由独立的人工决定或支持过的采纳建议产生。
        matched.append((row, record, result, draft))
    if not matched:
        if any((r.result.get('decision') or {}).get('preparation_id') == preparation_id and (r.result.get('decision') or {}).get('actor_user_id') == actor and r.item_key in records and row_matches(r, records[r.item_key]) for r in rows_for(session, snapshot)):
            return {'status': 'saved', 'version': snapshot['version']}
        ev.fail('evidence_stale', '建议申请不存在、已撤销或属于其他用户')
    for old, record, result, draft in matched:
        science.save_results(session, snapshot, {record['key']: result}, actor)
        # 不再把已应用的旧版本草稿用于下一次准备；历史仍保留在 result.decision。
        resolutions = dict(old.resolutions or {})
        resolutions.pop(PREFIX + str(actor), None)
        old.resolutions = resolutions
    return {'status': 'saved', 'version': snapshot['version']}


def validate_save(session, snapshot, actor, preparation_id, stage):
    current = {r['item_key']: [r['content_hash'], r['source_hash']] for r in snapshot['records']}
    for row in rows_for(session, snapshot):
        draft = (row.resolutions or {}).get(PREFIX + str(actor), {})
        preparation = draft.get('preparation') or {}
        if preparation.get('id') == preparation_id and draft.get('accepted'):
            expected = preparation['after_paper' if stage == 'scientific' else 'before']
            if expected != current:
                ev.fail('evidence_stale', '科学内容在准备后发生变化，未覆盖并发修改，请刷新后重试')
            return
    ev.fail('evidence_stale', '建议申请已失效或属于其他用户')


def validate_domain_values(session, record, values):
    if record.get('kind') != 'property' or not values:
        return
    from backend.ingest.property_modules import validate_record, PropertyValidationError
    candidate = {**record['claim']['record'], **values, 'module_code': record.get('module_code'),
                 'record_key': record.get('record_key')}
    definition = session.scalar(select(models.FormDefinition).where(
        models.FormDefinition.definition_key == candidate.get('definition_key'),
        models.FormDefinition.version == int(candidate.get('definition_version') or 1)))
    if definition is None:
        ev.fail('evidence_proposal_invalid', '当前科学记录的表单定义不存在，请返回编辑器处理')
    try:
        validate_record(candidate, definition, path=record['field'])
    except PropertyValidationError as error:
        ev.fail('evidence_proposal_invalid', str(error))
