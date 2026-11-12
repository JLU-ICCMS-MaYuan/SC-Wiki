"""局部图读修订不得覆盖已验证点；共享轴变化保留原点观察与真实依赖。"""
from copy import deepcopy
import pytest
from backend.tests.test_chart_reading import panel
from backend.ingest.image_feedback import _merge_chart_repair


def test_outside_tick_feedback_names_exact_boundary_without_relaxing_it():
    from backend.ingest.chart_calibration import coordinate_value, ChartReadingError
    axis = {'scale': 'linear', 'bounds': [351.4, 606.9], 'ticks': [
        {'position': 402.49, 'value': 4}, {'position': 504.03, 'value': 2},
        {'position': 606.93, 'value': 0}]}
    with pytest.raises(ChartReadingError) as failure:
        coordinate_value(axis, 538, pixel_error=1.5)
    assert failure.value.details['reason_code'] == 'TICK_OUTSIDE_AXIS_BOUNDS'
    assert failure.value.details['axis_bounds'] == [351.4, 606.9]
    assert failure.value.details['outside_ticks'] == [{'position': 606.93, 'value': 0}]
    assert axis['bounds'] == [351.4, 606.9] and axis['ticks'][-1]['position'] == 606.93


def test_cached_calibration_rejection_is_repaired_without_reextracting_valid_readings(tmp_path, monkeypatch):
    from backend.tests.test_chart_reading import original, fake_model
    from backend.ingest import chart_reading as reader
    from backend.ingest.chart_cache import bar_calibration_upgrade
    path, ir, source = original(tmp_path)
    with monkeypatch.context() as old:
        old.setattr(reader, 'VERSION', 'scientific-chart-reading-v13')
        reader.enrich_document(ir, path, source, fake_model([]))
    previous = ir.coverage['chart_reading']
    ids = {b.block_id for b in ir.blocks if b.metadata.get('chart_reading')}
    target = previous['targets'][0]
    previous['unresolved'].append({'region_id':target['region_id'],'page':target['page'],
        'figure':'Fig. 1','panel':'Failed axis','quantity':'dos_fermi','category':'Total','series':'Total',
        'reason':'Printed horizontal tick position unsupported','reason_code':'HORIZONTAL_TICK_LABEL_POSITION_UNSUPPORTED',
        'checked':True})
    upgrade = bar_calibration_upgrade(ir, path, source)
    assert upgrade is not None and len(upgrade['repair_targets']) == 1
    assert set(upgrade['reused_reading_block_ids']) == ids
    assert upgrade['required_panels'][target['region_id']][0]['panel'] == 'Failed axis'


