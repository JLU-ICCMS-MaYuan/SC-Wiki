"""条件规则必须同时验证值、软件、阶段、材料/相和真实全窗完成。"""
from copy import deepcopy
import json

import pytest

from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest import condition_rules as rules
from backend.ingest.scientific_context import bind_snapshot_source_documents
from test_association_recheck import setup, grid


TEXT = ('For LaSc2H24 in the P6/mmm phase, all pressures use these settings. '
        'Quantum ESPRESSO is used for phonons and EPC with a 24×24×24 k grid. '
        'The phonon response uses DFPT. The wavefunction cutoff is 90 Ry. '
        'VASP uses the PBE functional for structural relaxation, with 850 eV and a force threshold of 1 meV/Å.')


def snapshot(text=TEXT, target='upload', field='k_grid', value='24×24×24', extra=None):
    draft = setup(basis='paper_inference', legacy=True)
    state = draft['material_states'][0]
    state['reported_space_group_symbol'] = 'P6/mmm'
    record = state['property_modules'][0]['records'][0]
    record['payload']['calculation_conditions'].update(calculation_code='Quantum ESPRESSO', **{field: value})
    if field != 'k_grid':
        record['payload']['source_associations'] = []
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': text}]
    if extra:
        chunks.append({'file_id': 'si', 'chunk_index': 0, 'content': extra})
    snap = ev.complete_snapshot(target, 'rule-test', ev.draft_records(draft, {}), chunks, draft)
    docs = {str(c['file_id']): {'sha256': 'a'*64, 'role': 'main' if c['file_id']=='main' else 'supplementary'} for c in chunks}
    bind_snapshot_source_documents(snap, docs)
    row = next(r for r in snap['records'] if r.get('record_field') == 'payload.calculation_conditions.' + field)
    return snap, row


def assessment(row):
    return {'verdict': 'supported', 'scope': deepcopy(row['condition_context']), 'value_origin': 'reported',
            'exceptions': 'none', 'explanation': '原文明确当前材料和物相的QE计算共用该参数，未见局部例外。',
            'fact_evidences': [{'source_id': 'review-source-0'}],
            'scope_evidences': [{'source_id': 'review-source-0'}],
            'software_evidences': [{'source_id': 'review-source-0'}]}


def evaluate(monkeypatch, snap, row, review=None):
    raw = assessment(row) if review is None else review
    monkeypatch.setattr('backend.rag.llm.complete_json', lambda *a, **kw: {'results': [{
        'key': row['key'], 'status': 'supported', 'reason': '原文支持',
        'evidences': [], 'condition_review': raw}]})
    candidates = ev.evaluate_batch([row], snap['chunks'])
    results = ev.aggregate_candidates([row], {row['key']: candidates}, {row['key']: []}, 'model', snap['chunks'])
    return ev.checked_result(row, results[row['key']], snap['chunks']), results


@pytest.mark.parametrize('target', ['upload', 'paper', 'revision'])
def test_rule_passes_inference_without_forging_human_review(monkeypatch, target):
    snap, row = snapshot(target=target)
    result, stored = evaluate(monkeypatch, snap, row)
    assert result['status'] == 'supported'
    assert result['adopted_basis'] == 'paper_inference'
    assert not result['human_confirmed'] and not result.get('decision')
    assert result['rule_review']['version'] == rules.VERSION
    assert not result['source_associations'][0]['stale']
    assert '按已确认' in result['ai_reason']
    assert ev.checked_result(row, json.loads(json.dumps(stored[row['key']])), snap['chunks'])['status'] == 'supported'
    assert ev.resolve_results({**snap, 'records': [row]}, stored, 7, None, snap['version'])[0]['status'] == 'supported'


