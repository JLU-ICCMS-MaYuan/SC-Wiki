"""CaH6 整篇现场：不完整排除不能崩溃，也不能绕过逐行覆盖。"""
from backend.ingest.domain_extraction import normalize_extraction
from test_issue114_domain_extraction import extraction
import pytest
from copy import deepcopy


def test_incomplete_table_exclusion_is_deferred_without_dropping_records():
    raw = extraction()
    raw['coverage_exclusions'] = [
        {'file_id': 'main', 'table_id': 't', 'category': 'out_of_model_scope', 'reason': 'Structural parameters table'},
        {'file_id': 'main', 'table_id': 't', 'row_index': 0, 'category': 'header_or_unit_row', 'reason': 'Header'},
    ]
    result = normalize_extraction(raw, allowed_blocks={('main', 1, 'b1')}, allowed_tables={('main', 't'): 3})
    assert len(result['material_states'][0]['property_modules'][0]['records']) == 1
    assert [e['row_index'] for e in result['coverage_exclusions']] == [0]
    assert result['coverage_exclusion_issues'][0]['proposal']['table_id'] == 't'
    assert raw['coverage_exclusions'][0].get('row_index') is None


def test_incomplete_table_exclusion_never_covers_result_rows():
    from backend.ingest.coverage_audit import audit_coverage
    from backend.ingest.document_ir import DocumentTable, TableCell
    from test_issue114_multimodal_pdf_agent import _ir
    ir = _ir()
    ir.tables = [DocumentTable(table_id='t', pdf_page=1, block_id='block-1', row_count=2, column_count=1,
        cells=[TableCell(cell_id=f'c{i}', row_index=i, column_index=0, text='200 K') for i in range(2)])]
    report = audit_coverage(ir, [], processed_pages=[1], exclusions=[{
        'file_id':ir.source_file_id, 'table_id':'t', 'category':'out_of_model_scope', 'reason':'Whole table'}])
    assert report.requires_human
    assert {'table:t:row:0', 'table:t:row:1'} <= set(report.uncovered_candidates)


def test_paraphrased_quote_is_rejected_before_whole_paper_claim_repair():
    raw = extraction()
    with pytest.raises(ValueError, match='quote_id=block_id'):
        normalize_extraction(raw, allowed_blocks={('main', 1, 'b1')},
                             allowed_quote_text={('main', 1, 'b1'): 'LaH_{10} T_c = 200 K at 150 GPa'})


def test_explicit_block_reference_preserves_original_math_and_validates_claim():
    from backend.ingest.document_claims import claims_from_candidates
    from test_issue114_multimodal_pdf_agent import _ir
    ir = _ir()
    ir.source_file_id = 'main'
    ir.parser['mode'] = 'text'
    ir.blocks[0].block_id = 'b1'
    ir.blocks[0].text = 'LaH_{10} T_c = 200 K at 150 GPa'
    raw = extraction()
    for node in (raw['material_states'][0], raw['material_states'][0]['property_modules'][0]['records'][0]):
        node['evidences'][0].update(quote=None, quote_id='b1')
    result = normalize_extraction(raw, allowed_blocks={('main', 1, 'b1')},
                                 allowed_quote_text={('main', 1, 'b1'): ir.blocks[0].text})
    assert result['material_states'][0]['evidences'][0]['quote'] == ir.blocks[0].text
    assert all(c.status == 'validated' for c in claims_from_candidates(result, {'main': ir}))


def test_coverage_classifier_receives_cross_page_context_and_full_target():
    from backend.ingest.upload_jobs import _uncovered_classifier_items
    from backend.ingest.document_ir import DocumentBlock, PageGeometry, content_hash
    from test_issue114_multimodal_pdf_agent import _ir
    ir = _ir()
    ir.pages.append(PageGeometry(pdf_page=2, width=600, height=800))
    text = 'for mu*=0.13. ' + 'The previously reported result is discussed. ' * 12
    ir.blocks.append(DocumentBlock(block_id='continued', block_type='paragraph', pdf_page=2,
        reading_order=2, text=text, content_hash=content_hash(text)))
    item = _uncovered_classifier_items(ir.source_file_id, ir, ['block:continued'])[0]
    assert item['text'] == text and len(item['text']) > 300
    assert {b['block_id'] for b in item['page_context']} == {'block-1', 'continued'}
    assert item['id'] == 'block:continued'


def test_range_endpoint_dedup_preserves_distinct_tc_mu_pairs():
    from backend.ingest.state_optimization import assemble_candidates
    from backend.tests.test_state_review_convergence import state
    candidate = state('classical_static', 235, 'harmonic', 'CaH6')
    records = candidate['property_modules'][0]['records']
    other = deepcopy(records[0])
    other.update(record_key='220', value_number=220, value_raw='220')
    other['payload']['parameters']['mu_star'] = 0.13
    interval = deepcopy(records[0])
    interval.update(record_key='range', value_kind='range', value_number=None, value_min=220, value_max=235, value_raw='220-235')
    interval['payload']['parameters'].pop('mu_star')
    records.extend([other, interval])
    result = assemble_candidates([{'material_states': [candidate]}])[0]['property_modules'][0]['records']
    assert {(r['value_number'], r['payload']['parameters']['mu_star']) for r in result if r['value_kind'] == 'number'} == {(235, 0.1), (220, 0.13)}
    assert any(r['value_kind'] == 'range' for r in result)


