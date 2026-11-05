"""空值资格由字段schema和必要父级规则决定，不能用当前populated标记冒充必填。"""
import re


def is_empty(value):
    if value is None:return True
    if isinstance(value,str):return not value.strip()
    return isinstance(value,(list,dict)) and not value


def allowed(record,context=None):
    from .evidence_proposals import valid_value,VALUE_SLOTS
    field=record.get('field','')
    if field in {'paper.title','paper.year','paper.paper_type','paper.superconductor_kind',
                 'paper.material_families','paper.research_materials'}:
        return False
    if record.get('kind') in {'derived','structure','structure_issue'} or record.get('structure_field'):
        return False
    if context is None and 'empty_allowed' in record:
        return bool(record['empty_allowed'])  # 来自本次服务端完整字段投影，不读取客户端声明。
    context=context or {}
    if field=='paper.theoretical_subtype' and (context.get('paper') or {}).get('paper_type')=='theoretical':
        return False
    state_match=re.fullmatch(r'material_states\[(\d+)\]\.([a-z_]+)',field)
    if state_match:
        index,name=int(state_match[1]),state_match[2]
        states=context.get('material_states') or []
        state=states[index] if index<len(states) else (record.get('claim') or {}).get('context') or {}
        if name in {'state_kind','structure_optimization','crystal_system','material_dimensionality'}:
            return False
        if name in {'material','material_name'}:
            other='material_name' if name=='material' else 'material'
            if not str(state.get(other) or '').strip():return False
    path=record.get('record_field')
    owner=record.get('scientific_record') or (record.get('claim') or {}).get('record') or {}
    if path in VALUE_SLOTS.get(owner.get('value_kind'),set()) or path in {'name_raw','value_kind','record_type','property_code','definition_key','definition_version'}:
        return False
    if path=='method_code' and owner.get('record_type')=='predicted_tc':
        return False
    editable=record.get('editable_fields') or []
    schema=next((entry['schema'] for entry in editable if entry.get('path')==''),None)
    if schema is None:return False
    return any(valid_value(blank,schema) for blank in (None,'',[],{}))