@pytest.mark.parametrize('case', ['software', 'stage', 'material', 'phase', 'purpose', 'exception', 'unknown', 'quote', 'missing_scope'])
def test_wrong_ownership_or_incomplete_evidence_cannot_pass(monkeypatch, case):
    snap, row = snapshot(); raw = assessment(row)
    if case in {'software', 'stage', 'material', 'phase'}: raw['scope'][case] = 'wrong'
    if case == 'purpose': raw['scope']['parameter'] = 'q_grid_interpolated'
    if case == 'exception': raw['exceptions'] = 'present'
    if case == 'unknown': raw['verdict'] = 'uncertain'
    if case == 'quote': raw['fact_evidences'] = [{'file_id': 'main', 'quote': 'invented 24 grid'}]
    if case == 'missing_scope': raw['scope_evidences'] = []
    result, _ = evaluate(monkeypatch, snap, row, raw)
    assert result['status'] != 'supported' and not result['rule_review']


@pytest.mark.parametrize('change', ['content_hash', 'source_hash', 'version', 'missing_file', 'pdf_missing', 'one_pdf_unavailable'])
def test_old_or_incomplete_results_lose_auto_pass(monkeypatch, change):
    snap, row = snapshot(); _, stored = evaluate(monkeypatch, snap, row)
    result = deepcopy(stored[row['key']]); current = deepcopy(row)
    if change in {'content_hash', 'source_hash'}: current[change] = 'different'
    if change == 'version': result['rule_review']['version'] = 'old'
    if change == 'missing_file': current['condition_sources_complete'] = False
    if change == 'pdf_missing': result.update(status='missing', reason='PDF来源不可用')
    if change == 'one_pdf_unavailable': result['evidences'][0]['locator_status']='source_unavailable'
    assert ev.checked_result(current, result, snap['chunks'])['status'] != 'supported'


def test_every_window_must_finish_and_conflicts_are_not_outvoted(monkeypatch):
    snap, row = snapshot(extra='A local exception changes the grid at 200 GPa.')
    monkeypatch.setattr(ev, 'SOURCE_BATCH_CHARS', len(TEXT))
    windows = [[snap['chunks'][0]], [snap['chunks'][1]]]
    first = {'condition_window': rules.checked_window(row, assessment(row), windows[0])}
    assert not rules.finalize(row, [first], snap['chunks'])
    conflict = {'condition_window': rules.checked_window(row, {'verdict': 'conflict'}, windows[1])}
    assert not rules.finalize(row, [first, conflict], snap['chunks'])
    complete,row=snapshot(extra='This supplementary window contains unrelated background.')
    first={'condition_window':rules.checked_window(row,assessment(row),[complete['chunks'][0]])}
    clear={'condition_window':rules.checked_window(row,{'verdict':'not_reported'},[complete['chunks'][1]])}
    assert rules.finalize(row,[first,clear],complete['chunks'])


def test_missing_declared_si_or_hash_blocks_complete_source_marker():
    snap, row = snapshot()
    bind_snapshot_source_documents(snap, {'main': {'sha256':'a'*64,'role':'main'}}, {'main', 'si'})
    assert not row['condition_sources_complete']


def test_vasp_pbe_cannot_support_qe_but_explicit_qe_can(monkeypatch):
    snap, row = snapshot(field='exchange_correlation_functional', value='PBE')
    result, _ = evaluate(monkeypatch, snap, row)
    assert result['status'] != 'supported'
    snap, row = snapshot(text=TEXT + ' Quantum ESPRESSO uses the PBE functional.',
                         field='exchange_correlation_functional', value='PBE')
    assert evaluate(monkeypatch, snap, row)[0]['status'] == 'supported'


def test_dfpt_definition_supports_dft_but_not_a_functional(monkeypatch):
    snap, row = snapshot(field='electronic_method', value='DFT')
    raw = assessment(row); raw['value_origin'] = 'dfpt_definition'
    result, _ = evaluate(monkeypatch, snap, row, raw)
    assert result['status'] == 'supported' and result['adopted_basis'] == 'paper_inference'
    snap, row = snapshot(field='exchange_correlation_functional', value='PBE')
    raw = assessment(row); raw['value_origin'] = 'dfpt_definition'
    assert evaluate(monkeypatch, snap, row, raw)[0]['status'] != 'supported'


