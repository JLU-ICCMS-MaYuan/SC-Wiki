"""共享上传路径必须保留用户明确清空的条件，不从旧字段恢复。"""
from backend.ingest.upload_jobs import _normalize_material_states


def test_explicit_empty_pressure_does_not_restore_legacy_conditions():
    fields = ('pressure_value_gpa', 'pressure_min_gpa', 'pressure_max_gpa', 'pressure_raw', 'pressure_unit_raw')
    state = {'material': 'Sn', 'condition': {'pressure': '1-2', 'pressure_unit': 'GPa'}, **dict.fromkeys(fields)}
    saved = _normalize_material_states([state])[0]
    assert all(saved[field] is None for field in fields)


def test_manual_zero_preserves_explicit_missing_original_and_legacy_remains_readable():
    saved = _normalize_material_states([{'material': 'Sn', 'pressure_value_gpa': 0, 'pressure_raw': None, 'pressure_unit_raw': None}])[0]
    assert saved['pressure_value_gpa'] == 0
    assert saved['pressure_raw'] is None and saved['pressure_unit_raw'] is None
    legacy = _normalize_material_states([{'material': 'Sn', 'condition': {'pressure': '1 to 2', 'pressure_unit': 'GPa'}}])[0]
    assert legacy['pressure_min_gpa'] == 1 and legacy['pressure_max_gpa'] == 2