def test_v11_cache_rechecks_new_axis_guard_without_reextracting_valid_neighbors(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from backend.tests.test_chart_reading import original, fake_model
    from backend.ingest import chart_reading as reader
    from backend.ingest.chart_cache import bar_calibration_upgrade
    path, ir, source = original(tmp_path)
    with monkeypatch.context() as old:
        old.setattr(reader, 'VERSION', 'scientific-chart-reading-v11')
        reader.enrich_document(ir, path, source, fake_model([]))
        kept = {b.block_id for b in ir.blocks if b.metadata.get('chart_reading')}
        facts = [deepcopy(b.metadata['chart_reading']) for b in ir.blocks if b.block_id in kept]
        fixture = json.loads((Path(__file__).parent/'fixtures/native-tool-extra-closer.json').read_text())
        raw = json.loads(fixture['partial_response'])['tool_calls'][0]['arguments']
        answer, _ = json.JSONDecoder().raw_decode(raw)
        for fact in facts:
            fact.update(kind='line', panel='BadDOS', quantity='dos_fermi', unit='states/eV',
                        x_reading={'axis': answer['panels'][0]['x_axis']})
        reader.append_readings(ir, facts)
        ir.coverage['chart_reading']['readings'] = 4
    upgrade = bar_calibration_upgrade(ir, path, source)
    assert upgrade is not None and len(upgrade['repair_targets']) == 1
    assert set(upgrade['reused_reading_block_ids']) == kept
    assert upgrade['retained_panels'][upgrade['repair_targets'][0]['region_id']] == [
        {'figure': 'Fig. 1', 'panel': 'Tc', 'quantity': 'tc'}]


def test_partial_point_repair_keeps_valid_neighbor_conditions_and_absent_panel():
    tc=panel();dos={**deepcopy(tc),'panel':'DOS','quantity':'dos_fermi','unit':'states/eV'}
    previous={'panels':[tc,dos],'notes':[]}
    verified={('Fig. 1','Tc','tc','YH10','blue'),('Fig. 1','DOS','dos_fermi','YH10','blue'),
              ('Fig. 1','DOS','dos_fermi','YH10','green')}
    patch=deepcopy(tc);patch['points']=[deepcopy(tc['points'][1])];patch['points'][0]['y']=320
    result,reused=_merge_chart_repair(previous,{'panels':[patch],'notes':[]},verified)
    assert result['panels'][1]==dos
    assert result['panels'][0]['points'][0]==tc['points'][0]
    assert result['panels'][0]['points'][1]['y']==320
    assert len(reused)==3
    assert previous['panels'][0]['points'][1]['y']==300


def test_repeated_valid_point_does_not_broadcast_changed_pressure_or_phase():
    original=panel();patch=deepcopy(original)
    patch['points'][0].update(pressure_value_gpa=200,space_group_symbol='P1',y=1)
    key=('Fig. 1','Tc','tc','YH10','blue')
    result,reused=_merge_chart_repair({'panels':[original],'notes':[]},{'panels':[patch],'notes':[]},{key})
    assert result['panels'][0]['points'][0]==original['points'][0]
    assert list(key) in reused


@pytest.mark.parametrize('kind',['bar','line'])
def test_axis_repair_reuses_actual_point_observation_without_requiring_full_retyping(kind):
    original=panel();original['kind']=kind;patch=deepcopy(original);patch['axis']['ticks'][0]['value']=220;patch['points']=[]
    result,reused=_merge_chart_repair({'panels':[original],'notes':[]},{'panels':[patch],'notes':[]},
        {('Fig. 1','Tc','tc','YH10','blue')})
    assert result['panels'][0]['points']==original['points']
    assert result['panels'][0]['axis']==patch['axis']
    assert reused


def test_unresolved_omission_does_not_delete_previous_failed_observation():
    original=panel();patch=deepcopy(original);patch['points']=[];patch['unresolved']=[]
    result,_=_merge_chart_repair({'panels':[original],'notes':[]},{'panels':[patch],'notes':[]},set())
    assert result['panels'][0]['points']==original['points']


def test_explicit_unread_replaces_only_failed_point_and_keeps_valid_neighbor():
    original=panel();patch=deepcopy(original);patch['points']=[]
    patch['unresolved']=[{'category':'YH10','series':'green','reason':'No independently visible marker'}]
    answer,_=_merge_chart_repair({'panels':[original],'notes':[]},{'panels':[patch],'notes':[]},
        {('Fig. 1','Tc','tc','YH10','blue')})
    assert answer['panels'][0]['points']==[original['points'][0]]
    assert answer['panels'][0]['unresolved']==patch['unresolved']


def test_renamed_panel_and_duplicate_updates_are_not_guessed_or_silently_deduplicated():
    original=panel()
    for patch in ({**deepcopy(original),'panel':'renamed'},
                  {**deepcopy(original),'points':[original['points'][0],original['points'][0]]}):
        with pytest.raises(ValueError):
            _merge_chart_repair({'panels':[original],'notes':[]},{'panels':[patch],'notes':[]},set())


def test_cache_upgrade_repairs_only_failed_bar_panel_and_preserves_original_dos_blocks(tmp_path, monkeypatch):
    from backend.tests.test_chart_reading import original, fake_model
    from backend.ingest import chart_reading as reader
    from backend.ingest.document_ir import DocumentIR
    path, ir, source=original(tmp_path)
    with monkeypatch.context() as old:
        old.setattr(reader,'VERSION','scientific-chart-reading-v10')
        reader.enrich_document(ir,path,source,fake_model([]))
        facts=[deepcopy(b.metadata['chart_reading'])for b in ir.blocks if 'chart_reading'in b.metadata]
        expected_values={fact['value_number']for fact in facts}
        ir.blocks=[b for b in ir.blocks if 'chart_reading'not in b.metadata]
        dos=[]
        for fact in facts:
            kept=deepcopy(fact);kept.update(quantity='dos_fermi',quantity_name='DOS',panel='DOS',unit='states/eV')
            dos.append(kept)
            fact['axis']['ticks'][-1]['position']=800
            fact['calibrated_axis']['ticks'][-1]['position']=800
            fact['value_number']=0;fact['value_raw']='~0 K'
        reader.append_readings(ir,facts+dos)
    ir=DocumentIR.model_validate(ir.model_dump(mode='json'))
    ir.coverage['chart_reading']['readings']=4
    historical=ir.blocks[-1].model_copy(deep=True)
    historical.block_id='historical-retired-reading'
    historical.reading_order=len(ir.blocks)
    historical.metadata.update(selected_for_reading=False,superseded_by='scientific-chart-reading-v10')
    ir.blocks.append(historical)
    historical_snapshot=historical.model_dump(mode='json')
    kept={b.block_id:deepcopy(b.model_dump(mode='json'))for b in ir.blocks
          if b.metadata.get('chart_reading',{}).get('quantity')=='dos_fermi'
          and b.metadata.get('selected_for_reading')is not False}
    calls=[]
    def model(prompt,payload,**options):
        import json
        request=json.loads(payload);calls.append(request)
        assert 'image_pages'not in request  # 同文件同图发现结果复用，不重新遍历全文找图。
        assert request['retained_panels']==[{'figure':'Fig. 1','panel':'DOS','quantity':'dos_fermi'}]
        return {'panels':[panel()],'notes':[]}
    report=reader.enrich_document(ir,path,source,model)
    assert len(calls)==1 and report['readings']==4
    assert set(report['reused_reading_block_ids'])==set(kept)
    for block in ir.blocks:
        if block.block_id in kept:assert block.model_dump(mode='json')==kept[block.block_id]
        if block.block_id=='historical-retired-reading':assert block.model_dump(mode='json')==historical_snapshot
    active=[b.metadata['chart_reading']for b in ir.blocks if 'chart_reading'in b.metadata
            and b.metadata.get('selected_for_reading')is not False]
    assert len(active)==4
    assert {v['value_number']for v in active if v['quantity']=='tc'}==expected_values


def test_nonbar_source_upgrade_preserves_entire_ir_without_new_model_calls(tmp_path, monkeypatch):
    from backend.tests.test_chart_reading import original, fake_model
    from backend.ingest import chart_reading as reader
    path,ir,source=original(tmp_path)
    calls=[]
    base=fake_model(calls)
    def line_model(prompt,payload,**options):
        answer=base(prompt,payload,**options)
        for item in answer.get('panels',[]):item['kind']='line'
        return answer
    with monkeypatch.context()as old:
        old.setattr(reader,'VERSION','scientific-chart-reading-v10')
        reader.enrich_document(ir,path,source,line_model)
    before=[b.model_dump(mode='json')for b in ir.blocks]
    report=reader.enrich_document(ir,path,source,lambda *_a,**_k:pytest.fail('无关线图不应重提'))
    assert report['new_readings']==0 and len(report['reused_reading_block_ids'])==2
    assert [b.model_dump(mode='json')for b in ir.blocks]==before


def test_repair_inventory_cannot_lose_pending_panel_or_resolve_it_with_context_notes():
    from backend.ingest.image_feedback import _chart_repair_coverage
    required=[{'figure':'Fig. 1','panel':'Tc','quantity':'tc','points':[{'category':'YH10','series':'blue'}]}]
    note={'scope':'context','reason':'Only another panel was read.'}
    missing=_chart_repair_coverage({'panels':[],'notes':[note]},required)
    assert missing and missing[0]['reason_code']=='MISSING_REPAIR_CANDIDATES'
    observed=panel();observed['points']=[]
    observed['unresolved']=[{'category':'YH10','series':'blue','reason':'Original marker is occluded'}]
    assert _chart_repair_coverage({'panels':[observed],'notes':[]},required)==[]


def test_cache_reuse_cannot_borrow_same_pdf_hash_from_another_file_identity(tmp_path, monkeypatch):
    from backend.tests.test_chart_reading import original,fake_model
    from backend.ingest import chart_reading as reader
    path,ir,source=original(tmp_path)
    with monkeypatch.context()as old:
        old.setattr(reader,'VERSION','scientific-chart-reading-v10')
        reader.enrich_document(ir,path,source,fake_model([]))
    for block in ir.blocks:
        if 'chart_reading'in block.metadata:block.metadata['chart_reading']['source_file_id']='other-model-task-file'
    with pytest.raises(ValueError,match='来源'):
        reader.enrich_document(ir,path,source,lambda *_a,**_k:pytest.fail('不能借用另一任务结果'))


def test_cache_axis_correction_invalidates_shared_values_even_when_bar_edges_are_unchanged(tmp_path, monkeypatch):
    from backend.tests.test_chart_reading import original,fake_model
    from backend.ingest import chart_reading as reader,chart_calibration
    from backend.ingest.chart_cache import bar_calibration_upgrade
    path,ir,source=original(tmp_path)
    with monkeypatch.context() as old:
        old.setattr(reader,"VERSION","scientific-chart-reading-v10")
        reader.enrich_document(ir,path,source,fake_model([]))
    previous=chart_calibration.align_value_ticks
    def corrected_axis(image,axis,**options):
        fixed,facts=previous(image,axis,**options)
        fixed=deepcopy(fixed)
        fixed["ticks"][0]["position"]+=10
        return fixed,facts
    monkeypatch.setattr(chart_calibration,"align_value_ticks",corrected_axis)
    upgrade=bar_calibration_upgrade(ir,path,source)
    assert len(upgrade["repair_targets"])==1
    assert not upgrade["reused_reading_block_ids"]