def test_empty_functional_is_optional_and_proposals_cannot_guess():
    from backend.ingest.evidence_proposals import checked_proposal
    snap, row = snapshot(field='exchange_correlation_functional', value=None)
    assert row['required'] is False
    for basis in ['paper_inference', 'general_knowledge', 'paper_quote']:
        proposal = {'values': {'': 'PBE'}, 'basis_kind': basis, 'explanation': 'VASP使用PBE所以QE也应使用PBE',
                    'evidences': [{'file_id': 'main', 'quote': TEXT}], 'supported': True}
        assert checked_proposal(row, proposal, snap['chunks']) is None


def test_units_are_checked_together_and_zero_is_not_a_default():
    value = {'value_number': 1, 'unit_raw': 'meV/Å'}
    assert rules.value_matches(value, 'convergence_force', [{'quote': 'The force threshold is 0.001 eV/Å.'}])
    assert not rules.value_matches(value, 'convergence_force', [{'quote': 'The force threshold is 1 eV/Å.'}])
    assert not rules.value_matches({'value_number':0,'unit_raw':'K'}, 'temperature_k', [{'quote':'SSCHA uses 300 K.'}])


def test_identity_matching_does_not_accept_longer_formula_or_other_phase():
    assert not rules.identity_in_text('LaSc2H24', 'LaSc2H240')
    assert not rules.identity_in_text('P6/mm', 'P6/mmm')
    assert rules.identity_in_text('LaSc2H24', 'LaSc₂H₂₄ in P6/mmm')


def test_software_clause_boundaries_and_convergence_ownership():
    sources = [{'quote': 'VASP uses PBE, whereas Quantum ESPRESSO uses LDA.'}]
    assert not rules.reported_for_software('PBE', 'Quantum ESPRESSO', sources)
    assert rules.reported_for_software('LDA', 'Quantum ESPRESSO', sources)
    sources = [{'quote': 'VASP optimizes the structure. The force threshold is 1 meV/Å. Quantum ESPRESSO computes EPC.'}]
    assert rules.reported_for_software('1 meV/Å', 'VASP', sources)
    assert not rules.reported_for_software('1 meV/Å', 'Quantum ESPRESSO', sources)
    split=[{'file_id':'main','chunk_index':2,'quote':'Quantum ESPRESSO uses a wavefunction cutoff of 90 Ry'},
           {'file_id':'main','chunk_index':3,'quote':'and a charge density cutoff of 720 Ry.'}]
    assert rules.reported_for_software(720,'Quantum ESPRESSO',split)
    split[1]['chunk_index']=4
    assert not rules.reported_for_software(720,'Quantum ESPRESSO',split)


def test_sscha_requires_current_anharmonic_result_and_distinct_grid_purpose():
    text = 'LaSc2H24 P6/mmm. SSCHA estimates anharmonic effects. \n\nAnharmonic 150 3.94 745 281\n\n The sampling q grid is 2×2×2; interpolation uses 6×6×6.'
    snap, row = snapshot(text=text)
    row = deepcopy(row)
    row['current_value'] = {'key':'sscha.q_grid_interpolated','value_kind':'text','value_raw':'6×6×6'}
    row['condition_context'].update(parameter='q_grid_interpolated',stage='sscha',software='sscha',result_numbers=[281,3.94,745])
    raw = assessment(row); raw['scope']['approximation'] = 'anharmonic'
    assert rules.validate_assessment(row, raw, snap['chunks'])
    raw['scope']['parameter'] = 'q_grid'
    assert not rules.validate_assessment(row, raw, snap['chunks'])
    raw['scope']['parameter'] = 'q_grid_interpolated'
    row['condition_context']['approximation'] = 'harmonic'
    assert not rules.validate_assessment(row, raw, snap['chunks'])


