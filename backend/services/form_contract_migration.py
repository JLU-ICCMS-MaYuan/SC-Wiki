"""#203/#204显式数据转换；预检失败时不写入，也不修改冻结快照。"""
from copy import deepcopy
import json
import os
from pathlib import Path

from backend.ingest.fixed_form_contract import convert_record, FormContractError, RETIRED_PRESSURE, payload_schema


def require_explicit_migration(bind):
    # 防止共享工作区中其他任务的upgrade heads误执行本次业务迁移。
    if bind.engine.url.database == 'scwiki' and os.environ.get('SCWIKI_APPROVED_CONTRACT_MIGRATION') != '203,204':
        raise RuntimeError('203/204业务迁移须通过已预检的专用本机迁移入口执行')


def convert_draft(draft, *, structures=False, identity='', resolutions=None):
    from backend.ingest.tc_contexts import map_draft
    result = map_draft(deepcopy(draft))
    for state in result.get('material_states') or []:
        lower, upper, scalar = (state.get(key) for key in ('pressure_min_gpa', 'pressure_max_gpa', 'pressure_value_gpa'))
        if lower is not None or upper is not None:
            if scalar is None and lower is not None and upper is not None and float(lower) == float(upper):
                state['pressure_value_gpa'] = lower
            elif scalar is None or lower is not None and float(scalar) < float(lower) or upper is not None and float(scalar) > float(upper):
                raise FormContractError('pressure_value_gpa', '旧压力范围不能无损转为已报告单值')
        for key in RETIRED_PRESSURE:
            state.pop(key, None)
        for module in state.get('property_modules') or []:
            records = []
            for record in module.get('records') or []:
                if record.get('property_code') == 'band_gap' or record.get('record_type') == 'measured_tc':
                    records.append(deepcopy(record))
                    continue
                decision = (resolutions or {}).get(identity + ':' + record.get('record_key', ''))
                if decision:
                    context = {'material': state.get('material'), 'material_name': state.get('material_name'),
                               'pressure_value_gpa': state.get('pressure_value_gpa'), 'method': record.get('method_code'),
                               'tc': record.get('value_number')}
                    for field_decision in decision.values():
                        if field_decision.get('expected_context') != context:
                            raise FormContractError('phonon_method', '来源核对后目标上下文发生变化')
                item = convert_record(record, resolutions=decision)
                item['definition_version'] = max(2, int(item.get('definition_version') or 1))
                records.append(item)
            module['records'] = records
    if structures:
        from backend.ingest.canonical_structure import assign_structures
        from backend.services.structure_candidates import validate_structure_text, read_atoms, export_representations
        for state in result.get('material_states') or []:
            structure = state.get('structure') or {}
            if structure.get('structure_text'):
                fmt, content = structure.get('structure_format') or 'cif', structure['structure_text']
                parsed = validate_structure_text(fmt, content)
                structure['validation'] = parsed
                structure.setdefault('structure_hash', parsed['structure_hash'])
                structure['representations'] = export_representations(read_atoms(fmt, content))
                from backend.ingest.canonical_structure import structure_metadata
                structure.update(structure_metadata(structure))
        candidates = deepcopy(result.get('structure_candidates') or [])
        assign_structures(result, candidates)
    result['_form_contract_version'] = 1
    return map_draft(result, compact=True)


