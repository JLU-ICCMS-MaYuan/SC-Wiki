"""独立图面板外的上下文裁剪不等于目标数据读取失败。"""
from copy import deepcopy
import json

import pytest

from backend.ingest.chart_reading import enrich_document, ChartReadingError, reading_schema
from backend.ingest.document_ir import DocumentIR
from backend.rag.structured_output import validate_output, StructuredOutputError
from backend.tests.test_chart_reading import original, panel


def reader(note, *, panels=True):
    def model(_prompt,content,**_options):
        q=json.loads(content)
        if 'image_pages' in q:
            return {'pages':[{'page':1,'figures':[{'bbox':[100,100,900,900],
                'label':'Target scalar panel','target':True,'reason':'Tc bars'}]}]}
        return {'panels':[panel()] if panels else [],'notes':[deepcopy(note)]}
    return model


def test_context_note_is_preserved_without_becoming_unreadable_source(tmp_path):
    path,ir,source=original(tmp_path)
    note={'scope':'context','reason':'The neighboring DOS panel is clipped; only this requested Tc panel is read.'}
    report=enrich_document(ir,path,source,reader(note))
    restored=DocumentIR.model_validate_json(ir.model_dump_json())
    assert report['readings']==2 and not report['unresolved']
    assert report['context_notes'][0]['reason']==note['reason']
    assert report['context_notes'][0]['region_id']=='chart-page-1-figure-0'
    assert not any('chart_unresolved' in b.metadata for b in restored.blocks)
    assert all(b.metadata.get('selected_for_reading') is not False for b in restored.blocks)


def test_real_target_limitation_still_produces_unreadable_source(tmp_path):
    path,ir,source=original(tmp_path)
    report=enrich_document(ir,path,source,reader({'scope':'target','reason':'The target value axis is not readable.'},panels=False))
    assert report['unresolved'] and not report['context_notes']
    assert any('chart_unresolved' in b.metadata for b in ir.blocks)


def test_context_claim_alone_cannot_claim_target_was_read(tmp_path):
    path,ir,source=original(tmp_path);before=ir.model_dump()
    with pytest.raises(ChartReadingError,match='目标'):
        enrich_document(ir,path,source,reader({'scope':'context','reason':'Neighbor is clipped.'},panels=False))
    assert ir.model_dump()==before


def test_empty_panel_with_context_note_cannot_claim_target_was_read(tmp_path):
    path,ir,source=original(tmp_path)
    def model(prompt,content,**opts):
        answer=reader({'scope':'context','reason':'No target limitation stated.'})(prompt,content,**opts)
        if answer.get('panels'):
            answer['panels'][0].update(categories=[],series=[],points=[],unresolved=[])
        return answer
    with pytest.raises(ChartReadingError,match='目标'):
        enrich_document(ir,path,source,model)


def test_legacy_unscoped_note_is_not_guessed_or_silently_reclassified():
    old={'panels':[panel()],'notes':['Neighboring DOS and Tc panels are clipped.']}
    with pytest.raises(StructuredOutputError):validate_output(old,reading_schema())


def test_unreadable_target_point_identity_and_reason_are_kept(tmp_path):
    path,ir,source=original(tmp_path)
    def model(prompt,content,**opts):
        answer=reader({'scope':'context','reason':'Other panels outside requested scope.'})(prompt,content,**opts)
        if answer.get('panels'):
            p=answer['panels'][0];p['points'].pop();p['unresolved']=[{'category':'YH10','series':'green','reason':'Target bar overlaps baseline.'}]
        return answer
    report=enrich_document(ir,path,source,model)
    assert len(report['unresolved'])==1
    assert report['unresolved'][0]['category']=='YH10' and report['unresolved'][0]['series']=='green'
    assert 'Target bar' in report['unresolved'][0]['reason']