def test_one_bounded_repair_preserves_original_response(monkeypatch):
    snap, row = snapshot(); calls=[]; captures=[]
    def model(system, payload, **kwargs):
        calls.append(json.loads(payload))
        raw=assessment(row)
        if len(calls)==1: raw['scope_evidences']=[]
        return {'results':[{'key':row['key'],'status':'supported','evidences':[],'condition_review':raw}]}
    monkeypatch.setattr('backend.rag.llm.complete_json',model)
    evaluated=ev.evaluate_batch([row],snap['chunks'],on_response=captures.append)
    assert len(calls)==2 and calls[1]['validation_feedback']
    assert captures[0]['initial_response'] and captures[0]['repair_response']
    assert evaluated[0]['condition_window']['verdict']=='supported'


def test_bounded_repair_does_not_swallow_upload_cancellation(monkeypatch):
    class UploadCancelled(Exception):pass
    snap,row=snapshot();calls=[]
    def model(*args,**kwargs):
        calls.append(1)
        if len(calls)>1:raise UploadCancelled()
        raw=assessment(row);raw['scope_evidences']=[]
        return {'results':[{'key':row['key'],'status':'supported','condition_review':raw}]}
    monkeypatch.setattr('backend.rag.llm.complete_json',model)
    with pytest.raises(UploadCancelled):ev.evaluate_batch([row],snap['chunks'])


def test_progress_reads_compact_status_and_throttles_stream_checks(monkeypatch):
    from fastapi import HTTPException
    job_id='b'*32
    control=ev.job_control({'id':job_id,'owner':7,'status':'running','snapshot':{
        'target':'upload','target_id':'task','records':[{'claim':'x'*1000000}]},'prior':{'huge':'x'*1000000}})
    assert len(json.dumps(control))<500 and 'records' not in control['snapshot']
    class Cache:
        def get(self,key):
            assert key==ev.job_control_key(job_id), '流式检查不能读取大任务快照'
            return json.dumps(control)
    monkeypatch.setattr('backend.ingest.upload_tasks.redis_client',lambda:Cache())
    assert ev.read_job_status(job_id,7)['status']=='running'
    with pytest.raises(HTTPException):ev.read_job_status(job_id,8)
    clock=[100.];reads=[]
    monkeypatch.setattr(ev.time,'monotonic',lambda:clock[0])
    def status(*args):reads.append(1);return control
    monkeypatch.setattr(ev,'read_job_status',status)
    guard=ev.evidence_stream_guard(job_id,7,100.,10.)
    for _ in range(1000):guard('token')
    assert len(reads)==1
    clock[0]=101.1;control['status']='cancelled'
    with pytest.raises(InterruptedError):guard('token')
    clock[0]=111.
    with pytest.raises(TimeoutError):guard('token')


def test_sscha_table_match_never_borrows_numbers_from_harmonic_group():
    text='Harmonic 300 3.34 968 303 329\n\nAnharmonic 300 2.61 1165 293 330'
    assert rules.anharmonic_result_matches({'result_numbers':[300,2.61,1165,293,330]},text)
    assert not rules.anharmonic_result_matches({'result_numbers':[300,3.34,968,303,329]},text)


def test_material_phase_anchor_must_be_a_direct_statement():
    context={'material':'LaSc2H24','phase':'P6/mmm'}
    def chunks(text):return [{'file_id':'main','chunk_index':0,'content':text}]
    assert rules.material_phase_anchor(context,chunks('LaSc2H24 P6/mmm a = 4.712'))
    assert not rules.material_phase_anchor(context,chunks('LaSc2H24 does not adopt P6/mmm.'))
    assert not rules.material_phase_anchor(context,chunks('LaSc2H24 and H3S adopt Fm-3m and P6/mmm respectively.'))
    assert not rules.material_phase_anchor(context,chunks('LaSc2H24 is discussed.\nH3S adopts P6/mmm.'))


