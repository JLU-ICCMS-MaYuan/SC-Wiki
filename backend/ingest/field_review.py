"""逐字段审核策略。编辑不调用此模块；提交和显式核对共用同一判定。"""
from copy import deepcopy


def field_version(record):
    """结果版本不包含模型名称或实现版本。"""
    return (record['item_key'], record['content_hash'], record['source_hash'])


def reusable(record, result):
    return bool(result and not result.get('stale') and
                result.get('source_kind') != 'human_review' and
                all(result.get(key) == record.get(key) for key in ('content_hash', 'source_hash')) and
                result.get('status') in {'supported', 'unsupported', 'uncertain', 'missing'})


def needs_review(record, result):
    if reusable(record, result):
        return False
    return record.get('required', True) or bool(record.get('human_modified'))


def blocking(record, result):
    if not record.get('required', True) and not record.get('human_modified'):
        return False
    return not reusable(record, result) or result.get('status') != 'supported'


def retain_valid_pass(record, previous, incoming):
    """同版本的矛盾回答是系统异常，不能要求用户重复解决科学问题。"""
    if (reusable(record, previous) and previous.get('status') == 'supported'
            and incoming.get('status') != 'supported'):
        result = deepcopy(previous)
        result.setdefault('consistency_anomalies', []).append({
            'status': incoming.get('status'), 'reason': incoming.get('reason'),
            'model': incoming.get('model'), 'review_started_at': incoming.get('review_started_at'),
        })
        return result
    return incoming


def compact_result(result):
    """摘要不携带原文、候选大对象或历史，字段详情通过独立接口取得。"""
    keys = ('key', 'item_key', 'field', 'fields', 'label', 'current_value', 'status', 'reason',
            'ai_reason', 'resolution', 'required', 'stale', 'pending_review', 'human_modified', 'content_hash',
            'source_hash', 'record_field', 'record_field_key', 'record_group_key', 'state_key',
            'module_key', 'record_key', 'structure_hash', 'structure_field', 'settings_field', 'settings_part', 'owner_label', 'source_kind', 'check_mode')
    return {key: deepcopy(result[key]) for key in keys if key in result} | {'evidences': []}


