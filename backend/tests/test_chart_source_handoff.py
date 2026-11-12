from copy import deepcopy
import pytest
from backend.ingest.coverage_audit import reviewable_chart_limits
from backend.ingest.chart_reading import unresolved_block, VERSION
from backend.ingest.document_ir import DocumentIR,PageGeometry


def case():
    issue={'page':1,'region_id':'figure','figure':'Fig. 1','category':'A','series':'Tc','reason':'Original curves overlap; no numerical reading.'}
    block=unresolved_block('a'*64,issue,0)
    ir=DocumentIR(document_id='doc',source_file_id='main',source_sha256='a'*64,
        parse_profile='complementary',pages=[PageGeometry(pdf_page=1,width=200,height=200)],blocks=[block],
        coverage={'chart_reading':{'status':'completed','version':VERSION,'source_sha256':'a'*64,
            'scanned_pages':[1],'targets':[{'region_id':'figure','page':1}]}})
    report={'requires_human':True,'uncovered_candidates':[],'limitations':['unreadable_exclusion_present'],
        'unreadable_regions':[{'locator':block.block_id}]}
    return ir,report


def test_known_chart_missing_is_preserved_without_claiming_coverage_or_values():
    ir,report=case();before=deepcopy(report)
    result=reviewable_chart_limits({'main':ir},{'main':report})
    assert len(result)==1 and result[0]['observation']['reason'].startswith('Original curves')
    assert 'value_number'not in result[0] and report==before and report['requires_human']


def test_real_coverage_locator_shape_preserves_three_original_unknowns():
    import json,gzip
    from pathlib import Path
    with gzip.open(Path(__file__).parent/'fixtures/chart-source-locator-real.json.gz','rt')as f:data=json.load(f)
    ir=DocumentIR.model_validate(data['document']);report=data['report'];before=deepcopy(report)
    limits=reviewable_chart_limits({ir.source_file_id:ir},{ir.source_file_id:report})
    assert len(limits)==3 and {x['block_id']for x in limits}=={x['locator']for x in report['unreadable_regions']}
    assert report==before and report['requires_human']


@pytest.mark.parametrize('kind',['invalid_claim','uncovered_result','technical_axis','ordinary_unreadable','old_reader','truncated','source_changed'])
def test_no_invalid_source_or_real_missing_result_is_admitted(kind):
    ir,report=case()
    if kind=='uncovered_result':report['uncovered_candidates']=['block:missing-lambda']
    if kind=='technical_axis':ir.blocks[0].metadata['chart_unresolved']['reason_code']='TICK_CALIBRATION_INCONSISTENT'
    if kind=='ordinary_unreadable':ir.blocks[0].metadata={}
    if kind=='old_reader':ir.coverage['chart_reading']['version']='old'
    if kind=='truncated':report['truncation_signals']=['output_truncated']
    if kind=='source_changed':ir.coverage['chart_reading']['source_sha256']='b'*64
    assert reviewable_chart_limits({'main':ir},{'main':report},invalid_claims=kind=='invalid_claim')is None
