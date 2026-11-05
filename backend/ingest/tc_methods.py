"""显式方法行的共同语义与逐结果原文分离；不靠同名猜测归属。"""


def field_owns_record(field, record):
    group = field.get('record_group_key')
    if not group:
        return field.get('record_key') == record.get('record_key')
    identity = (record.get('payload') or {}).get('tc_group') or {}
    actual_group = identity.get('group_key') or record.get('tc_group_key') or record.get('record_group_key')
    actual_method = identity.get('method_key') or record.get('tc_method_key') or record.get('record_method_key')
    return actual_group == group and (not field.get('record_method_key') or actual_method == field['record_method_key'])


def method_identity(record):
    code = record.get('method_code')
    group = (record.get('payload') or {}).get('tc_group') or {}
    name = group.get('method_name')
    if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 180):
        raise ValueError('Tc 共同方法名称无效')
    # 有明确组/方法引用时，归属由已有整理及来源核对建立，不再按原文写法重新判同。
    # 历史共同名称保持可读；无显式身份的旧记录仍保留各自名称，不能因枚举相同合并。
    explicit = bool(group.get('group_key') and group.get('method_key'))
    if code not in {'other', 'unknown'}:
        return code, None
    if name is not None:
        return code, name
    return code, None if explicit else record.get('method_raw')


def method_review_identity(record):
    code, name = method_identity(record)
    group = (record.get('payload') or {}).get('tc_group') or {}
    return {'method_code': code, 'method_name': name,
            'group_key': group.get('group_key'), 'method_key': group.get('method_key')}


def write_method_value(record, field, value):
    """方法行修正共同含义，已有逐结果原文不被建议或人工输入覆盖。"""
    group = (record.get('payload') or {}).get('tc_group')
    if field == 'method_raw' and group:
        group['method_name'] = value
        if not record.get('method_raw'):
            record['method_raw'] = value
    else:
        if field == 'method_code' and group and record.get(field) != value:
            group.pop('method_name', None)
        record[field] = value