def independent_fields(records):
    """把旧整条物性、补充条件对象、旧条件汇总拆成现有可编辑键。"""
    from .scientific_evidence import item_identity, populated
    from .property_field_review import read_path
    from .evidence_proposals import schema_for
    result = []
    excluded = {'id', 'paper_id', 'paper_revision', 'material_state_id', 'module_id',
                'record_key', 'module_key', 'state_key', 'display_order', 'is_representative',
                'created_at', 'updated_at', 'record_checksum', 'source_fingerprint',
                'evidences', 'evidence', 'source_associations', 'field_settings',
                'tc_group', 'tc_range_origin', 'dos_fermi_sources', 'parameters_json', 'field_key',
                'record_type', 'property_code', 'custom_property_key', 'definition_key', 'definition_version',
                'canonical_unit', 'canonical_value', 'structure_key'}

    def paths(value, prefix=''):
        for name, child in value.items():
            if name in excluded:
                continue
            path = f'{prefix}.{name}' if prefix else name
            if isinstance(child, dict):
                yield from paths(child, path)
            elif isinstance(child, list) and name == 'extensions':
                for index, extension in enumerate(child):
                    if isinstance(extension, dict):
                        yield from paths(extension, f'{path}.{index}')
            else:
                yield path, child

    for parent in records:
        claim = parent.get('claim') or {}
        root = parent.get('record_field') or ''
        original = claim.get('record')
        value = parent.get('current_value')
        if parent.get('kind') == 'structure' and isinstance(value, dict):
            file_key = parent['item_key']
            result.append({**parent, 'field': parent['field'] + '.structure_text',
                'fields': [parent['field'] + '.structure_text'], 'structure_field': 'structure_text',
                'label': '结构文件及归属', 'current_value': parent.get('structure_hash'),
                'claim': {**parent['claim'], 'context': parent.get('_state_context') or {}}})
            parts = [('volume', value.get('volume')), ('atom_count', value.get('atom_count'))]
            parts += [('cell_parameters.' + key, val) for key, val in (value.get('cell_parameters') or {}).items()]
            for path, child in parts:
                key = item_identity(file_key, 'field', path)
                field = parent['field'] + '.' + path
                result.append({**parent, 'key': key, 'item_key': key, 'kind': 'derived',
                    'field': field, 'fields': [field], 'structure_field': path,
                    'label': {'volume': '晶胞体积', 'atom_count': '原子数'}.get(path, path.split('.')[-1]),
                    'current_value': child, 'required': populated(child), 'dependency': file_key,
                    'claim': {'value': child, 'field': path, 'context': {'state_key': parent.get('state_key')}},
                    'provenance': {'kind': 'derived', 'rule': '从已核对结构文件读取本字段',
                                   'input': child, 'expected': child, 'verified': True}})
            continue
        if parent.get('kind') == 'property' and isinstance(original, dict):
            candidates = list(paths(original))
            context = {'state': claim.get('state') or {}, 'record': deepcopy(original)}
            base = parent['field']
        elif root and isinstance(value, dict) and '.extensions.' in root:
            candidates = list(paths(value))
            context = deepcopy(claim.get('context') or {})
            context['record'] = deepcopy(value)
            base = parent['field']
        elif (parent['field'].endswith(('.calculation_context', '.experimental_context'))
              and isinstance(value, dict)):
            candidates = list(paths(value))
            context = deepcopy(claim.get('context') or {})
            base = parent['field']
        else:
            result.append(parent)
            continue
        from .property_evidence import digest
        from .scientific_evidence import canonical
        from .condition_rules import descriptor
        legacy_claim = deepcopy(parent['claim'])
        policy = descriptor(parent)
        if policy:
            legacy_claim.setdefault('context', {})['condition_policy'] = policy
        legacy_hash = digest(canonical(legacy_claim))
        for path, child in candidates:
            # 扩展的key是定位元数据；name_raw等展示名称是独立审核字段。
            if path.rsplit('.', 1)[-1] == 'key':
                continue
            if path == 'name' and isinstance(value, dict) and value.get('name_raw') is not None:
                continue
            if '.extensions.' in (root + '.' + path) and path.rsplit('.', 1)[-1] not in {'name_raw', 'name', 'value_raw', 'value_kind', 'unit_raw'}:
                continue
            if original is not None and path == 'value_text' and child == original.get('value_raw'):
                continue  # 界面隐藏的兼容镜像不是另一个输入格。
            semantic = 'name_raw' if path == 'name' else path
            extension_key = parent.get('record_field_key')
            if '.extensions.' in path:
                group, tail = path.split('.extensions.', 1)
                index, suffix = tail.split('.', 1)
                extension = read_path(original, f'{group}.extensions.{index}')
                extension_key = extension.get('field_key') or extension.get('key')
                if not extension_key:
                    # 不伪造稳定身份；草稿保存入口负责为新扩展分配field_key。
                    extension_key = item_identity(parent['item_key'], 'legacy-extension', index)
                semantic = f'{group}.extensions.{extension_key}.{suffix}'
            key = item_identity(parent['item_key'], 'leaf', semantic)
            field = f'{base}.{path}'
            row = {k: deepcopy(v) for k, v in parent.items() if k not in {
                'key', 'item_key', 'claim', 'current_value', 'fields', 'field', 'label',
                'condition_context', 'record_dependencies', 'state_dependencies', 'field_schema'}}
            row.update(key=key, item_key=key, kind='field', field=field, fields=[field],
                       label={'name_raw': '名称', 'value_raw': '原始值', 'value_number': '数值', 'value_min': '下界', 'value_max': '上界', 'value_text': '文本值', 'value_boolean': '布尔值', 'unit_raw': '单位', 'value_kind': '值类型', 'method_code': '方法'}.get(path.rsplit('.', 1)[-1], path.rsplit('.', 1)[-1]), current_value=deepcopy(child),
                       required=populated(child), legacy_item_key=parent['item_key'],
                       legacy_content_hash=legacy_hash,
                       field_schema={**schema_for(child, path.rsplit('.', 1)[-1]), 'nullable': True},
                       claim={'value': deepcopy(child), 'field': path, 'context': context},
                       independent_field=True)
            if original is not None or root:
                row.update(record_field=f'{root}.{path}' if root else path,
                           record_field_key=extension_key,
                           validation_record=deepcopy(original or parent.get('validation_record') or {}))
            if root and '.extensions.' in root:
                row['settings_field'] = base + '.value_raw'
                row['settings_part'] = {'name': 'name', 'name_raw': 'name', 'unit_raw': 'unit', 'value_kind': 'kind', 'value_raw': 'raw'}.get(path)
            result.append(row)
    return annotation_fields(result)