def test_grobid_abstract_boundary_requires_matching_layout_and_keeps_raw_source():
    from backend.ingest.grobid_document import _bounded_abstract
    from backend.ingest.document_ir import DocumentBlock, content_hash
    from test_issue114_multimodal_pdf_agent import _ir
    ir = _ir()
    abstract = 'Hydrogen rich compounds are investigated under high pressure. ' * 12
    ir.blocks[0].text = abstract
    marker = 'calcium hydride | sodalite structure'
    ir.blocks.append(DocumentBlock(block_id='keywords', block_type='paragraph', pdf_page=1,
        reading_order=1, text=marker, content_hash=content_hash(marker)))
    original = abstract + marker + ' Introduction discusses previous studies and open questions. ' * 12
    document = {'source_sha256': ir.source_sha256, 'metadata': {'abstract': original},
                'metadata_sources': {'abstract': {'text': original}}}
    result = _bounded_abstract(document, ir)
    assert result['metadata']['abstract'] == abstract.strip()
    assert result['metadata_sources']['abstract']['text'] == original
    assert document['metadata']['abstract'] == original
    assert _bounded_abstract(document, None) is document
    other = ir.model_copy(update={'source_sha256': 'b' * 64})
    assert _bounded_abstract(document, other) is document


def test_motivation_source_reference_resolves_exact_original_text():
    from backend.ingest.research_motivation import generate_motivation
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': r'We explore CaH_{6} to understand hydrogen networks.'}]
    def model(_, body):
        import json
        assert json.loads(body)['sources'][0]['source_id'] == 'review-source-0'
        return {'motives': [{'point': 'The authors seek to understand hydrogen networks.',
                             'evidences': [{'source_id': 'review-source-0'}]}]}
    value, error = generate_motivation(chunks, complete=model, attempts=1)
    assert value and error is None
    bad = lambda *_: {'motives': [{'point': 'The authors seek to understand hydrogen networks.',
        'evidences': [{'source_id': 'review-source-9'}]}]}
    assert generate_motivation(chunks, complete=bad, attempts=1)[1] == 'quote_unlocated'


@pytest.mark.parametrize('explicit_dft', [False, True])
def test_optimized_their_structures_is_valid_wording_but_vasp_does_not_prove_dft(explicit_dft):
    from backend.ingest.state_optimization import resolve_candidates
    from backend.tests.test_state_review_convergence import state
    candidate = {'material_states': [state('unknown', 235, material='CaH6')]}
    text = 'We optimized their structures using VASP.'
    if explicit_dft:
        text += ' The structural relaxation used density functional theory.'
    source = {'file_id': 'main', 'content': text}
    def model(*_):
        return {'workflows': [{'id': 'w', 'material': 'CaH6', 'optimization': 'classical_static',
            'evidences': [{'workflow_source_id': 'workflow-source-0'}]}],
            'assignments': [{'target': '0/0', 'workflow_id': 'w', 'optimization': 'classical_static',
                'approximation': 'unknown', 'evidences': [{'source_index': 0, 'quote': text}]}]}
    result, issues = resolve_candidates([candidate], [source], model)
    assert bool(issues) is not explicit_dft
    assert result[0]['material_states'][0]['structure_optimization'] == ('classical_static' if explicit_dft else 'unknown')



def test_completed_draft_reparse_refuses_concurrent_edit_before_artifact_or_draft_write(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from hashlib import sha256
    from types import SimpleNamespace
    from backend.ingest import upload_jobs as jobs, upload_tasks as tasks
    from backend.ingest.document_parsers import ParserError
    from test_issue139_workflow import test_worker_finishes_direct_claim_gate_before_common_methods_fill as worker_scenario
    process = jobs._process_upload_task
    @contextmanager
    def lock(_):
        with monkeypatch.context() as isolated:
            isolated.setattr(tasks, 'redis_client', lambda: SimpleNamespace(get=lambda _: 'human-edited-draft'))
            yield
    def protected_run(task):
        jobs.update_state(task, reparse_expected_draft_hash=sha256(b'original-draft').hexdigest())
        monkeypatch.setattr(jobs, 'upload_task_lock', lock)
        monkeypatch.setattr(jobs, 'save_draft', lambda *args: pytest.fail('不得覆盖人工改稿'))
        return process(task)
    monkeypatch.setattr(jobs, '_process_upload_task', protected_run)
    with pytest.raises(ParserError) as error:
        worker_scenario(tmp_path, monkeypatch)
    assert error.value.code == 'draft_changed_during_parsing'
    assert not (tmp_path / 'artifacts' / 'result.json').exists()



def test_range_does_not_replace_separately_reported_point_even_without_mu():
    from backend.ingest.state_optimization import assemble_candidates
    from backend.tests.test_state_review_convergence import state
    candidate = state('classical_static', 235, 'harmonic', 'CaH6')
    point = candidate['property_modules'][0]['records'][0]
    point['payload']['parameters'].pop('mu_star')
    interval = deepcopy(point)
    interval.update(record_key='range', value_kind='range', value_number=None, value_min=220, value_max=235, value_raw='220-235')
    candidate['property_modules'][0]['records'].append(interval)
    records = assemble_candidates([{'material_states': [candidate]}])[0]['property_modules'][0]['records']
    assert len(records) == 2
    assert {r['value_kind'] for r in records} == {'range', 'number'}


def test_summary_conclusions_are_numbered_and_checked_without_weakening_format():
    from backend.ingest.paper_summary import choose_summary
    from test_issue120_summary import ABSTRACT, SUMMARY
    attempts = []
    points = [line.split('. ', 1)[1] for line in SUMMARY.splitlines()]
    value, error = choose_summary('', ABSTRACT, [], lambda *_: {'conclusions': points}, on_attempt=attempts.append)
    assert (value, error) == (SUMMARY, None)
    assert [attempt['valid'] for attempt in attempts] == [False, True]
