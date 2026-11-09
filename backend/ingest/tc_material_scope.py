"""#211：全文判断仅范围Tc材料的收录范围，程序只核验身份和来源。"""
from copy import deepcopy
import json

VERSION = 'specific-tc-materials-v1'
PROMPT = '''Also inventory ALL current-paper materials with reported Tc in tc_materials. This is a
BACKEND AUDIT list, NOT the scientific form. Include BOTH retained AND excluded materials; never omit
a material from tc_materials because it will be excluded from the form. In a shared statement listing
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
Read all body and SI windows. A material is excluded from specialized extraction and the form ONLY
when the whole paper/SI reports range/bounds Tc and NO specific Tc for that material. If any window
reports a specific Tc, preserve that material. Do not exclude materials merely because Tc is absent.
Keep different materials distinct. Other papers' Tc does not qualify. Preserve source-backed reasons;
empty tc_materials means this window has no such reported Tc, not that all materials are excluded.'''


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


def is_excluded(material, scope):
    key = material_key(material)
    return bool(key) and any(key == material_key(item.get('material'))
        for item in (scope or {}).get('excluded_materials', []))


def assert_allowed(states, scope):
    for state in states:
        if is_excluded(state.get('material'), scope):
            raise ValueError('已按整篇原文排除的仅范围Tc材料不能重新进入表单：' + state['material'])


def scope_prompt(scope):
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
