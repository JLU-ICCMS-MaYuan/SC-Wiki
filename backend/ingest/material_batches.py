"""材料组按填写、来源门、核对、保存串行执行；完整草稿只由宿主持有。"""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

from .scientific_context import fingerprint
from .scientific_form_filling import fill_scientific_forms, validate_filling_coverage, VERSION as FILL_VERSION
from .model_review import CONTRACT as REVIEW_VERSION

VERSION = 'material-groups-v1'
BATCH_SIZE = 2


class MaterialBatchIncomplete(RuntimeError):
    pass


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def report_summary(value):
    """请求全文只留执行制品；嵌套分组也不能将attempts带回科学草稿。"""
    if isinstance(value, dict):
        return {k: report_summary(v) for k, v in value.items() if k != 'attempts'}
    if isinstance(value, list):
        return [report_summary(v) for v in value]
    return deepcopy(value)


def _report(groups, status):
    dispositions = {}
    for group in groups:
        rows = group['filling_report'].get('candidate_dispositions') or {}
        if set(dispositions) & set(rows):
            raise ValueError('材料分组的原候选身份重复')
        dispositions.update(deepcopy(rows))
    return {'version': FILL_VERSION, 'status': status, 'stop_reason': 'material_groups',
            'candidate_dispositions': dispositions,
            'issues': [deepcopy(issue) for g in groups for issue in g['filling_report'].get('issues') or []],
            'batches': [report_summary(g['filling_report']) for g in groups]}


def process_material_groups(draft, sources, model, *, review, prepare, save, checkpoint,
                            identity, cancelled=lambda: None, on_progress=lambda _: None):
    """每组完成后才调用下一组；回调沿正式来源、核对和事务保存，不另设科学通过规则。"""
    checkpoint = Path(checkpoint)
    original = deepcopy(draft['material_states'])
    keys = [s['state_key'] for s in original]
    if len(set(keys)) != len(keys):
        raise ValueError('材料状态身份重复')
    source_identity = fingerprint([VERSION, FILL_VERSION, REVIEW_VERSION, BATCH_SIZE,
                                   identity, draft['paper'], original, sources])
    groups = []
    try:
        saved = json.loads(checkpoint.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        saved = {}
    if saved.get('source_identity') == source_identity:
        cached = saved.get('completed_groups') or []
        valid = len(cached) <= (len(original) + BATCH_SIZE - 1) // BATCH_SIZE
        for index, group in enumerate(cached):
            offset = index * BATCH_SIZE
            valid = valid and group.get('offset') == offset and group.get('state_keys') == keys[offset:offset+BATCH_SIZE]
        if valid and saved.get('draft', {}).get('paper') == draft['paper']:
            groups = deepcopy(cached)
            draft.clear(); draft.update(deepcopy(saved['draft']))
    total = (len(original) + BATCH_SIZE - 1) // BATCH_SIZE
    filled_states = deepcopy(original)
    for group in groups:
        start = group['offset']
        filled_states[start:start+len(group['state_keys'])] = deepcopy(group['filled_states'])
    if groups:
        on_progress({'index': len(groups), 'total': total, 'state_count': len(groups[-1]['state_keys']),
                     'completed_states': sum(len(g['state_keys']) for g in groups), 'action': 'completed'})
    for index in range(len(groups), total):
        cancelled()
        offset = index * BATCH_SIZE
        state_keys = keys[offset:offset+BATCH_SIZE]
        def progress(action):
            on_progress({'index': index + 1, 'total': total, 'state_count': len(state_keys),
                         'completed_states': offset, 'action': action})
        progress('filling')
        values, filling = fill_scientific_forms(original[offset:offset+BATCH_SIZE], sources, model,
            _state_offset=offset, cancelled=cancelled,
            on_attempt=lambda value: _write(checkpoint.parent/'material-groups'/f'{index:04d}-filling.json', value))
        if filling['status'] not in {'completed', 'not_needed'}:
            reasons = '; '.join(i.get('message', '') for i in filling.get('issues') or [])
            raise MaterialBatchIncomplete(f'第{index+1}/{total}组填写未完成：{reasons}')
        if [s.get('state_key') for s in values] != state_keys:
            raise ValueError('材料填写改变了状态身份或数量')
        draft['material_states'][offset:offset+len(state_keys)] = values
        claims = prepare(draft, offset, len(state_keys))
        prepared = deepcopy(draft['material_states'][offset:offset+len(state_keys)])
        entry = {'offset': offset, 'state_keys': state_keys, 'filling_report': report_summary(filling),
                 'filled_states': prepared, 'claims': [c.model_dump(mode='json') for c in claims]}
        draft['form_filling_report'] = _report([*groups, entry], 'in_progress')
        paper, other = deepcopy(draft['paper']), deepcopy(draft['material_states'])
        cancelled(); progress('reviewing')
        results = review(draft, state_keys) or {}
        if draft['paper'] != paper or len(draft['material_states']) != len(keys):
            raise ValueError('材料组核对改变了论文值或状态数量')
        if any(s != other[i] for i, s in enumerate(draft['material_states']) if i not in range(offset, offset+len(state_keys))):
            raise ValueError('材料组核对修改了其他组')
        if [s.get('state_key') for s in draft['material_states']] != keys:
            raise ValueError('材料组核对改变了状态身份')
        errors = [str(r['review_error']) for r in results.values() if r.get('review_error')]
        errors.extend(str(e.get('message') or e) for e in (draft.get('model_review_report') or {}).get('errors') or [])
        cancelled(); progress('saving')
        save(draft)
        if errors:
            raise MaterialBatchIncomplete(f'第{index+1}/{total}组核对未完成：' + '; '.join(errors))
        entry.update(review_results=deepcopy(results), review_report=deepcopy(draft.get('model_review_report') or {}))
        groups.append(entry)
        filled_states[offset:offset+len(state_keys)] = prepared
        cancelled()
        _write(checkpoint, {'version': VERSION, 'source_identity': source_identity,
                            'completed_groups': groups, 'draft': draft})
        on_progress({'index': index+1, 'total': total, 'state_count': len(state_keys),
                     'completed_states': offset+len(state_keys), 'action': 'completed'})
    report = _report(groups, 'completed')
    validate_filling_coverage(original, filled_states, report)
    draft['form_filling_report'] = report
    from .claim_evidence import Claim
    return {'filling_report': report, 'input_states': original, 'filled_states': filled_states,
            'claims': [Claim.model_validate(c) for g in groups for c in g['claims']],
            'review_results': {key: value for g in groups for key, value in g['review_results'].items()},
            'review_reports': [g['review_report'] for g in groups]}
