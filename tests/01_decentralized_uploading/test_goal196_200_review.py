"""新目标：未知分类、派生字段和正式题录进入同一模型查证。"""
import json
from copy import deepcopy


def test_unknown_kind_and_derived_basics_are_reviewed():
    from backend.ingest.scientific_evidence import field_records, state_records
    from backend.ingest.model_review import _reviewable
    row = field_records('paper', 'paper', {'superconductor_kind': 'unknown'}, {'superconductor_kind': '超导类型'})[0]
    assert _reviewable(row)
    assert _reviewable({'field': 'material_states[0].structure_optimization', 'kind': 'field', 'required': False})
    assert not _reviewable({'field': 'material_states[0].structures[0].reported_space_group_number', 'kind': 'derived', 'required': True})
    rows = state_records({'state_key': 's', 'material': 'CaH6', 'element_count': 2,
        'reported_space_group_symbol': 'Im-3m', 'reported_space_group_number': 229, 'crystal_system': 'cubic'}, 0)
    selected = [r for r in rows if r['field'].split('.')[-1] in {'element_count', 'crystal_system', 'reported_space_group_number'}]
    assert len(selected) == 3 and all(_reviewable(r) for r in selected)


def test_successful_derived_inheritance_clears_pending():
    from backend.ingest.scientific_evidence import state_records, apply_derived
    rows = state_records({'state_key': 's', 'material': 'CaH6', 'element_count': 2}, 0)
    for row in rows:
        row.update(status='unchecked', pending_review=True, content_hash='c', source_hash='s')
        if row['field'].endswith('.material'):
            row.update(status='supported', pending_review=False, evidences=[{'quote': 'CaH6'}])
    value = next(r for r in apply_derived(rows) if r['field'].endswith('.element_count'))
    assert value['status'] == 'supported' and not value['pending_review']


def test_retired_optimization_details_are_not_normalized_or_exposed():
    from backend.ingest.material_state_contract import state_metadata
    result = state_metadata({'state_kind': 'theoretical', 'structure_optimization': 'sscha',
        'structure_optimization_details': {'method': 'old', 'volume': 'optimized'}})
    assert result['structure_optimization'] == 'sscha'
    assert 'structure_optimization_details' not in result


def test_model_can_read_formal_bibliography_and_preserves_external_source(monkeypatch):
    from backend.ingest import bibliography_lookup
    from backend.ingest.model_review import review_fields
    from backend.ingest.property_evidence import complete_snapshot
    monkeypatch.setattr(bibliography_lookup, 'lookup', lambda doi: {'DOI': doi,
        'title': ['Current paper'], 'volume': '109', 'issue': '17', 'page': '6463-6466'})
    row = {'key': 'pages', 'item_key': 'pages', 'field': 'paper.pages', 'kind': 'field',
        'label': '页码', 'current_value': None, 'required': False, 'claim': {'value': None}}
    snap = complete_snapshot('upload', 'isolated', [row], [{'file_id': 'main', 'chunk_index': 0,
        'content': 'Current paper DOI 10.1073/pnas.1118168109. Early Edition.'}], {})
    calls = []
    def model(_, prompt, **kwargs):
        request = json.loads(prompt); calls.append(request)
        if len(calls) == 1:
            assert 'lookup_bibliography' in request['tools']
            return {'action': {'name': 'lookup_bibliography', 'arguments': {'doi': '10.1073/pnas.1118168109'}}}
        source = next(s for s in request['sources'] if s.get('origin_kind') == 'external_bibliography')
        return {'results': [{'key': 'pages', 'status': 'supported', 'reason': 'DOI和标题均对应本篇正式题录。',
            'final_value': '6463-6466', 'unique': True, 'basis_kind': 'paper_synthesis', 'source_ids': [source['source_id']]}]}
    result = review_fields(snap['records'], snap['chunks'], model=model)['pages']
    assert result['proposal']['final_verified'] and result['proposal']['values'][''] == '6463-6466'
    assert result['evidences'][0]['origin_kind'] == 'external_bibliography'
    assert result['evidences'][0]['source_url'].startswith('https://api.crossref.org/works/')