def annotation_fields(records):
    """固定参数的显示名称和单位也是独立键；不能放进数值的内容摘要。"""
    from .scientific_evidence import item_identity, populated
    from .property_field_review import read_path
    output = []
    for original in records:
        path = original.get('record_field') or ''
        source = original.get('validation_record') or {}
        setting = None
        if source.get('record_type') == 'predicted_tc' and '.extensions.' not in path:
            if path.startswith('value_'):
                setting = 'payload.field_settings.tc'
            elif path.startswith('payload.parameters.mu_star'):
                setting = 'payload.field_settings.mu_star'
            elif path.startswith('payload.parameters.'):
                setting = 'payload.parameters.field_settings.' + path.split('.')[2].replace('omega_log_k', 'omega_log')
            elif path.startswith('payload.calculation_conditions.'):
                setting = 'payload.calculation_conditions.field_settings.' + path.split('.')[2]
        if setting is None:
            output.append(original)
            continue
        record = deepcopy(original)
        record['claim'].get('context', {}).pop('field_settings', None)
        record['settings_field'], record['settings_part'] = record['field'], 'raw'
        output.append(record)
        root = record['field'][:-len(path)]
        for name, part, label in [('name_raw', 'name', '名称'), ('unit_raw', 'unit', '单位')]:
            value = read_path(source, setting + '.' + name)
            key = item_identity(record['item_key'], 'setting', name)
            field = root + setting + '.' + name
            context = {k: deepcopy(v) for k, v in record['claim'].get('context', {}).items()
                       if k not in {'direct_inputs', 'paired_tc', 'paired_mu_star', 'association_dependencies', 'field_settings'}}
            context['record'] = {'field': record['claim'].get('field'), 'value': record['current_value'],
                                 'canonical_unit': record['claim'].get('context', {}).get('unit')}
            output.append({**record, 'key': key, 'item_key': key, 'field': field, 'fields': [field],
                'record_field': setting + '.' + name, 'settings_part': part, 'independent_field': True,
                'label': record['label'] + ' · ' + label, 'current_value': value, 'required': populated(value),
                'claim': {'value': value, 'field': label, 'context': context}, 'source_associations': [],
                'field_schema': {'type': 'string', 'nullable': True}, 'legacy_item_key': None,
                'record_dependencies': [], 'state_dependencies': []})
    return output


def content_claim(record):
    """核对可读完整上下文，但相邻键不进入本键的内容摘要。"""
    claim = record['claim']
    if not record.get('independent_field'):
        return claim
    context = claim.get('context') or {}
    scope = context.get('state') if 'state' in context else {
        k: v for k, v in context.items() if k not in {'direct_inputs', 'field_settings', 'record'}}
    return {'value': record.get('current_value'), 'scope': scope}


def changed_keys(snapshot):
    """比较本次最终值与第一次人工编辑前的值，不以曾经输入过作为变化。"""
    from .scientific_evidence import canonical
    before = {}
    for event in snapshot.get('_field_change_events') or []:
        if event.get('item_key'):
            before.setdefault(event['item_key'], event.get('before_value'))
    return {r['item_key'] for r in snapshot['records'] if r['item_key'] in before
            and canonical(before[r['item_key']]) != canonical(r.get('current_value'))}


