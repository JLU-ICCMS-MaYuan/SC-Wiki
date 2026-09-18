"""真实 TS 批准载荷进入 Python prepare-review；数据库与人工确认均为隔离夹具。"""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.api import evidence
from backend.database import Base
from backend.ingest import property_evidence as ev


def test_saved_classifications_reach_real_prepare_review(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(evidence, 'SessionLocal', sessions)
    actor = SimpleNamespace(id=7, role='admin')
    try:
        with sessions.begin() as session:
            session.add(models.Paper(id=1, title='分类回归', year=2026, review_status='pending',
                                     content_revision=1, superconductor_kind='conventional'))
            session.add(models.ChemicalSystem(id=1, paper_id=1, paper_revision=1, system_key='Sn', elements_list=['Sn'], element_count=1))
            session.add(models.Superconductor(id=1, paper_id=1, paper_revision=1, chemical_system_id=1,
                chemical_formula='Sn', formula_normalized='Sn', composition_key='Sn:1', display_name='Sn',
                elements_list=['Sn'], composition={'Sn': 1}, element_ratio={'Sn': 1}))
            session.add(models.MaterialFamily(id=1, code='elemental', name_zh='单质超导体', normalized_name='单质超导体'))
            session.add(models.PaperMaterialFamily(paper_id=1, paper_revision=1, material_family_id=1))
            session.add(models.MaterialState(id=501, state_key='Sn', paper_id=1, paper_revision=1,
                superconductor_id=1, state_kind='unknown', crystal_system='unknown', material_dimensionality='three_dimensional'))
        pending = {'paper': {'superconductor_kind': 'conventional', 'material_families': [{'id': 1, 'name': '单质超导体'}]},
                   'material_states': [{'material_dimensionality': 'three_dimensional', 'structure_families': []}]}
        # 模拟 pending 保存：落库值变化但论文版本与上传快照不变。
        with sessions.begin() as session:
            session.get(models.Paper, 1).superconductor_kind = 'unconventional'
            session.get(models.MaterialState, 501).material_dimensionality = 'two_dimensional'
        with sessions.begin() as session:
            paper = session.get(models.Paper, 1)
            state = session.get(models.MaterialState, 501)
            assert paper.content_revision == 1
            detail = dict(id=paper.id, review_status=paper.review_status, superconductor_kind=paper.superconductor_kind,
                          material_families=[{'id': 1, 'name': '单质超导体'}], material_states=[dict(id=state.id,
                          material_dimensionality=state.material_dimensionality, structure_families=[])])
            snapshot = ev.paper_snapshot(session, paper.id, actor.id, actor.role)
            assert snapshot['records']
            # 已持久化、绑定当前内容和来源的人工确认夹具；生产读取及校验不替换。
            for row in snapshot['records']:
                result = {**row, 'status': 'missing', 'evidences': [], 'decision': {
                    'human_confirmed': True, 'accepted': True, 'actor_user_id': actor.id,
                    'reason': '隔离回归中的已确认分类', 'final_content_hash': row['content_hash'],
                    'source_hash': row['source_hash']}}
                session.add(models.ScientificEvidenceCheck(target='paper', target_id='1', item_key=row['item_key'],
                    content_hash=row['content_hash'], source_hash=row['source_hash'], rule_version=snapshot['rule_version'],
                    result=result, resolutions={}, actor_user_id=actor.id))
        process = subprocess.run(['node', str(Path(__file__).with_name('review-classification-payload.mjs'))],
                                 input=json.dumps(dict(detail=detail, pendingValues=pending)), text=True,
                                 capture_output=True, check=True)
        payload = json.loads(process.stdout)
        request = evidence.PrepareReview(paper_id=1, expected_version=snapshot['version'], classifications=payload)
        prepared = evidence.prepare_review(request, actor)
        assert prepared['version'] == snapshot['version']
        assert payload['superconductor_kind'] == 'unconventional'
        assert payload['material_states'][0]['material_dimensionality'] == 'two_dimensional'
        for field in ('kind', 'dimension', 'version', 'family', 'structure'):
            invalid = request.model_copy(deep=True)
            if field == 'kind': invalid.classifications['superconductor_kind'] = 'conventional'
            elif field == 'dimension': invalid.classifications['material_states'][0]['material_dimensionality'] = 'three_dimensional'
            elif field == 'version': invalid.expected_version = 'outdated'
            elif field == 'family': invalid.classifications['material_families'] = [{'id': 99, 'name': '旧家族'}]
            else: invalid.classifications['material_states'][0]['structure_families'] = [{'id': 99, 'is_primary': True}]
            with pytest.raises(HTTPException) as error:
                evidence.prepare_review(invalid, actor)
            assert error.value.status_code == 409
            assert error.value.detail['code'] == 'evidence_stale'
        with pytest.raises(HTTPException) as error:
            evidence.prepare_review(request, SimpleNamespace(id=8, role='user'))
        assert error.value.status_code == 403
        with sessions.begin() as session:
            session.get(models.Paper, 1).uploaded_by_user_id = actor.id
        with pytest.raises(HTTPException) as error:
            evidence.prepare_review(request, actor)
        assert error.value.status_code == 403
    finally:
        engine.dispose()
