"""经用户确认的计算条件规则；来源类型与审核结果分开保存。"""
from copy import deepcopy
import math
import re
import unicodedata

VERSION = 'condition-rules-v2'
PARAMETERS = {'calculation_code', 'electronic_method', 'exchange_correlation_functional',
              'phonon_method', 'k_grid', 'q_grid', 'q_grid_interpolated', 'energy_cutoff',
              'charge_density_cutoff', 'convergence_energy', 'convergence_force',
              'supercell', 'atoms', 'temperature_k'}
STAGES = {'structural_relaxation', 'electronic_structure', 'electron_phonon', 'superconductivity', 'sscha'}
SOFTWARE_ALIASES = {
    'vasp': ('vasp', 'viennaabinitiosimulationpackage'),
    'quantumespresso': ('quantumespresso',), 'sscha': ('sscha',),
}


def normalized(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold().replace('\u00ad', '')
    return text.replace('−', '-').replace('–', '-').replace('å', 'a')


def compact(value):
    return re.sub(r'[^a-z0-9]', '', normalized(value))


def identity_in_text(value, text):
    text = re.sub(r'[/_{}$-]', '', normalized(text))
    token = compact(value)
    return bool(token) and bool(re.search(r'(?<![a-z0-9])' + r'\s*'.join(map(re.escape, token)) + r'(?![a-z0-9])', text))


def scalar(value):
    if isinstance(value, dict):
        for key in ('value_number', 'value_text', 'value_raw'):
            if value.get(key) not in (None, ''):
                return value[key]
    return value


def software_key(value):
    key = compact(scalar(value))
    if key in {'qe', 'quantumespressopackage', 'quantumespressosoftware'}:
        return 'quantumespresso'
    if key.startswith('viennaabinitiosimulationpackage'):
        return 'vasp'
    return key


def software_in_text(software, text):
    key = software_key(software)
    if not key:
        return False
    if key == 'quantumespresso' and re.search(r'\bqe\b', normalized(text)):
        return True
    return any(alias in compact(text) for alias in SOFTWARE_ALIASES.get(key, (key,)))


def is_condition(record):
    return str(record.get('record_field') or '').startswith('payload.calculation_conditions.')


def descriptor(record):
    if not is_condition(record):
        return None
    context = (record.get('claim') or {}).get('context') or {}
    source = record.get('validation_record') or {}
    conditions = (source.get('payload') or {}).get('calculation_conditions') or {}
    path = record['record_field']
    if '.extensions.' in path:
        value = record.get('current_value')
        if not isinstance(value, dict):
            if not path.endswith('.value_raw'):
                return None
            from .property_field_review import read_path
            value = read_path(source, '.'.join(path.split('.')[:4]))
            if not isinstance(value, dict):
                return None
        key = str(value.get('key') or '')
        if '.' not in key:
            return None
        stage, parameter = key.split('.', 1)
    else:
        parameter = path.rsplit('.', 1)[-1]
        stages = {a.get('stage') for a in record.get('source_associations') or []}
        if len(stages) > 1:
            return None
        stage = next(iter(stages), 'electron_phonon')
    if parameter not in PARAMETERS or stage not in STAGES:
        return None
    if parameter in {'supercell', 'atoms', 'temperature_k'} and stage != 'sscha':
        return None
    if parameter == 'calculation_code':
        software = scalar(record.get('current_value'))
    elif stage == 'electron_phonon':
        software = conditions.get('calculation_code')
    else:
        values = [scalar(e) for e in conditions.get('extensions') or [] if e.get('key') == stage + '.calculation_code']
        software = values[0] if len(values) == 1 else None
    result = {'version': VERSION, 'parameter': parameter, 'stage': stage, 'software': software_key(software),
            'material': context.get('material'),
            'phase': context.get('reported_space_group_symbol') or context.get('reported_space_group_number'),
            'approximation': context.get('approximation'), 'structure_optimization': context.get('structure_optimization')}
    return result


def policy_context(record):
    return record.get('condition_context') or descriptor(record)


def scope_candidates(record, chunks):
    context = policy_context(record)
    if not context:
        return []
    return [f'review-source-{i}' for i, c in enumerate(chunks) if
            identity_in_text(context.get('material'), c['content']) and identity_in_text(context.get('phase'), c['content'])]


def result_context(record):
    """结果数字只作表格定位辅助，不进入共用条件内容版本。"""
    context = deepcopy(policy_context(record) or {})
    source = record.get('validation_record') or {}
    state = (record.get('claim') or {}).get('context') or {}
    parameters = (source.get('payload') or {}).get('parameters') or {}
    context['result_numbers'] = [v for v in [state.get('pressure_value_gpa'), source.get('value_number'),
        source.get('value_min'), source.get('value_max'), scalar(parameters.get('lambda_ep')),
        scalar(parameters.get('omega_log'))] if type(v) in (int, float)]
    return context


def result_candidates(record, chunks):
    context = result_context(record)
    if context.get('stage') != 'sscha' or not context.get('result_numbers'):
        return []
    return [f'review-source-{i}' for i, c in enumerate(chunks) if anharmonic_result_matches(context, c['content'])]


def anharmonic_result_matches(context, text):
    """仅匹配明确非谐分组内的当前结果；不能借同一表的谐波行凑数。"""
    from .scientific_context import reported_value_matches
    values = context.get('result_numbers') or []
    if not values:
        return False
    for paragraph in re.split(r'\n\s*\n', text):
        match = re.search(r'\banharmonic[\s|:]+(?=\d)', paragraph, re.I)
        if not match:
            continue
        section = re.split(r'\bharmonic[\s|:]+(?=\d)', paragraph[match.start():], flags=re.I)[0]
        if all(reported_value_matches(n, str(n), [{'quote': section}]) for n in values):
            return True
    return False


def evidence_candidates(record, chunks):
    context = policy_context(record) or {}
    if not context:
        return {}
    return {'material_phase': scope_candidates(record, chunks), 'sscha_result': result_candidates(record, chunks),
            'software': [f'review-source-{i}' for i, c in enumerate(chunks) if software_in_text(context['software'], c['content'])],
            'value': [f'review-source-{i}' for i, c in enumerate(chunks)
                      if value_matches(record.get('current_value'), context['parameter'], [{'quote': c['content']}])]}


def material_phase_anchor(context, chunks):
    """补入同一原句/表行的明确身份锚点，不用全文两个孤立词拼接归属。"""
    from .property_evidence import locate
    anchors = []
    for chunk in chunks:
        for sentence in re.split(r'(?<=[.!?])\s+|\n+', chunk['content']):
            if len(sentence) > 600 or re.search(r'\b(?:not|without|unlike|whereas|respectively|previously)\b', sentence, re.I):
                continue
            if identity_in_text(context.get('material'), sentence) and identity_in_text(context.get('phase'), sentence):
                found = locate({**chunk, 'quote': sentence.strip()}, chunks)
                if found:
                    anchors.append(found)
    return min(anchors, key=lambda e: len(e['quote'])) if anchors else None


PROMPT = '''
计算条件规则 condition-rules-v2：有 condition_context 的记录，额外在每个 results[i] 内输出 condition_review：
{"verdict":"supported|not_reported|conflict|uncertain","value_origin":"reported|dfpt_definition",
 "scope":{"material":"当前材料","phase":"当前物相","software":"对应软件","stage":"对应阶段","parameter":"对应参数用途","approximation":"anharmonic|harmonic|unknown"},
 "exceptions":"none|present|unknown","explanation":"简短中文依据及适用范围",
 "fact_evidences":[{"source_id":"review-source-N"}],"scope_evidences":[{"source_id":"review-source-N"}],
 "software_evidences":[{"source_id":"review-source-N"}]}。
引用本次 sources 的编号，服务端取原文；范围依据要能对应材料及物相，不能仅引用没有材料/相的通用Methods句子。
condition_scope_candidates仅为包含当前材料和物相文字的原文候选，请阅读后选择适用的一条或多条，
并与Methods共同放入scope_evidences；不能只复制旧关联的Methods引句而漏掉物相依据。
condition_evidence_candidates分别给出值、软件、材料/相和SSCHA结果行候选；这些可能在不同段落，
请分别放到fact_evidences、software_evidences和scope_evidences，不要机械地三处填同一个编号。
阅读本批全部正文/SI，包括局部例外。若本批无相关内容，返回not_reported且不编造证据；
无法判明归属用uncertain；明确不同的软件/阶段/相/参数用途或数值用conflict。
同材料、同相、同软件、同阶段且无例外时，仅压力不同允许共用Methods设置，不要求作者逐压力重复。
software与stage都必须匹配，VASP的能量/力收敛阈值不能给QE。
分别处理采样q网格与插值q网格、波函数与电荷密度截断能、能量与力阈值。
明确DFPT用于当前流程时，允许value_origin=dfpt_definition判断电子结构方法DFT；DFPT仍是声子方法。
其他数值必须原文明示，不按比例补截断能、不凭化学式猜超胞原子数、不默认0 K。
泛函必须有对应软件的报告。严禁从VASP-PBE推断QE-PBE；QE没有报告泛函就留空。
未报告的可选条件留空，不提出通用知识猜测或软件默认值。已有值仍逐项判断，不自动改写。
SSCHA超胞/原子数/温度只能给当前SSCHA/非谐流程，不能套给另一条谐波或AIMD结果。
SSCHA条件须引用声明SSCHA非谐流程及材料/物相适用范围的原文，scope写approximation=anharmonic。
不要以Tc数值或μ*是否匹配决定未变共用条件是否有效；结果配对与流程归属另行核对。
condition_result_candidates仅提供原表定位线索，不是共用条件通过的前置要求；结果数值归属由结果核对处理。
旧关联标签和以前的判断不是本次依据。关联属于paper_inference不妨碍按确认规则核对，仍保留其推断身份。
有condition_context时优先完成condition_review，服务端会据此更新对应关联，无需重复生成association_reviews。
'''


def locate_sources(entries, chunks):
    from .property_evidence import locate
    if not isinstance(entries, list) or not entries:
        return None
    found = []
    for evidence in entries:
        if not isinstance(evidence, dict):
            return None
        if str(evidence.get('source_id') or '').startswith('review-source-'):
            matches = [c for i, c in enumerate(chunks) if evidence['source_id'] == f'review-source-{i}']
            if len(matches) != 1:
                return None
            evidence = {**matches[0], 'quote': matches[0]['content']}
        located = locate(evidence, chunks)
        if not located:
            return None
        found.append(located)
    return found


def reported_for_software(value, software, sources):
    """参数与软件须有同句或连续单软件语境，不能拼接不同软件的报告。"""
    from .scientific_context import reported_value_matches
    ordered = sorted(sources, key=lambda e: (str(e.get('file_id') or ''), e.get('chunk_index') if isinstance(e.get('chunk_index'), int) else -1))
    previous = None
    active = set()
    for source in ordered:
        identity = (source.get('file_id'), source.get('chunk_index'))
        if not (previous and identity[0] is not None and identity[0] == previous[0]
                and isinstance(identity[1], int) and isinstance(previous[1], int) and identity[1] == previous[1] + 1):
            active = set()
        sentences = re.split(r'[.!?;]\s+|\n\s*\n|\b(?:whereas|while|but|unlike)\b|'
                             r'(?:,\s*|\band\s+)(?=(?:QE|Quantum|VASP|SSCHA|ABINIT)\b)', source['quote'], flags=re.I)
        for sentence in sentences:
            mentioned = {key for key in {*SOFTWARE_ALIASES, software_key(software)} if software_in_text(key, sentence)}
            if mentioned:
                active = mentioned
            if reported_value_matches(scalar(value), '', [{'quote': sentence}]):
                if active == {software_key(software)}:
                    return True
        previous = identity
    return False


def value_matches(value, parameter, facts):
    from .scientific_context import reported_value_matches
    if scalar(value) in (None, ''):
        return False
    if parameter not in {'energy_cutoff', 'charge_density_cutoff', 'convergence_energy', 'convergence_force', 'temperature_k'}:
        return reported_value_matches(value, str(scalar(value)), facts)
    # 数值与单位一起比较，避免1 meV被1 eV或其他用途的裸数字授信。
    unit = value.get('unit_raw') if isinstance(value, dict) else None
    target = str(scalar(value)) + (' ' + unit if unit else '')
    units = {'ev': 1., 'mev': .001, 'ry': 13.605693122994, 'ha': 27.211386245988, 'hartree': 27.211386245988}
    if parameter == 'convergence_force':
        units = {k + '/a': v for k, v in units.items()}
    if parameter == 'temperature_k':
        units = {'k': 1.}
    def quantities(text):
        text = normalized(text).replace('Å', 'a')
        text = re.sub(r'10\s*\^?\s*\{?(-\d+)\}?', r'1e\1', text)
        alternatives = '|'.join(re.escape(u) for u in sorted(units, key=len, reverse=True))
        pattern = r'(?<![\d.])([+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?)\s*(' + alternatives + r')(?![a-z/])'
        return [float(n) * units[u] for n, u in re.findall(pattern, text)]
    expected = quantities(target)
    observed = quantities(' '.join(e['quote'] for e in facts))
    return bool(expected) and all(any(math.isclose(a, b, rel_tol=1e-6, abs_tol=0.) for b in observed) for a in expected)


def window_hash(chunks):
    from .property_evidence import digest
    # 文件身份和角色另由source_hash绑定；提交时文件ID转换不改变实际读到的正文。
    return digest([c['content'] for c in chunks])


def validate_assessment(record, raw, chunks):
    context = policy_context(record)
    if not context or not isinstance(raw, dict) or raw.get('verdict') != 'supported':
        return None
    if not all(context.get(k) for k in ('material', 'phase', 'software')) or raw.get('exceptions') != 'none':
        return None
    scope = raw.get('scope') or {}
    if not isinstance(scope, dict):
        return None
    for key in ('material', 'phase', 'stage', 'parameter'):
        if compact(scope.get(key)) != compact(context.get(key)):
            return None
    if software_key(scope.get('software')) != context['software']:
        return None
    if context['stage'] == 'sscha' and context.get('approximation') == 'harmonic':
        return None
    evidence = {name: locate_sources(raw.get(name), chunks) for name in ('fact_evidences', 'scope_evidences', 'software_evidences')}
    if not all(evidence.values()) or not str(raw.get('explanation') or '').strip():
        return None
    software_text = ' '.join(e['quote'] for e in evidence['software_evidences'])
    scope_text = ' '.join(e['quote'] for e in evidence['scope_evidences'])
    if not software_in_text(context['software'], software_text):
        return None
    if not identity_in_text(context['material'], scope_text) or not identity_in_text(context['phase'], scope_text):
        method_sources = {(e.get('file_id'), e.get('chunk_index')) for e in
                          [*evidence['fact_evidences'], *evidence['software_evidences']]}
        if not all((e.get('file_id'), e.get('chunk_index')) in method_sources for e in evidence['scope_evidences']):
            return None
        anchor = material_phase_anchor(context, chunks)
        if not anchor:
            return None
        evidence['scope_evidences'].append(anchor)
        scope_text += ' ' + anchor['quote']
    if context['stage'] == 'sscha':
        if scope.get('approximation') == 'harmonic':
            return None
        # 非谐流程必须有依据；结果数值不是共用条件事实的身份。
        if scope.get('approximation') != 'anharmonic' or not re.search(r'\banharmonic\b|非谐', normalized(scope_text + ' ' + software_text)):
            return None
    origin = raw.get('value_origin')
    value = record.get('current_value')
    ownership_sources = [*evidence['fact_evidences'], *evidence['software_evidences']]
    if (context['parameter'] == 'electronic_method' and dfpt_definition(value, evidence['fact_evidences'])
        and reported_for_software('DFPT', context['software'], ownership_sources)):
        origin = 'dfpt_definition'
    if origin == 'dfpt_definition':
        facts_text = ' '.join(e['quote'] for e in evidence['fact_evidences'])
        if context['parameter'] != 'electronic_method' or compact(scalar(value)) != 'dft' or not (
            re.search(r'\bdfpt\b', normalized(facts_text)) or 'densityfunctionalperturbation' in compact(facts_text)) or not reported_for_software('DFPT', context['software'], ownership_sources):
            return None
    elif origin != 'reported' or not value_matches(value, context['parameter'], evidence['fact_evidences']):
        return None
    ownership_fields = {'exchange_correlation_functional', 'electronic_method', 'energy_cutoff',
                        'charge_density_cutoff', 'convergence_energy', 'convergence_force'}
    if origin == 'reported' and context['parameter'] in ownership_fields and not reported_for_software(value, context['software'], ownership_sources):
        return None
    return {'verdict': 'supported', 'value_origin': origin,
            'scope': {**deepcopy(context), **({'approximation': 'anharmonic'} if context['stage'] == 'sscha' else {})},
            'exceptions': 'none', 'explanation': raw['explanation'].strip(), **evidence}


def checked_window(record, raw, chunks, source_catalog=None):
    if not policy_context(record):
        return None
    catalog = source_catalog if source_catalog is not None else chunks
    prepared = deepcopy(raw)
    if isinstance(raw, dict) and raw.get('verdict') == 'supported':
        for name in ('fact_evidences', 'scope_evidences', 'software_evidences'):
            # 模型编号只在当前窗口解释；全目录只能补入确定性的身份/表行依据。
            prepared[name] = locate_sources(raw.get(name), chunks) or []
    assessment = validate_assessment(record, prepared, catalog)
    verdict = raw.get('verdict') if isinstance(raw, dict) else 'uncertain'
    if not assessment and verdict not in {'not_reported', 'conflict'}:
        verdict = 'uncertain'
    return {'window_hash': window_hash(chunks), 'verdict': 'supported' if assessment else verdict,
            'assessment': assessment, 'error': review_error(record, prepared, catalog) if not assessment else None}


def review_error(record, raw, chunks):
    context = policy_context(record)
    if not context:
        return None
    if not isinstance(raw, dict):
        return '未返回当前计算条件的范围核对'
    if raw.get('verdict') in {'not_reported', 'conflict', 'uncertain'}:
        return None
    software = locate_sources(raw.get('software_evidences'), chunks)
    if not software or not software_in_text(context.get('software'), ' '.join(e['quote'] for e in software)):
        return '软件依据未明确出现当前软件 ' + str(context.get('software')) + '，请引用声明该软件的段落，不能只引用下一段的参数'
    scope = locate_sources(raw.get('scope_evidences'), chunks)
    if not scope:
        return '缺少可定位的适用范围原文'
    text = ' '.join(e['quote'] for e in scope)
    if not identity_in_text(context.get('material'), text) or not identity_in_text(context.get('phase'), text):
        return '范围引句未包含当前材料及物相，请在Methods之外补入适用的材料/物相原文'
    if context['stage'] == 'sscha':
        from .scientific_context import reported_value_matches
        if ((raw.get('scope') or {}).get('approximation') != 'anharmonic'
            or not re.search(r'\banharmonic\b|非谐', normalized(text))):
            return 'SSCHA范围须明确非谐计算流程，并提供当前材料/物相的适用原文'
    return '当前值、单位、软件、阶段或参数用途未通过一致性校验，不能只引用其他软件的设置'


def finalize(record, candidates, chunks):
    from .property_evidence import source_batches
    if not record.get('condition_sources_complete') or not chunks:
        return None
    windows = [c.get('condition_window') for c in candidates]
    expected = {window_hash(batch) for batch in source_batches(chunks)}
    if (not all(windows) or len(windows) != len(expected)
        or {w['window_hash'] for w in windows} != expected
        or any(w['verdict'] in {'conflict', 'uncertain'} for w in windows)):
        return None
    assessments = [w['assessment'] for w in windows if w['assessment']]
    if not assessments:
        return None
    return {'version': VERSION, 'content_hash': record['content_hash'], 'source_hash': record['source_hash'],
            'rule_id': 'dfpt_to_dft' if any(a['value_origin'] == 'dfpt_definition' for a in assessments) else 'reported_condition_scope',
            'coverage': sorted(expected), 'assessments': assessments}


def current_review(record, result, chunks):
    from .property_evidence import source_batches
    review = result.get('rule_review') or {}
    if (result.get('stale') or result.get('status') in {'missing', 'unsupported', 'unchecked'}
        or any(e.get('locator_status') == 'source_unavailable' for e in result.get('evidences') or [])
        or not record.get('condition_sources_complete')
        or review.get('version') != VERSION or review.get('content_hash') != record.get('content_hash')
        or review.get('source_hash') != record.get('source_hash')
        or review.get('coverage') != sorted({window_hash(b) for b in source_batches(chunks)})):
        return None
    assessments = [validate_assessment(record, a, chunks) for a in review.get('assessments') or []]
    if not assessments or not all(assessments) or result.get('association_conflict') or result.get('condition_conflict'):
        return None
    rule_id = 'dfpt_to_dft' if any(a['value_origin'] == 'dfpt_definition' for a in assessments) else 'reported_condition_scope'
    if review.get('rule_id') != rule_id:
        return None
    return {**review, 'assessments': assessments}


def renewed_associations(record, review, chunks):
    from .association_review import association_id, checked_review
    assessment = review['assessments'][0]
    return checked_review(record, [{'association_id': association_id(a), 'verdict': 'applicable',
        'basis_kind': a.get('basis_kind', 'paper_inference'), 'explanation': assessment['explanation'],
        'fact_evidences': assessment['fact_evidences'], 'scope_evidences': assessment['scope_evidences']}
        for a in record.get('source_associations') or []], chunks)


def proposal_allowed(record, basis, values, sources):
    if not is_condition(record):
        return True
    context = policy_context(record)
    if not context or basis != 'paper_quote':
        return False
    value = values.get('')
    if context['parameter'] == 'exchange_correlation_functional':
        return reported_for_software(value, context['software'], sources)
    return value_matches(value, context['parameter'], sources)


def dfpt_definition(value, facts):
    text = ' '.join(e['quote'] for e in facts)
    return compact(scalar(value)) == 'dft' and bool(
        re.search(r'\bdfpt\b', normalized(text)) or 'densityfunctionalperturbation' in compact(text))


def functional_candidate_allowed(candidate, record, candidates, facts, scopes=()):
    path, value, stage = candidate.get('target_path', ''), candidate.get('value'), candidate.get('stage')
    functional = path.endswith('/exchange_correlation_functional') or (
        isinstance(value, dict) and str(value.get('key', '')).endswith('.exchange_correlation_functional'))
    if candidate.get('inference_rule') == 'vasp_pbe_to_qe_v1':
        return False
    if not functional:
        return True
    conditions = (record.get('payload') or {}).get('calculation_conditions') or {}
    software = conditions.get('calculation_code') if stage == 'electron_phonon' else next(
        (scalar(e) for e in conditions.get('extensions') or [] if e.get('key') == stage + '.calculation_code'), None)
    if not software:
        software = next((scalar(c.get('value')) for c in candidates if c.get('target') == candidate.get('target')
            and c.get('stage') == stage and (c.get('target_path', '').endswith('/calculation_code') or
            isinstance(c.get('value'), dict) and c['value'].get('key') == stage + '.calculation_code')), None)
    return bool(software) and reported_for_software(value, software, [*facts, *scopes])


def remove_unreported_generated_conditions(extraction):
    """仅用于新提取候选；缺少所引原文依据的已知条件不冒充直接事实。"""
    for state in extraction.get('material_states') or []:
        for module in state.get('property_modules') or []:
            for record in module.get('records') or []:
                conditions = (record.get('payload') or {}).get('calculation_conditions') or {}
                sources = [e for e in [*record.get('evidences', []), *state.get('evidences', [])]
                           if isinstance(e, dict) and e.get('quote')]
                programs = {'electron_phonon': conditions.get('calculation_code')}
                for item in conditions.get('extensions') or []:
                    key = str(item.get('key') or '')
                    if key.endswith('.calculation_code'):
                        programs[key.split('.', 1)[0]] = scalar(item)
                def reported(parameter, value, stage):
                    if parameter not in PARAMETERS:
                        return True
                    if parameter == 'calculation_code':
                        return any(software_in_text(scalar(value), e['quote']) for e in sources)
                    if not value_matches(value, parameter, sources):
                        return False
                    if parameter in {'exchange_correlation_functional', 'electronic_method', 'energy_cutoff',
                                     'charge_density_cutoff', 'convergence_energy', 'convergence_force'}:
                        if not programs.get(stage) and parameter != 'exchange_correlation_functional':
                            # 原文报告的值仍保留；未知软件会在自动核对时阻止通过，不等同于未报告值。
                            return True
                        return reported_for_software(value, programs.get(stage), sources)
                    return True
                for key in list(conditions):
                    if key in PARAMETERS and conditions[key] not in (None, '') and not reported(key, conditions[key], 'electron_phonon'):
                        conditions[key] = None
                if 'extensions' in conditions:
                    conditions['extensions'] = [e for e in conditions['extensions'] if '.' not in str(e.get('key') or '')
                        or reported(str(e['key']).split('.', 1)[1], e, str(e['key']).split('.', 1)[0])]