def prepare_submission(snapshot, cached):
    """关系变化的检查归到修改的键；旧通过仅在该关系重新通过后适用。"""
    from .scientific_evidence import canonical
    changed = changed_keys(snapshot)
    modified = [r for r in snapshot['records'] if r['item_key'] in changed]
    for record in snapshot['records']:
        record['human_modified'] = record['item_key'] in changed
        previous = cached.get(record['key'])
        if record['human_modified']:
            related = [r for r in snapshot['records'] if r.get('state_key') == record.get('state_key')
                       and r['item_key'] != record['item_key'] and r.get('required', True)
                       and (r.get('record_key') == record.get('record_key') if record.get('record_key') else
                            r.get('record_field') in {'value_number', 'value_min', 'value_max', 'value_raw', 'method_code'} or r.get('structure_field') == 'structure_text')] if record.get('state_key') else []
            record['review_relationships'] = [{'field': r['field'], 'value': r['claim'] if r.get('structure_field') == 'structure_text' else r.get('current_value'),
                'context': {k: (r.get('claim', {}).get('context') or {}).get(k)
                            for k in ('material', 'method_code', 'approximation')}} for r in related]
        if (record['human_modified'] or not previous or previous.get('status') != 'supported'
                or previous.get('source_hash') != record['source_hash']
                or canonical(previous.get('current_value')) != canonical(record.get('current_value'))
                or reusable(record, previous)):
            continue
        # 只有明确发生变化的同状态字段才能承担新范围判断；来源变更不能借此继承。
        owners = [r for r in modified if record.get('state_key') and r.get('state_key') == record['state_key']
                  and (not r.get('record_key') or r.get('record_key') == record.get('record_key')
                       or r.get('record_group_key') and r.get('record_group_key') == record.get('record_group_key'))]
        def differences(left, right, prefix=''):
            if canonical(left) == canonical(right):
                return []
            if isinstance(left, dict) and isinstance(right, dict):
                return [path for key in left.keys() | right.keys()
                        for path in differences(left.get(key), right.get(key), prefix + '.' + key)]
            return [prefix]
        changed_context = differences((previous.get('claim') or {}).get('context') or {},
                                      (record.get('claim') or {}).get('context') or {})
        # 软件、阶段和物相真的改变时，旧参数在新范围下仍需核实；问题责任归修改入口。
        old_policy = (previous.get('claim') or {}).get('context', {}).get('condition_policy')
        new_policy = (record.get('claim') or {}).get('context', {}).get('condition_policy')
        if canonical(old_policy) != canonical(new_policy):
            record['review_owner_keys'] = [r['key'] for r in owners]
            record['review_owner_values'] = {r['key']: deepcopy(r.get('current_value')) for r in owners}
            continue
        # 不能借一个无关改名，给由其他上下文差异引起的旧结论重新授信。
        if any(not any(path.endswith('.' + (r.get('record_field') or r['field'].split('.')[-1]))
                       or path.endswith('.' + r['field'].split('.')[-1]) for r in owners)
               for path in changed_context):
            continue
        if not owners:
            continue
        cached[record['key']] = {**previous, 'stale': False, 'pending_review': False,
            'content_hash': record['content_hash'], 'source_hash': record['source_hash'],
            'claim': deepcopy(record['claim']), 'prior_claim': deepcopy(previous.get('claim')),
            'scope_review': {'previous_content_hash': previous['content_hash'],
                             'required_keys': [r['key'] for r in owners]}}
    return snapshot, cached


def attribute_relationship_issues(records):
    """保留每个键的原始结论，只把本次关联问题展示在造成范围变化的键上。"""
    from .scientific_evidence import canonical
    records = [dict(r) for r in records]
    by_key = {r['key']: r for r in records}
    for record in records:
        owners = record.get('review_owner_keys') or []
        if not owners or record.get('status') not in {'unsupported', 'uncertain', 'missing'}:
            continue
        record['pending_review'] = True
        for key in owners:
            owner = by_key.get(key)
            if owner is None or canonical(owner.get('current_value')) != canonical((record.get('review_owner_values') or {}).get(key)):
                continue
            owner['status'] = 'unsupported'
            owner['reason'] = '程序检查（关联范围）：新' + owner['label'] + '与现有' + record['label'] + '不对应；' + str(record.get('reason') or '')
            owner['ai_reason'] = owner['reason']
            owner['pending_review'] = False
    return records


