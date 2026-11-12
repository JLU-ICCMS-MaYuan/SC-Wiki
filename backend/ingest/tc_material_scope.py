"""#211：全文判断仅范围Tc材料的收录范围，程序只核验身份和来源。"""
from copy import deepcopy
import json

VERSION = 'current-paper-structures-v2'
PROMPT = '''Also inventory ALL current-paper materials with reported Tc in tc_materials. This is a
BACKEND AUDIT list, NOT the scientific form. Include BOTH retained AND excluded materials; never omit
a material from tc_materials because its Tc cannot become a numeric form record. In a shared statement listing
several materials with a common Tc bound/range, create one audit entry for EACH named material.
For each material
give its chemical formula (or exact reported name), has_specific_tc, has_range_tc, source_ids and reason.
A specific Tc includes a reported approximate numeric value and explicitly paired Tc/mu_star points.
A calibrated original-figure reading with its own material/series/conditions and declared reading
precision is a specific approximate Tc; include it BEFORE range-only exclusion. A shared textual
maximum is not each material's detailed point. A range, upper/lower bound, an UNREAD curve alone
or guessed endpoints without calibrated figure evidence is not a specific Tc.
has_range_tc is true ONLY for an explicitly reported NUMERICAL Tc interval or inequality in the
current-paper text. A Tc figure/caption WITHOUT readable reported numbers is NOT a numerical range:
set BOTH flags false and retain the material. Do not infer a Tc range from a plot, a pressure/stability
interval, a general high-Tc statement or another paper's results. Missing Tc is not range-only Tc.
Read all body and SI windows. A range-only Tc must not become a numeric Tc record. Preserve all
current-paper structures independently of whether a concrete Tc was reported. If any window reports
a specific Tc, preserve that point. Do not exclude materials merely because Tc is absent.
Keep different materials distinct. Other papers' Tc does not qualify. Preserve source-backed reasons;
empty tc_materials means this window has no such reported Tc, not that all materials are excluded.'''
PROMPT += '''
Current collection policy separates Tc values from structures: preserve EVERY crystal geometry
actually studied in the current paper/body/SI, including materials with no Tc or only a Tc bound.
Range-only Tc is not a numeric Tc point. Preserve its original expression and sources in this audit.
Do not collect structures merely cited from other works; introduction location alone does not decide
this relationship, because it may also describe this paper's own contributions.
'''


def material_key(value):
    from backend.db_helpers import normalize_formula
    value = str(value or '').strip()
    if not value:
        return ''
    try:
        return 'formula:' + normalize_formula(value)[0]
    except ValueError:
        return 'name:' + value.casefold()


def collect_scope(reports, sources):
    """所有已读窗口中的具体值均保留，汇总响应不能覆盖它。"""
    materials = {}
    for report in reports:
        entries = report.get('tc_materials', [])
        if not isinstance(entries, list):
            raise ValueError('材料收录范围格式无效')
        for entry in entries:
            key = material_key(entry.get('material'))
            ids = entry.get('source_ids')
            if (not key or not isinstance(ids, list) or not ids
                    or any(not isinstance(i, str) or i not in sources for i in ids)
                    or type(entry.get('has_specific_tc')) is not bool
                    or type(entry.get('has_range_tc')) is not bool
                    or not str(entry.get('reason') or '').strip()):
                raise ValueError('材料收录范围缺少实际原文或明确判断')
            item = materials.setdefault(key, dict(material=entry['material'], material_key=key,
                has_specific_tc=False, has_range_tc=False, reasons=[], evidences=[]))
            for flag in ('has_specific_tc', 'has_range_tc'):
                item[flag] |= entry[flag]
            if entry['reason'] not in item['reasons']:
                item['reasons'].append(entry['reason'])
            for source_id in ids:
                source = sources[source_id]
                evidence = {k: deepcopy(source.get(k)) for k in
                    ('file_id', 'file_role', 'chunk_index', 'page_start', 'page_end', 'content')}
                if evidence not in item['evidences']:
                    item['evidences'].append(evidence)
    values = list(materials.values())
    return dict(rule_version=VERSION, materials=values, excluded_materials=[
        deepcopy(m) for m in values if m['has_range_tc'] and not m['has_specific_tc']])


