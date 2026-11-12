"""仅结构状态的外层身份须沿已归属结构读取原始来源，不能借用旧Claim。"""
from copy import deepcopy
from backend.ingest.document_ir import DocumentIR, DocumentBlock, PageGeometry, content_hash
from backend.ingest.document_claims import claims_from_candidates


def case():
    text = 'ScH (200 GPa) Fm-3m a=b=c=3.57401'
    ir = DocumentIR(document_id='si', source_file_id='si', source_sha256='a'*64,
        parse_profile='complementary', parser={'name':'test','version':'1','mode':'text'},
        pages=[PageGeometry(pdf_page=30,width=600,height=800)],
        blocks=[DocumentBlock(block_id='table-row',block_type='paragraph',pdf_page=30,
            reading_order=0,text=text,content_hash=content_hash(text))])
    evidence={'file_id':'si','pdf_page':30,'block_id':'table-row','quote':text}
    state={'state_key':'structure-state-same-reported-geometry','material':'ScH',
        'pressure_value_gpa':200,'reported_space_group_symbol':'Fm-3m',
        'state_kind':'theoretical','structure_optimization':'unknown','property_modules':[],
        'structure':{'sources':[evidence]}}
    return state,ir


def test_structure_generated_parent_uses_its_owned_locatable_original_sources():
    state,ir=case();before=deepcopy(state)
    claims=claims_from_candidates({'material_states':[state]},{'si':ir})
    assert len(claims)==1 and claims[0].status=='validated'
    assert claims[0].evidences[0].block_id=='table-row'
    assert state==before  # 仅建立来源Claim，不改值或伪造科学核对。


def test_foreign_source_or_existing_explicit_parent_source_is_not_replaced():
    state,ir=case();state['structure']['sources'][0]['file_id']='other'
    assert claims_from_candidates({'material_states':[state]},{'si':ir})[0].status=='uncertain'
    state,ir=case();state['evidences']=[dict(state['structure']['sources'][0],block_id='bad')]
    assert claims_from_candidates({'material_states':[state]},{'si':ir})[0].status=='uncertain'
    state,ir=case();state['state_key']='ordinary-unassigned-state'
    assert claims_from_candidates({'material_states':[state]},{'si':ir})[0].status=='uncertain'
