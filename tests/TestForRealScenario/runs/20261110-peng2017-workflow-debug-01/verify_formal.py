"""只读核验本轮正式论文；参数依分组/方法真实所有权展开。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv('.env')
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from backend.database import engine
from backend import models
from backend.ingest.tc_contexts import expanded_record

ROOT = Path(__file__).resolve().parent
DOI = '10.1103/PhysRevLett.119.107001'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--paper-id', type=int)
parser.add_argument('--expect', choices=['absent', 'pending', 'rejected', 'approved'])
args = parser.parse_args()
with Session(engine, autoflush=False) as session:
    session.execute(text('SET TRANSACTION READ ONLY'))
    paper = session.scalars(select(models.Paper).where(models.Paper.doi == DOI)).one_or_none()
    result = {'at': datetime.now(timezone.utc).isoformat(),
              'target': {'host': engine.url.host, 'port': engine.url.port, 'database': engine.url.database},
              'doi': DOI, 'paper': None}
    if paper:
        if args.paper_id is not None:
            assert paper.id == args.paper_id, '不能用同体系其他论文代验'
        active = json.loads((ROOT / 'active-task.json').read_text())
        assert paper.upload_task_id == active['task_id'], '论文并非本轮任务'
        result['paper'] = {key: getattr(paper, key) for key in (
            'id', 'title', 'doi', 'upload_task_id', 'review_status', 'content_revision',
            'approved_revision', 'reviewed_by_user_id', 'reviewed_at', 'review_comment')}
        reviewer = session.get(models.User, paper.reviewed_by_user_id) if paper.reviewed_by_user_id else None
        result['reviewer_email'] = reviewer.email if reviewer else None
        result['files'] = [{key: getattr(row, key) for key in (
            'id', 'role', 'sha256', 'size', 'original_filename', 'paper_revision')}
            for row in session.scalars(select(models.PaperFile).where(models.PaperFile.paper_id == paper.id))]
        result['states'] = []
        for state in session.scalars(select(models.MaterialState).where(models.MaterialState.paper_id == paper.id)):
            item = {key: getattr(state, key) for key in (
                'id', 'state_key', 'paper_revision', 'material_name', 'pressure_value_gpa',
                'reported_space_group_symbol', 'reported_space_group_number', 'structure_optimization', 'note')}
            item['modules'] = [{'id': module.id, 'module_key': module.module_key,
                'code': module.module_code, 'metadata': module.metadata_json,
                'records': [{'id': record.id, **expanded_record(record),
                    'evidence_links': [{'id': link.paper_evidence_id, 'field_path': link.field_path,
                                       'role': link.evidence_role} for link in record.evidences]}
                    for record in module.records]} for module in state.property_modules]
            item['structures'] = [{key: getattr(row, key) for key in (
                'id', 'paper_revision', 'structure_format', 'structure_text', 'structure_hash',
                'cell_parameters', 'atom_count', 'calculation_code', 'method_parameters', 'metadata_json', 'source_locator')}
                for row in session.scalars(select(models.StructureModel).where(
                    models.StructureModel.material_state_id == state.id))]
            result['states'].append(item)
        result['history'] = [{key: getattr(row, key) for key in (
            'id', 'paper_revision', 'event_type', 'actor_user_id', 'actor_username_snapshot',
            'review_status', 'review_comment', 'occurred_at')}
            for row in session.scalars(select(models.PaperHistoryEvent).where(
                models.PaperHistoryEvent.paper_id == paper.id).order_by(models.PaperHistoryEvent.id))]
    path = ROOT / ('formal-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(json.dumps({'evidence': path.name, 'target': result['target'], 'paper': result['paper'],
                      'states': len(result.get('states', [])), 'history': len(result.get('history', []))},
                     ensure_ascii=False, default=str))
    if args.expect == 'absent':
        assert paper is None
    elif args.expect:
        assert paper and paper.review_status == args.expect
    session.rollback()