def is_excluded(material, scope, *, purpose='tc'):
    if purpose == 'structure' and (scope or {}).get('rule_version') == VERSION:
        return False
    key = material_key(material)
    return bool(key) and any(key == material_key(item.get('material'))
        for item in (scope or {}).get('excluded_materials', []))


def assert_allowed(states, scope, *, purpose='form'):
    for state in states:
        if state.get('scope') == 'referenced_work':
            continue
        if (scope or {}).get('rule_version') == VERSION:
            if purpose == 'structure' or not is_excluded(state.get('material'), scope):
                continue
            records = [*(state.get('tc_results') or []), *[r for m in state.get('property_modules') or []
                for r in m.get('records') or [] if r.get('record_type') in {'predicted_tc', 'measured_tc'}]]
            if not any(any(r.get(k) is not None and r.get(k) != '' for k in
                ('value_number', 'value_min', 'value_max', 'value_raw', 'value_text')) for r in records):
                continue
        if is_excluded(state.get('material'), scope):
            message = ('仅范围Tc不得补造具体Tc；本文结构仍应保留：' if (scope or {}).get('rule_version') == VERSION
                       else '已按整篇原文排除的仅范围Tc材料不能重新进入表单：')
            raise ValueError(message + state['material'])


def scope_prompt(scope, *, purpose='form'):
    if (scope or {}).get('rule_version') == VERSION:
        if purpose == 'structure':
            return ('\nCURRENT-PAPER STRUCTURE POLICY v2: retain all structures actually studied in the '
                'current paper/body/SI regardless of absent/range-only Tc. Do not import reference-only '
                'structures. Judge the currently supplied original file and registered read-only tools; '
                'Tc range audit text is not a source of coordinates, file identity or page identity.\n')
        excluded = (scope or {}).get('excluded_materials') or []
        # 整篇审计保留原文；当前片段只接收范围结论，不把别窗正文伪装成可引用输入。
        audit = [{'material': e['material'], 'has_specific_tc': e.get('has_specific_tc'),
                  'has_range_tc': e.get('has_range_tc'), 'reasons': e.get('reasons', []),
                  'source_refs': [{k: source.get(k) for k in
                      ('file_id', 'file_role', 'chunk_index', 'page_start', 'page_end')}
                      for source in e.get('evidences', [])]} for e in excluded]
        return ('\nCURRENT-PAPER STRUCTURE POLICY v2: retain all structures actually studied in this '
            'body/SI regardless of absent/range-only Tc. Do not import reference-only structures. '
            'Range-only materials cannot acquire invented Tc points; preserve original bounds and sources. '
            + ('For each material listed below, emit NO predicted_tc/measured_tc record, including '
               'range or upper-bound records. Its original Tc bound remains in this whole-paper audit '
               'and source-backed coverage_exclusions, NOT property_modules. Retain studied structures '
               'and independently supported non-Tc records. This list is whole-paper decision metadata; '
               'source_refs are provenance locations, not currently read blocks. Only the supplied '
               'Document IR pages provide source IDs for this extraction. ' if excluded and purpose == 'form' else '') +
            'A calibrated material/condition-specific graph point remains a specific approximate Tc.\n' +
            json.dumps(audit, ensure_ascii=False))
    excluded = (scope or {}).get('excluded_materials') or []
    if not excluded:
        return ''
    return ('\nWHOLE-PAPER MATERIAL SCOPE: The following materials report ONLY range/bounds Tc '
        'and no specific Tc anywhere in the current body/SI. Do not extract their scientific records, '
        'structures or create form states. Do not substitute a bound as a numeric Tc or invent an endpoint. '
        'For their original text retain out_of_model_scope coverage exclusions with the reason '
        'range-only Tc material excluded by the confirmed collection policy. Do not apply this exclusion '
        'to other materials or discard their specific Tc. This scope takes precedence over general '
        'instructions to preserve all structures or ranges.\n' + json.dumps(
            [{'material': e['material'], 'reasons': e.get('reasons', [e.get('reason')])} for e in excluded],
            ensure_ascii=False))