def deterministic_results(snapshot):
    """只承认解析器已明确定位的首页字面事实，不用软件默认值猜测科学条件。"""
    from .scientific_evidence import BIBLIOGRAPHY_FIELDS
    from .property_evidence import locate, normalized_text
    results = {}
    for record in snapshot['records']:
        if record['field'].removeprefix('paper.') not in BIBLIOGRAPHY_FIELDS or record.get('human_modified'):
            continue
        value = record.get('current_value')
        values = value if isinstance(value, list) else [value]
        if not all(value not in (None, '') for value in values):
            continue
        sources = [locate(e, snapshot['chunks']) for e in record.get('evidences') or []
                   if e.get('origin_kind') == 'verified_front_matter']
        sources = [e for e in sources if e]
        text = normalized_text(' '.join(e['quote'] for e in sources))
        if sources and all(normalized_text(str(value)) in text for value in values):
            results[record['key']] = {**record, 'status': 'supported', 'source_kind': 'paper_quote',
                'reason': '程序检查：字段与已定位的论文首页原文一致', 'ai_reason': '程序检查：字段与已定位的论文首页原文一致',
                'evidences': sources, 'check_method': 'program'}
    return results


def bind_support_versions(snapshot, session=None):
    """补充证据版本也是本字段来源版本；这里只读取元数据，不加载附件正文。"""
    from contextlib import nullcontext
    from sqlalchemy import select
    from backend.database import SessionLocal
    from .manual_evidence import ScientificManualEvidence, table_available
    from .property_evidence import digest
    with (nullcontext(session) if session is not None else SessionLocal()) as db:
        if not table_available(db):
            return snapshot
        rows = db.execute(select(ScientificManualEvidence.id, ScientificManualEvidence.item_key,
            ScientificManualEvidence.value_hash, ScientificManualEvidence.source_hash,
            ScientificManualEvidence.items, ScientificManualEvidence.reason,
            ScientificManualEvidence.no_evidence_reason).where(
                ScientificManualEvidence.target == snapshot['target'],
                ScientificManualEvidence.target_id == snapshot['target_id'],
                ScientificManualEvidence.item_key.in_([r['item_key'] for r in snapshot['records']]),
                ScientificManualEvidence.status != 'historical')).all()
    for record in snapshot['records']:
        source = record.get('paper_source_hash', record['source_hash'])
        record['source_hash'] = source
        versions = sorted((row[0], digest([row[5], row[6],
            [(i.get('sha256'), i.get('kind'), i.get('source_description')) for i in row[4] or []]]))
            for row in rows if row[1] == record['item_key']
            and row[2] == record['content_hash'] and row[3] == source and (row[4] or row[5] or row[6]))
        if versions:
            record['paper_source_hash'] = source
            record['source_hash'] = digest([source, versions])
    snapshot['version'] = digest([snapshot['target'], snapshot['target_id'],
        sorted(field_version(r) for r in snapshot['records'])])
    return snapshot


def validate_support_versions(snapshot, session):
    """核对期间补充依据有变时保留旧版本历史，禁止把旧回答当成当前结论。"""
    from .property_evidence import fail
    current = bind_support_versions({'target': snapshot['target'], 'target_id': snapshot['target_id'],
        'records': [{key: r[key] for key in ('item_key', 'content_hash', 'source_hash', 'paper_source_hash') if key in r}
                    for r in snapshot['records']]}, session)
    if [field_version(r) for r in current['records']] != [field_version(r) for r in snapshot['records']]:
        fail('evidence_stale', '核对期间人工理由或补充证据发生变化，请核对最新依据')
