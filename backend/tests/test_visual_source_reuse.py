import hashlib
import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.database import Base
from backend import models
from backend.tests.test_pdf_regions import source
from backend.ingest.pdf_regions import region_locator
from backend.rag.visual_sources import visual_catalog, read_visual_source, capture_visual_sources


def database(tmp_path):
    path, ir=source(tmp_path)
    locator=region_locator(path,'main',ir.source_sha256,1,[30,35,210,218])
    ir.blocks[0].metadata['region_locator']=locator
    ir.coverage['visual_regions']={locator['region_id']:locator}
    url=os.environ.get('SCWIKI_VISUAL_TEST_DATABASE_URL')
    if url:
        from backend.tests.mysql_isolation import require_isolated_mysql
        engine=create_engine(url)
        require_isolated_mysql(engine)
    else:
        engine=create_engine('sqlite:///:memory:',connect_args={'check_same_thread':False})
        Base.metadata.create_all(engine)
    session=Session(engine)
    if url and session.get(models.User,2) is None:
        session.add(models.User(id=2,email='source-fixture@isolation.invalid',username='source-fixture',
            password_hash='test-only',real_name='来源隔离测试',role='user'))
        session.flush()
    paper=models.Paper(year=2026,review_status='approved',content_revision=1,approved_revision=1)
    session.add(paper);session.flush()
    file=models.PaperFile(paper_id=paper.id,paper_revision=1,role='main',sort_order=0,
        original_filename='source.pdf',stored_path=str(path),sha256=ir.source_sha256,size=path.stat().st_size)
    session.add(file);session.flush()
    run=models.PaperDocumentParserRun(paper_id=paper.id,paper_revision=1,paper_file_id=file.id,
        parse_profile='complementary',parser_name='fixture',parser_version='1',mode='text',
        status='succeeded',reading_state='ir_ready',document_json=ir.model_dump(mode='json'))
    session.add(run);session.flush()
    return session,paper,file,path,locator


def test_approved_sources_reuse_cache_and_recheck_visibility(tmp_path,monkeypatch):
    from backend.storage import paths
    session,paper,file,path,locator=database(tmp_path)
    monkeypatch.setattr(paths,'resolve_file',lambda *a,**k:path)
    rows=visual_catalog(session,paper.id)
    assert rows and 'stored_path' not in json.dumps(rows)
    first=read_visual_source(session,paper.id,rows[0]['source_id'],cache_dir=tmp_path/'cache')
    second=read_visual_source(session,paper.id,rows[0]['source_id'],cache_dir=tmp_path/'cache')
    assert first['image']['png']==second['image']['png'] and second['image']['cache_hit']
    paper.review_status='pending';paper.approved_revision=None;session.flush()
    assert visual_catalog(session,paper.id)==[]
    with pytest.raises(ValueError):
        read_visual_source(session,paper.id,rows[0]['source_id'],cache_dir=tmp_path/'cache')
    session.close()


def test_capture_is_immutable_reference_only_and_not_latest_locator(tmp_path):
    session,paper,file,path,locator=database(tmp_path)
    captured=capture_visual_sources(session,paper,[{'file_id':str(file.id),'sha256':file.sha256}])
    assert captured and 'data:image' not in json.dumps(captured)
    old=json.loads(json.dumps(captured))
    run=session.query(models.PaperDocumentParserRun).one()
    changed=json.loads(json.dumps(run.document_json))
    changed['coverage']['visual_regions']={}
    changed['blocks'][0]['metadata']={}
    run.document_json=changed;session.flush()
    assert captured==old
    assert next(iter(old.values()))['locator']['bbox_page']==locator['bbox_page']
    session.close()


def test_only_adopted_blocks_are_captured(tmp_path):
    session,paper,file,path,locator=database(tmp_path)
    files=[{'file_id':str(file.id),'sha256':file.sha256}]
    assert not capture_visual_sources(session,paper,files,records=[{'evidences':[{'block_id':'other'}]}])
    assert capture_visual_sources(session,paper,files,records=[{'evidences':[{'block_id':'fig'}]}])
    session.close()


