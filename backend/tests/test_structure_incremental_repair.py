"""结构反馈只重读失败项，成功结构保持来源、身份和已验证结果。"""
import hashlib
import json
from copy import deepcopy

import pymupdf
import pytest


@pytest.mark.parametrize('native', [True, False])
def test_partial_structure_repair_reuses_valid_neighbor_without_revalidation(tmp_path, monkeypatch, native):
    from backend.ingest import structure_reading as reader
    path = tmp_path / 'two.pdf'
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40, 40), '\n'.join([
            'NaCl 10 GPa Pm-3m fractional coordinates',
            'a = b = c = 5.64 Angstrom', 'alpha = beta = gamma = 90 degree',
            'Na 0.000 0.000 0.000', 'Cl 0.500 0.500 0.500',
            'KCl 20 GPa Pm-3m coordinates', 'K 0.000 0.000 0.000']))
        pdf.save(path)
    source = dict(file_id='si', role='supplementary', filename=path.name,
                  sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    calls, checks, events = [], [], []
    original = reader._reading_result

    def validate(answer, *args):
        checks.extend(item['material'] for item in answer['structures'])
        return original(answer, *args)

    monkeypatch.setattr(reader, '_reading_result', validate)

    def model(system, payload, **options):
        request = json.loads(payload)
        calls.append(request)
        if len(calls) == 1:
            return dict(action=dict(name='read_original_page', arguments=dict(file_id='si', page=1)))
        rows = request['sources']
        def ref(prefix):
            return next(row['source_id'] for row in rows if row['content'].startswith(prefix))
        if len(calls) == 2:
            items = []
            for material, pressure, atom, mode in [('NaCl', 10, 'Na', 'fractional'), ('KCl', 20, 'K', 'unknown')]:
                items.append(dict(material=material, pressure_value_gpa=pressure, space_group_symbol='Pm-3m',
                    coordinate_mode=mode, length_unit='angstrom', angle_unit='degree', position_unit='dimensionless',
                    cell_parameters=dict(a=5.64,b=5.64,c=5.64,alpha=90,beta=90,gamma=90),
                    cell_source_ids=[ref('a ='),ref('alpha =')], source_ids=[ref(material+' ')],
                    atoms=[dict(element=atom,coordinates=[0,0,0],source_id=ref(atom+' ')),
                           dict(element='Cl',coordinates=[.5,.5,.5],source_id=ref('Cl '))],
                    uncertainties=[],reason='原页及坐标原行'))
            return dict(structures=items,uncertainties=[],reason='首次完整读取')
        assert len(calls) == 3
        tools = {d['function']['name']:d['function'] for d in options['tool_definitions']}
        assert 'repair_structures' in tools and 'report_structures' not in tools
        pending = request['structure_repairs']
        assert len(pending) == 1 and pending[0]['structure']['material'] == 'KCl'
        assert checks == ['NaCl', 'KCl']
        fixed = deepcopy(pending[0]['structure'])
        fixed['coordinate_mode'] = 'fractional'
        update = dict(
            updates=[dict(reading_id=pending[0]['reading_id'],structure=fixed)],
            uncertainties=[],reason='只明确KCl原行的坐标类型')
        return dict(action=dict(name='repair_structures',arguments=update)) if native else update

    result = reader.extract_structure_candidates('',source=source,pdf_path=path,model=model,on_event=events.append)
    assert checks == ['NaCl', 'KCl', 'KCl']
    assert {c['reported_structure']['material'] for c in result if c['status']=='valid'} == {'NaCl','KCl'}
    repair = next(e for e in events if e['status']=='structure-repair')
    assert len(repair['reused_reading_ids']) == len(repair['updated_reading_ids']) == 1


def test_repair_cannot_target_a_valid_neighbor_or_duplicate_identity():
    from backend.ingest.structure_reading import _apply_structure_updates
    rows = {'good':{'status':'valid'}, 'bad':{'status':'blocked'}}
    for updates in ([dict(reading_id='good',structure={})],
                    [dict(reading_id='bad',structure={}),dict(reading_id='bad',structure={})]):
        with pytest.raises(ValueError):
            _apply_structure_updates(updates, rows)
    assert rows == {'good':{'status':'valid'},'bad':{'status':'blocked'}}