def test_missing_identity_citation_can_be_completed_from_same_paper(monkeypatch):
    snap,row=snapshot(text='Quantum ESPRESSO computes phonons with a 24×24×24 k grid.',
                      extra='The LaSc2H24 compound has space group P6/mmm.')
    result,_=evaluate(monkeypatch,snap,row)
    assert result['status']=='supported'
    assert any('space group P6/mmm' in e['quote'] for a in result['rule_review']['assessments'] for e in a['scope_evidences'])


def test_identity_in_another_window_does_not_bypass_full_coverage(monkeypatch):
    text='Quantum ESPRESSO computes phonons with a 24×24×24 k grid.'
    snap,row=snapshot(text=text,extra='The LaSc2H24 compound has space group P6/mmm.')
    monkeypatch.setattr(ev,'SOURCE_BATCH_CHARS',len(text))
    first={'condition_window':rules.checked_window(row,assessment(row),[snap['chunks'][0]],snap['chunks'])}
    assert first['condition_window']['assessment']
    assert not rules.finalize(row,[first],snap['chunks'])
    second={'condition_window':rules.checked_window(row,{'verdict':'not_reported'},[snap['chunks'][1]],snap['chunks'])}
    assert rules.finalize(row,[first,second],snap['chunks'])
    # 未提供的窗口编号不能通过完整目录被错误解释。
    invalid=assessment(row);invalid['fact_evidences']=[{'source_id':'review-source-1'}]
    assert not rules.checked_window(row,invalid,[snap['chunks'][0]],snap['chunks'])['assessment']


@pytest.mark.parametrize('explicit_qe',[False,True])
def test_real_normalizer_does_not_turn_vasp_functional_into_qe(explicit_qe):
    from test_issue114_domain_extraction import extraction,normalize
    raw=extraction();state=raw['material_states'][0];state['state_kind']='theoretical'
    record=state['property_modules'][0]['records'][0];record['record_type']='predicted_tc'
    record['payload']={'calculation_conditions':{'calculation_code':'Quantum ESPRESSO','exchange_correlation_functional':'PBE'}}
    quote='Quantum ESPRESSO uses the PBE functional.' if explicit_qe else 'VASP uses PBE for optimization. Quantum ESPRESSO computes phonons.'
    record['evidences'].append({'file_id':'main','pdf_page':2,'block_id':'b2','quote':quote})
    result=normalize(raw)['material_states'][0]['property_modules'][0]['records'][0]
    assert result['payload']['calculation_conditions'].get('exchange_correlation_functional')==('PBE' if explicit_qe else None)
    assert record['payload']['calculation_conditions']['exchange_correlation_functional']=='PBE'


def test_clear_plan_is_exactly_two_authorized_qe_values(monkeypatch):
    import importlib.util
    from pathlib import Path
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: None)
    spec=importlib.util.spec_from_file_location('recheck_script',Path(__file__).parents[2]/'scripts/recheck-upload-associations.py')
    script=importlib.util.module_from_spec(spec);spec.loader.exec_module(script)
    d=setup();state=d['material_states'][0];r=state['property_modules'][0]['records'][0]
    r['record_key']='legacy-tc-0'
    r['payload']['calculation_conditions'].update(calculation_code='Quantum ESPRESSO',exchange_correlation_functional='PBE')
    r['payload']['calculation_conditions']['extensions']=[{'key':'structural_relaxation.exchange_correlation_functional','value_kind':'text','value_raw':'PBE'}]
    second=deepcopy(r);second['record_key']='tc-point-cec51c89-335d-4988-9738-c903a170fe54'
    state['property_modules'][0]['records'].append(second)
    original=deepcopy(d)
    changed,plan=script.qe_clear_candidate('c16cc627a0c04dc8ad4289624d1da80a',d)
    assert len(plan)==2 and d==original
    for row in changed['material_states'][0]['property_modules'][0]['records']:
        assert row['payload']['calculation_conditions']['exchange_correlation_functional'] is None
        assert row['payload']['calculation_conditions']['extensions'][0]['value_raw']=='PBE'
    with pytest.raises(ValueError):script.qe_clear_candidate('other-task',d)
    with pytest.raises(ValueError):script.qe_clear_candidate('c16cc627a0c04dc8ad4289624d1da80a',changed)
    d['material_states'][0].pop('state_key',None)
    assert script.qe_clear_candidate('c16cc627a0c04dc8ad4289624d1da80a',d)[1][0]['state_key']=='state-1'