def test_public_api_checks_approval_even_when_cache_exists(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.visual_sources import router
    from backend.database import get_db
    from backend.storage import paths
    session,paper,file,path,locator=database(tmp_path)
    monkeypatch.setattr(paths,'resolve_file',lambda *a,**k:path)
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:session
    client=TestClient(app)
    result=client.get(f'/api/rag/visual-sources/{paper.id}').json()
    source_id=result['sources'][0]['source_id']
    response=client.get(f'/api/rag/visual-sources/{paper.id}/{source_id}/image')
    assert response.status_code==200 and response.content.startswith(b'\x89PNG')
    paper.review_status='pending';paper.approved_revision=None;session.flush()
    assert client.get(f'/api/rag/visual-sources/{paper.id}/{source_id}/image').status_code==404
    session.close()


def test_rag_tool_image_reaches_model_user_content_without_breaking_call_id(monkeypatch):
    from langchain_core.messages import ToolMessage,AIMessage
    from types import SimpleNamespace as NS
    from backend.rag.agent import mentor
    image={'type':'image_url','image_url':{'url':'data:image/png;base64,AA=='}}
    original=ToolMessage(content=[{'type':'text','text':'{"source":"fixed"}'},image],tool_call_id='call-fixed')
    calls=[]
    model=NS(invoke=lambda messages:(calls.append(messages) or AIMessage(content='checked')))
    monkeypatch.setattr(mentor,'_build_llm',lambda:model)
    mentor.mentor_node({'messages':[original]},tools=[])
    assert calls[0][0].tool_call_id=='call-fixed'
    assert calls[0][1].content[1]==image
    assert original.content[1]==image


def test_real_handoff_freezes_only_references_and_history_rebuilds_original(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from backend.services import manuscript_handoffs as h
    from backend.rag.visual_sources import read_snapshot_visual_source
    from backend.storage import paths
    from backend.storage.files import LocalFileStorage
    import backend.storage
    session,paper,file,path,locator=database(tmp_path)
    paper.uploaded_by_user_id=2
    storage=LocalFileStorage(tmp_path/'objects')
    monkeypatch.setattr(backend.storage,'create_storage',lambda:storage)
    def resolve(key,**_):
        return path if str(key)==str(path) else storage._path(str(key))
    monkeypatch.setattr(paths,'resolve_file',resolve)
    author=SimpleNamespace(id=2,username='author',role='user')
    records=[{'field':'tc','evidences':[{'block_id':'fig'}]}]
    files=[{'file_id':str(file.id),'stored_path':str(path),'sha256':file.sha256,
        'size':file.size,'original_filename':'source.pdf','media_type':'application/pdf'}]
    first=h.record_handoff(session,paper,author,action='submit',holder='review',
        draft={},records=records,files=files,initial=True,operation_id='source-first')
    frozen=h.public_snapshot(session,paper,author,first['snapshot_id'])['content']
    assert frozen['visual_sources'] and 'data:image' not in json.dumps(frozen)
    source_id=next(iter(frozen['visual_sources']))
    image=read_snapshot_visual_source(session,paper,author,first['snapshot_id'],source_id,cache_dir=tmp_path/'cache')
    # 新目录固定到批准快照，不能随当前解析IR重定位。
    assert visual_catalog(session,paper.id)[0]['source_id']==source_id
    run=session.query(models.PaperDocumentParserRun).one()
    changed=json.loads(json.dumps(run.document_json));changed['coverage']={};changed['blocks'][0]['metadata']={}
    run.document_json=changed;session.flush()
    reviewer=SimpleNamespace(id=1,username='reviewer',role='admin')
    second=h.record_handoff(session,paper,reviewer,action='return',holder='author',
        draft={'changed':True},records=records,files=files,operation_id='source-next')
    assert second['snapshot_id']!=first['snapshot_id']
    path.unlink()  # 测试工作副本消失，必须使用快照冻结原件。
    rebuilt=read_snapshot_visual_source(session,paper,author,first['snapshot_id'],source_id)
    assert rebuilt['image']['png']==image['image']['png']
    assert read_visual_source(session,paper.id,source_id)['image']['png']==image['image']['png']
    with pytest.raises(HTTPException):
        read_snapshot_visual_source(session,paper,SimpleNamespace(id=99,role='user'),first['snapshot_id'],source_id)
    session.close()


def test_compacted_adopted_source_keeps_refined_locator_and_complete_parent(tmp_path):
    from backend.workdraft_models import ScientificSourceItem
    from backend.ingest.image_reading import ImageReadingTools
    session,paper,file,path,locator=database(tmp_path)
    ir=__import__('backend.ingest.document_ir',fromlist=['DocumentIR']).DocumentIR.model_validate(
        session.query(models.PaperDocumentParserRun).one().document_json)
    tools=ImageReadingTools({'main':ir},{'main':path})
    full,_=tools.call('read_complete_object',{'file_id':'main','block_id':'fig'})
    refined,_=tools.call('adjust_image_region',{'region_id':full['locator']['region_id'],
        'bbox_page':[30,80,100,180],'dpi':600,'reason':'只核对采用的柱'})
    evidence=tools.bind_evidences([{'file_id':'main','block_id':'fig','quote':'ScH6'}])[0]
    session.add(ScientificSourceItem(id='fixed-adoption',namespace='test',payload=evidence));session.flush()
    captured=capture_visual_sources(session,paper,[{'file_id':str(file.id),'sha256':file.sha256}],
        records=[{'evidences':[{'source_ref':'fixed-adoption','binding':{}}]}])
    assert len(captured)==1
    actual=next(iter(captured.values()))
    assert actual['locator']==refined['locator'] and actual['complete_figure']==full['locator']
    session.close()
