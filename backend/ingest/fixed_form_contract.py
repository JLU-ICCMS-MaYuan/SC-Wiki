"""#203：经审查的科学字段；生产校验与显式旧数据转换分别处理。"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

DATA = Path(__file__).resolve().parents[1] / 'data'
CONTRACT = json.loads((DATA / 'scientific_form_contract.v1.json').read_text())
LOCK = json.loads((DATA / 'scientific_form_contract.lock.json').read_text())
if hashlib.sha256((DATA / 'scientific_form_contract.v1.json').read_bytes()).hexdigest() != LOCK['sha256']:
    raise RuntimeError('科学字段契约与已审查基线不一致；请先完成Issue/Spec变更审查')
VERSION = CONTRACT['version']
COMMON = frozenset(CONTRACT['condition_fields'])
SOFTWARE = CONTRACT['software']
RETIRED_PRESSURE = frozenset(CONTRACT['retired_state_fields'])
PARAMETERS = frozenset(key for fields in SOFTWARE.values() for key in fields)
VALUE_FIELDS = frozenset(CONTRACT['quantity_fields'])


class FormContractError(ValueError):
    def __init__(self, field, message):
        self.field = field
        super().__init__(f'{field}：{message}')


def validate_common_value(scope, key, value):
    fields = CONTRACT['paper_fields'] if scope == 'paper' else {**CONTRACT['state_fields'], **CONTRACT['state_scientific_fields']}
    if key not in fields:
        # 稳定身份、模块和内部元数据由各自既有契约处理。
        return
    if value is None:
        return
    kind = fields[key]
    if kind == 'enum' and value not in CONTRACT['enums'][key]:
        raise FormContractError(key, '枚举值未登记或已退役')
    if kind == 'text' and not isinstance(value, str):
        raise FormContractError(key, '必须是文本')
    if kind == 'text[]' and (not isinstance(value, list) or not all(isinstance(item, str) for item in value)):
        raise FormContractError(key, '必须是文本列表')
    if kind == 'selection[]' and not isinstance(value, list):
        raise FormContractError(key, '必须是分类选择列表')
    if kind.startswith('number:') or kind == 'integer':
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or kind == 'integer' and not float(value).is_integer():
            raise FormContractError(key, '数值或整数类型无效')
    if key == 'element_count' and not 1 <= value <= 118:
        raise FormContractError(key, '元素种类数须为1至118')
    if key == 'reported_space_group_number' and not 1 <= value <= 230:
        raise FormContractError(key, '空间群号须为1至230')
    if kind == 'structure' and (not isinstance(value, dict) or set(value) - set(CONTRACT['structure_fields'])):
        raise FormContractError(key, '结构对象类型或子键未登记')


def software_key(value):
    text = re.sub(r'[^a-z0-9]', '', str(value or '').casefold())
    matches = []
    if 'quantumespresso' in text or text in {'qe', 'pwscf'}:
        matches.append('qe')
    if 'epw' in text:
        matches.append('epw')
    if 'sscha' in text:
        matches.append('sscha')
    return matches[0] if len(matches) == 1 else None


def validate_value(value, path):
    if value is None:
        return
    if isinstance(value, bool):
        raise FormContractError(path, '标准计算参数不能填写布尔值')
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or value < 0:
            raise FormContractError(path, '计算参数必须是非负有限数值')
        if path.endswith('.atoms') and not float(value).is_integer():
            raise FormContractError(path, '原子数必须是整数')
        return
    if isinstance(value, str):
        return
    if isinstance(value, list):
        if not path.endswith(('.k_grid', '.q_grid', '.q_grid_interpolated', '.supercell', '.temperature_k')):
            raise FormContractError(path, '该参数不接受数组')
        for item in value:
            validate_value(item, path)
        return
    if not isinstance(value, dict):
        raise FormContractError(path, '计算参数类型无效')
    unknown = set(value) - VALUE_FIELDS
    if unknown:
        raise FormContractError(path, '未登记的参数子键：' + ', '.join(sorted(unknown)))
    if value.get('value_kind') not in {None, 'number', 'range', 'text'}:
        raise FormContractError(path, '标准计算参数只接受文本、数值或范围')
    if value.get('value_kind') == 'number' and str(value.get('value_raw') or '').strip() and value.get('value_number') is None:
        raise FormContractError(path, '请输入完整有效的数值')
    for key in ('value_number', 'value_min', 'value_max'):
        if value.get(key) is not None:
            if type(value[key]) not in (int, float):
                raise FormContractError(path + '.' + key, '必须是数值，不能嵌套对象或文本')
            validate_value(value[key], path)
    if value.get('value_min') is not None and value.get('value_max') is not None and value['value_min'] > value['value_max']:
        raise FormContractError(path, '范围下界不能大于上界')
    for key in ('value_raw', 'value_text', 'unit_raw'):
        if value.get(key) is not None and not isinstance(value[key], str):
            raise FormContractError(path + '.' + key, '必须是文本')


def validate_conditions(conditions, *, model_output=False):
    if conditions is None:
        return
    if not isinstance(conditions, dict):
        raise FormContractError('calculation_conditions', '必须是对象')
    allowed = COMMON | set(SOFTWARE) | {'extensions', 'field_settings'}
    unknown = set(conditions) - allowed
    if unknown:
        raise FormContractError('calculation_conditions', '未登记或已退役的字段：' + ', '.join(sorted(unknown)))
    for key in COMMON:
        if conditions.get(key) is not None and not isinstance(conditions[key], str):
            raise FormContractError('calculation_conditions.' + key, '必须是文本')
    for name, fields in SOFTWARE.items():
        group = conditions.get(name)
        if group is None:
            continue
        if not isinstance(group, dict):
            raise FormContractError('calculation_conditions.' + name, '软件参数必须是对象')
        for key, value in group.items():
            if key not in fields:
                raise FormContractError(f'calculation_conditions.{name}.{key}', '不是该软件已审定的参数')
            validate_value(value, f'calculation_conditions.{name}.{key}')
            if isinstance(value, dict) and key == 'temperature_k' and value.get('unit_raw') not in (None, '', 'K', 'kelvin'):
                raise FormContractError(f'calculation_conditions.{name}.{key}', 'temperature_k须使用K；原始单位请保留在原文依据')
    extensions = conditions.get('extensions', [])
    if not isinstance(extensions, list):
        raise FormContractError('calculation_conditions.extensions', '必须是数组')
    if model_output and extensions:
        raise FormContractError('calculation_conditions.extensions', '模型不能创建人工扩展或阶段字段')
    if model_output and conditions.get('field_settings'):
        raise FormContractError('calculation_conditions.field_settings', '模型不能伪造人工字段设置')
    if conditions.get('field_settings') is not None and not isinstance(conditions['field_settings'], dict):
        raise FormContractError('calculation_conditions.field_settings', '字段设置必须是对象')
    for index, item in enumerate(extensions):
        path = f'calculation_conditions.extensions.{index}'
        if not isinstance(item, dict) or not item.get('field_key') or not str(item.get('name_raw') or item.get('name') or '').strip():
            raise FormContractError(path, '人工扩展必须有稳定身份和名称')
        if set(item) - set(CONTRACT['manual_extension_fields']):
            raise FormContractError(path, '人工扩展包含未登记子键')
        if item.get('key') in COMMON or str(item.get('key') or '').startswith(tuple(name + '.' for name in SOFTWARE)):
            raise FormContractError(path, '不能以人工扩展重复定义标准字段')


def parameter_paths(conditions):
    """返回当前值/空值均可定位的固定科学叶子，不扫描整稿。"""
    for key in CONTRACT['condition_fields']:
        yield key, (conditions or {}).get(key)
    for software, fields in SOFTWARE.items():
        group = (conditions or {}).get(software) or {}
        for key in fields:
            yield software + '.' + key, group.get(key)


def _quantity(item):
    return {key: deepcopy(value) for key, value in item.items() if key in VALUE_FIELDS}


def _equivalent(left, right):
    def normalized(value):
        if not isinstance(value, dict):
            return (str(value).strip().replace('×', 'x').replace(' ', ''), '')
        content = next((value[key] for key in ('value_number', 'value_text', 'value_raw') if value.get(key) is not None), None)
        if value.get('value_kind') == 'range':
            content = [value.get('value_min'), value.get('value_max')]
        return (str(content).strip().replace('×', 'x').replace(' ', ''), str(value.get('unit_raw') or '').strip())
    if left == right:
        return True
    a, b = normalized(left), normalized(right)
    return a[0] == b[0] and (a[1] == b[1] or not a[1] or not b[1])


def convert_conditions(before, *, resolutions=None):
    """仅供明确迁移/旧版边界；冲突抛错，绝不在新模型入口调用。"""
    if before is None:
        return None, {}
    if not isinstance(before, dict):
        raise FormContractError('calculation_conditions', '旧条件不是对象')
    original = deepcopy(before)
    unknown = set(original) - (COMMON | set(SOFTWARE) | PARAMETERS | {'extensions', 'field_settings', 'method_scope'})
    if unknown:
        raise FormContractError('calculation_conditions', '旧数据包含未登记字段：' + ', '.join(sorted(unknown)))
    result = {key: deepcopy(value) for key, value in original.items() if key in COMMON or key in SOFTWARE or key == 'field_settings'}
    moves = {}
    primary = software_key(original.get('calculation_code'))
    def put(path, value, old_path):
        keys = path.split('.')
        parent = result
        for key in keys[:-1]:
            parent = parent.setdefault(key, {})
        if parent.get(keys[-1]) is not None and not _equivalent(parent[keys[-1]], value):
            decision = (resolutions or {}).get(path) or {}
            expected = decision.get('expected_values') or []
            selected = decision.get('value')
            if (path != 'phonon_method' or not decision.get('source_verified') or not decision.get('evidences')
                    or expected != [parent[keys[-1]], value] or selected not in expected):
                raise FormContractError(path, '新旧值或单位冲突，拒绝自动选择')
            parent[keys[-1]] = deepcopy(selected)
        if parent.get(keys[-1]) is None:
            parent[keys[-1]] = deepcopy(value)
        moves[old_path] = path
    for key in PARAMETERS & set(original):
        if original[key] is None:
            continue
        if primary is None or key not in SOFTWARE[primary]:
            raise FormContractError(key, '无法确定旧参数所属软件')
        put(primary + '.' + key, original[key], key)
    manual = []
    extensions = original.get('extensions') or []
    if not isinstance(extensions, list):
        raise FormContractError('extensions', '旧扩展必须是数组')
    for index, item in enumerate(extensions):
        key = str(item.get('key') or '')
        stage, _, parameter = key.partition('.')
        old_path = 'extensions.' + str(index)
        if stage in {'structural_relaxation', 'structure_relaxation', 'aimd'}:
            moves[old_path] = None
            continue
        if parameter in COMMON and stage in {'electron_phonon', 'superconductivity'}:
            value = item.get('value_text') if item.get('value_text') is not None else item.get('value_raw')
            put(parameter, value, old_path)
        elif stage == 'sscha' and parameter == 'calculation_code':
            moves[old_path] = None
        elif stage in {'electron_phonon', 'superconductivity', 'sscha', 'qe', 'epw'} and parameter in PARAMETERS:
            software = stage if stage in SOFTWARE else primary
            if software is None or parameter not in SOFTWARE[software]:
                raise FormContractError(key, '无法确定旧阶段参数所属软件')
            put(software + '.' + parameter, _quantity(item), old_path)
        elif item.get('field_key') and str(item.get('name_raw') or '').strip():
            manual.append(deepcopy(item))
            moves[old_path] = 'extensions.' + str(len(manual) - 1)
        else:
            raise FormContractError(key or old_path, '未登记旧扩展，需明确处理，不能伪装人工创建')
    display = result.get('field_settings') or {}
    for old, new in moves.items():
        if old not in display:
            continue
        if new is None:
            display.pop(old, None)
        elif new != old:
            if new in display and display[new] != display[old]:
                raise FormContractError('field_settings.' + new, '新旧人工标注冲突')
            display[new] = display.pop(old)
    if manual or 'extensions' in original:
        result['extensions'] = manual
    validate_conditions(result)
    return result, moves


def convert_record(record, *, resolutions=None):
    result = deepcopy(record)
    payload = result.get('payload') or {}
    if 'calculation_conditions' not in payload:
        return result
    conditions, moves = convert_conditions(payload['calculation_conditions'], resolutions=resolutions)
    payload['calculation_conditions'] = conditions
    for association in payload.get('source_associations') or []:
        path = str(association.get('target_path') or '')
        base = '/payload/calculation_conditions/'
        if not path.startswith(base):
            continue
        relative = path[len(base):].replace('/', '.')
        for old in sorted(moves, key=len, reverse=True):
            if relative == old or relative.startswith(old + '.'):
                new = moves[old]
                if new is not None:
                    association['target_path'] = base + new.replace('.', '/')
                    association.pop('field_binding', None)
                    association.pop('target_fingerprint', None)
                else:
                    association['_retired_contract_path'] = True
                break
    if 'source_associations' in payload:
        payload['source_associations'] = [a for a in payload['source_associations'] if not a.pop('_retired_contract_path', False)]
    result['payload'] = payload
    return result


def validate_model_record(record):
    """只接受已登记科学项目，模型不能借开放payload生成另一份表单。"""
    payload = record.get('payload') or {}
    if not isinstance(payload, dict):
        raise FormContractError('payload', '必须是对象')
    code = record.get('property_code')
    stability = record.get('module_code') == 'thermodynamical_properties' and isinstance(payload.get('thermodynamic_stability'), dict)
    if code not in CONTRACT['standard_properties'] and not (code == 'custom' and stability):
        raise FormContractError('property_code', '不是本套表单已审定的科学项目')
    allowed = {'parameters', 'calculation_conditions', 'thermodynamic_stability', 'source_associations',
               'table_row_ref', 'method_variant_status'}
    if set(payload) - allowed:
        raise FormContractError('payload', '模型输出了未登记科学字段：' + ', '.join(sorted(set(payload) - allowed)))
    validate_conditions(payload.get('calculation_conditions'), model_output=True)
    parameters = payload.get('parameters') or {}
    if not isinstance(parameters, dict) or set(parameters) - {'lambda_ep', 'omega_log', 'mu_star', 'extensions'}:
        raise FormContractError('parameters', '模型不能创建参数键或人工设置')
    for item in parameters.get('extensions') or []:
        if item.get('key') not in {'mu_star', 'mu_star_reported_range', 'mu_star_reported', 'lambda_ep_reported', 'omega_log_reported'}:
            raise FormContractError('parameters.extensions', '模型不能创建人工扩展')
    if stability:
        value = payload['thermodynamic_stability']
        if set(value) - set(CONTRACT['thermodynamic_fields']):
            raise FormContractError('thermodynamic_stability', '热力学子字段未登记')
        for key, case in (value.get('cases') or {}).items():
            if key not in {'formation_energy', 'formation_enthalpy', 'formation_gibbs', 'unspecified'} or not isinstance(case, dict) or set(case) - set(CONTRACT['thermodynamic_case_fields']):
                raise FormContractError('thermodynamic_stability.cases', '判据或子字段未登记')


def conditions_schema():
    """已发布定义和前端的同一白名单；历史定义保持不变。"""
    quantity = {'type': 'object', 'additionalProperties': False,
                'properties': {key: {} for key in CONTRACT['quantity_fields']}}
    value = {'anyOf': [{'type': 'null'}, {'type': 'string'}, {'type': 'number', 'minimum': 0},
                       {'type': 'array', 'items': {'type': 'number', 'minimum': 0}}, quantity]}
    fields = {key: {'type': ['string', 'null'], 'title': label} for key, label in CONTRACT['condition_fields'].items()}
    for software, keys in SOFTWARE.items():
        fields[software] = {'type': ['object', 'null'], 'additionalProperties': False,
                            'title': CONTRACT['software_labels'][software],
                            'properties': {key: {**deepcopy(value), 'title': CONTRACT['labels'][key]} for key in keys}}
    fields['extensions'] = {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
        'properties': {key: {} for key in CONTRACT['manual_extension_fields']}, 'required': ['field_key', 'name_raw']}}
    fields['field_settings'] = {'type': 'object'}
    return {'type': 'object', 'additionalProperties': False, 'properties': fields}


def payload_schema():
    fields = {key: {} for key in CONTRACT['payload_fields']}
    fields['calculation_conditions'] = conditions_schema()
    return {'type': 'object', 'additionalProperties': False, 'properties': fields}


def finalize_current_draft(draft, *, model_output=False, legacy=False):
    """所有组装/补全完成后封口；派生组装器不能重新带回退役字段。"""
    draft['_form_contract_version'] = VERSION
    for state in draft.get('material_states') or []:
        for key in RETIRED_PRESSURE:
            state.pop(key, None)
        for module in state.get('property_modules') or []:
            for record in module.get('records') or []:
                if record.get('property_code') == 'band_gap' or record.get('record_type') == 'measured_tc':
                    continue
                payload = record.get('payload') or {}
                if legacy and 'calculation_conditions' in payload:
                    payload['calculation_conditions'], _ = convert_conditions(payload['calculation_conditions'])
                validate_conditions(payload.get('calculation_conditions'), model_output=model_output)
                record['definition_version'] = max(2, int(record.get('definition_version') or 1))
    return draft


MODEL_PROMPT = '''
FIXED SCIENTIFIC FORM CONTRACT v1 (#203): Use ONLY the following calculation_conditions fields:
calculation_code, electronic_method, exchange_correlation_functional, phonon_method,
vibrational_treatment, qe, epw, sscha. phonon_method is a DIRECT string field, NEVER an extension.
Each software group uses its separately declared parameter keys. Preserve reported values and units.
Never emit method_scope, structural_relaxation/structure_relaxation parameters, arbitrary extension
keys, manual field_settings, human-origin flags, or custom property types. VASP structural relaxation
settings do not belong to superconducting calculation conditions. Do not infer QE PBE from VASP.
Use each field's actual source to establish software/material/result applicability.
Missing or unused software parameters remain null/empty, never guessed or copied across groups.
'''.strip() + '\nSOFTWARE PARAMETER KEYS: ' + json.dumps(SOFTWARE)