def test_new_upload_rechecks_final_filled_conditions(monkeypatch,tmp_path):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from backend.ingest.scientific_context import scientific_fingerprint
    d=setup();state=d['material_states'][0];state['reported_space_group_symbol']='P6/mmm'
    source=state['property_modules'][0]['records'][0]
    source['payload']['source_associations']=[]
    source['payload']['calculation_conditions']={'calculation_code':'Quantum ESPRESSO'}
    chunks=[{'file_id':'main','chunk_index':0,'content':TEXT}]
    def build(task,owner,*,parsing_draft):
        snap=ev.complete_snapshot('upload',task,ev.draft_records(parsing_draft,{}),chunks,parsing_draft)
        bind_snapshot_source_documents(snap,{'main':{'sha256':'a'*64,'role':'main'}})
        return snap
    monkeypatch.setattr(ev,'upload_snapshot',build)
    monkeypatch.setattr('backend.ingest.upload_jobs._ensure_not_cancelled',lambda *_:None)
    monkeypatch.setattr('backend.ingest.upload_tasks.artifact_directory',lambda _:tmp_path)
    def ledger(draft,context,*args,**kwargs):
        row=draft['material_states'][0]['property_modules'][0]['records'][0]
        e={'file_id':'main','chunk_index':0,'quote':TEXT}
        return {'complete':True,'gaps':[],'associations':[{'target':'s/m/r','expected_fingerprint':scientific_fingerprint(row),
            'target_path':'/payload/calculation_conditions/k_grid','value':'24×24×24','reported_value_raw':'24×24×24',
            'basis_kind':'paper_inference','stage':'electron_phonon','scope':{'material':'LaSc2H24'},
            'explanation':'当前材料物相共用QE网格','fact_evidences':[e],'scope_evidences':[e]}]}
    monkeypatch.setattr('backend.ingest.scientific_context.generate_context_associations',ledger)
    checked_values=[]
    def model(system,payload,**kwargs):
        request=json.loads(payload);results=[]
        for row in request['records']:
            condition=row.get('condition_context')
            item={'key':row['key'],'status':'supported','evidences':[{'file_id':'main','quote':TEXT}],'reason':'本文依据'}
            if condition:
                value=row['claim']['value']
                if condition['parameter']=='k_grid':checked_values.append(value)
                item['condition_review']={'verdict':'supported' if value else 'not_reported','value_origin':'reported',
                    'scope':condition,'exceptions':'none','explanation':'原文明确当前材料物相的软件和设置，未见例外',
                    **{k:[{'source_id':'review-source-0'}] for k in ['fact_evidences','scope_evidences','software_evidences']}}
            results.append(item)
        return {'results':results}
    monkeypatch.setattr('backend.rag.llm.complete_json',model)
    @contextmanager
    def begin():yield object()
    monkeypatch.setattr('backend.database.SessionLocal',SimpleNamespace(begin=begin))
    saved=[]
    monkeypatch.setattr(science,'save_results',lambda session,snap,results,owner:saved.append((snap,results)))
    monkeypatch.setattr('backend.ingest.pdf_source_pages.current_pdf_results',lambda session,snap,results:results)
    ev.generate_upload_suggestions('new-upload',d,7,scientific_sources=chunks)
    snap,results=saved[-1];row=grid(snap)
    assert None in checked_values and '24×24×24' in checked_values
    assert results[row['key']]['status']=='supported' and results[row['key']]['rule_review']