def test_journal_volume_is_not_a_retired_geometry_constraint():
    from backend.ingest.evidence_proposals import editable_fields, valid_value
    field = editable_fields({'field': 'paper.volume', 'kind': 'field', 'label': '卷号', 'claim': {'value': None}, 'current_value': None})[0]
    assert 'enum' not in field['schema']
    assert valid_value('109', field['schema'])


def test_retirement_migration_cleans_current_draft_and_preserves_other_data():
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    path = Path(__file__).parents[2] / 'alembic/versions/20261101_0198_single_optimization_method.py'
    spec = importlib.util.spec_from_file_location('retire198', path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE material_states (id INTEGER PRIMARY KEY,structure_optimization VARCHAR(32),structure_optimization_details JSON)')
        connection.exec_driver_sql("INSERT INTO material_states VALUES (1,'anharmonic_quantum','{}')")
        table = sa.Table('scientific_work_drafts', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True), sa.Column('body', sa.JSON))
        table.create(connection)
        connection.execute(table.insert().values(id=1, body={'paper': {'title': 'Keep'}, 'material_states': [
            {'pressure_value_gpa': 200, 'structure_optimization': 'classical_static', 'structure_optimization_details': {'volume': 'fixed'}}]}))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert 'structure_optimization_details' not in {c['name'] for c in sa.inspect(connection).get_columns('material_states')}
        body = connection.scalar(sa.select(table.c.body))
        assert body['paper']['title'] == 'Keep' and body['material_states'][0]['pressure_value_gpa'] == 200
        assert 'structure_optimization_details' not in body['material_states'][0]
        assert connection.scalar(sa.text('SELECT structure_optimization FROM material_states')) == 'unknown'
    engine.dispose()


def test_external_tool_is_fixed_host_and_rejects_wrong_identity(monkeypatch):
    import httpx
    import pytest
    from backend.ingest.bibliography_lookup import lookup
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json={'message': {'DOI': '10.1000/other'}}, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx, 'get', get)
    with pytest.raises(ValueError):
        lookup('https://untrusted.example/document')
    assert not calls
    with pytest.raises(ValueError, match='DOI不一致'):
        lookup('10.1073/pnas.1118168109')
    assert calls[0].startswith('https://api.crossref.org/works/')


def test_external_bibliography_roundtrip_keeps_origin_and_link(db_session):
    from backend.ingest import property_evidence as ev, scientific_evidence as science
    from backend.ingest.model_review import bind_result
    row = {'key': 'volume', 'item_key': 'volume', 'field': 'paper.volume', 'kind': 'field',
           'label': '卷号', 'current_value': '109', 'claim': {'value': '109'}, 'required': False}
    snap = ev.complete_snapshot('upload', 'isolated', [row], [{'file_id': 'main', 'chunk_index': 0, 'content': 'Current paper'}], {})
    evidence = {'file_id': 'crossref:10.1073/pnas.1118168109', 'chunk_index': 0,
                'quote': 'Formal volume 109', 'origin_kind': 'external_bibliography',
                'source_url': 'https://api.crossref.org/works/10.1073%2Fpnas.1118168109'}
    result = bind_result(snap['records'][0], {'status': 'supported', 'reason': '正式题录身份已核实',
                         'source_kind': 'external_bibliography', 'evidences': [evidence]}, snap['chunks'])
    science.save_results(db_session, snap, {'volume': result}, 1); db_session.flush()
    loaded = science.load_results(db_session, snap)
    view = ev.public_snapshot(snap, loaded)['records'][0]
    assert view['status'] == 'supported'
    assert view['evidences'][0]['origin_kind'] == 'external_bibliography'
    assert view['evidences'][0]['source_url'] == evidence['source_url']


def test_grobid_probe_reports_current_service_without_changing_task(monkeypatch):
    import httpx
    from backend.ingest.grobid_document import service_available
    monkeypatch.setattr(httpx, 'get', lambda *a, **k: httpx.Response(200, text='true'))
    assert service_available()
    def offline(*a, **k): raise httpx.ConnectError('offline')
    monkeypatch.setattr(httpx, 'get', offline)
    assert not service_available()