def _decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def prepare_changes(bind, *, structures=False):
    """先计算所有目标行；冲突会在任何UPDATE/DDL之前抛出。"""
    import sqlalchemy as sa
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    changes = []
    resolution_path = os.environ.get('SCWIKI_FORM_CONTRACT_RESOLUTIONS')
    resolutions = json.loads(Path(resolution_path).read_text()) if resolution_path else {}
    for name, column in [('scientific_work_drafts', 'body'), ('scientific_upload_drafts', 'draft'),
                         ('scientific_review_drafts', 'draft'), ('paper_revision_drafts', 'draft')]:
        if name not in tables:
            continue
        table = sa.Table(name, sa.MetaData(), autoload_with=bind)
        if column not in table.c:
            continue
        query = sa.select(table)
        if name == 'paper_revision_drafts' and 'submitted_revision' in table.c:
            query = query.where(table.c.submitted_revision.is_(None))
        for row in bind.execute(query).mappings():
            before = _decoded(row[column])
            if not isinstance(before, dict) or 'material_states' not in before:
                continue
            identity = name + ':' + ':'.join(str(row[key.name]) for key in table.primary_key)
            after = convert_draft(before, structures=structures, identity=identity, resolutions=resolutions)
            if before != after:
                values = {column: after}
                if name == 'scientific_work_drafts':
                    import uuid
                    values.update(revision=row['revision'] + 1, write_epoch=uuid.uuid4().hex)
                changes.append((table, {key.name: row[key.name] for key in table.primary_key}, values))
    if not structures and 'property_records' in tables:
        table = sa.Table('property_records', sa.MetaData(), autoload_with=bind)
        papers = sa.Table('papers', sa.MetaData(), autoload_with=bind)
        query = sa.select(table).join(papers, sa.and_(table.c.paper_id == papers.c.id, table.c.paper_revision == papers.c.content_revision))
        from backend.ingest.property_modules import record_checksum
        for row in bind.execute(query).mappings():
            if row['property_code'] == 'band_gap' or row['record_type'] == 'measured_tc':
                continue
            record = dict(row)
            record['payload'] = _decoded(row['payload_json']) or {}
            after = convert_record(record, resolutions=resolutions.get('property_records:' + str(row['id'])))
            values = {'payload_json': after['payload'], 'definition_version': max(2, row['definition_version'])}
            after['definition_version'] = values['definition_version']
            values['record_checksum'] = record_checksum(after)
            if values['payload_json'] != record['payload'] or values['definition_version'] != row['definition_version']:
                changes.append((table, {'id': row['id']}, values))
        modules = sa.Table('property_modules', sa.MetaData(), autoload_with=bind)
        if 'metadata_json' in modules.c:
            from backend.ingest.fixed_form_contract import convert_conditions
            query = sa.select(modules).join(papers, sa.and_(modules.c.paper_id == papers.c.id, modules.c.paper_revision == papers.c.content_revision))
            for row in bind.execute(query).mappings():
                before = _decoded(row['metadata_json']) or {}
                after = deepcopy(before)
                for group in ((after.get('tc_contexts') or {}).get('groups') or {}).values():
                    if 'calculation_conditions' in group:
                        group['calculation_conditions'], _ = convert_conditions(group['calculation_conditions'])
                if after != before:
                    changes.append((modules, {'id': row['id']}, {'metadata_json': after}))
    return changes


def apply_changes(bind, changes):
    import sqlalchemy as sa
    for table, identity, values in changes:
        if table.name == 'property_records' and values.get('definition_version'):
            definitions = sa.Table('form_definitions', sa.MetaData(), autoload_with=bind)
            key = bind.execute(sa.select(table.c.definition_key).where(table.c.id == identity['id'])).scalar_one()
            definition_id = bind.execute(sa.select(definitions.c.id).where(
                definitions.c.definition_key == key, definitions.c.version == values['definition_version'])).scalar_one()
            values = {**values, 'definition_id': definition_id}
        bind.execute(table.update().where(sa.and_(*(table.c[key] == value for key, value in identity.items()))).values(**values))


def publish_definitions(bind):
    import sqlalchemy as sa
    from backend.ingest.form_definitions import definition_checksum
    table = sa.Table('form_definitions', sa.MetaData(), autoload_with=bind)
    definitions = bind.execute(sa.select(table).where(table.c.status == 'published')).mappings().all()
    seen = {(row['definition_key'], row['version']) for row in definitions}
    for row in definitions:
        if row['target_kind'] != 'property_record' or row['property_code'] == 'band_gap' or row['record_type'] == 'measured_tc':
            continue
        if (row['definition_key'], 2) in seen:
            continue
        values = {key: value for key, value in row.items() if key not in {'id', 'created_at', 'published_at'}}
        values.update(version=2, json_schema=payload_schema(), published_at=sa.func.now())
        values['checksum'] = definition_checksum(values)
        bind.execute(table.insert().values(**values))
        seen.add((row['definition_key'], 2))
