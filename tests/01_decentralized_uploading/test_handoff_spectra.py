"""当前谱随整稿冻结；审核私稿、公开谱和退回稿分别持有数据。"""
from copy import deepcopy
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from backend import models
from backend.services import spectra,manuscript_handoffs as h,workdrafts as w
from test_workdraft_ownership import context

def test_private_spectrum_copy_return_and_frozen_points(context,monkeypatch):
    session,paper,(author,reviewer,other)=context
    collection=models.SpectrumCollection(id='a'*32,target='paper',target_id=str(paper.id),owner_id=author.id,
        paper_id=paper.id,paper_revision=paper.content_revision,source_key='isolated',panel_key='panel',
        state_signature=spectra.state_signature(None),source_json={'source_sha256':'0'*64,'source_name':'隔离谱夹具','pdf_page':1},
        review_json={},version=1)
    session.add(collection);session.flush()
    run=models.SpectrumRun(id='b'*32,collection_id=collection.id,input_hash='f'*64,algorithm_version='isolated',
        status='succeeded',calibration_json={},result_json={'curves':[{'id':'curve','kind':'phonon_dos',
        'points':[{'frequency_thz':1,'value':2}]}]})
    session.add(run);session.flush();collection.current_run_id=run.id;session.commit()
    lease=w.open_draft(session,'paper',str(paper.id),reviewer);session.commit()
    revision_before=lease.revision
    context=spectra.context(session,'paper',str(paper.id),reviewer,write=True)
    assert context['target']=='revision' and context['can_review']
    private_id=context['target_id']
    private=session.scalar(select(models.SpectrumCollection).where(models.SpectrumCollection.target_id==private_id))
    assert private.id!=collection.id
    current=session.get(models.SpectrumRun,private.current_run_id)
    changed=deepcopy(current.result_json);changed['curves'][0]['points'][0]['value']=9
    current.result_json=changed;session.commit()
    assert w.row(session,'paper',str(paper.id)).revision>revision_before
    received=spectra.context(session,'paper',str(paper.id),other)
    assert not received['can_edit'] and not received['can_review']
    assert spectra.listing(session,received)['items'][0]['result']['curves'][0]['points'][0]['value']==2
    with pytest.raises(HTTPException):spectra.context(session,'paper',str(paper.id),other,write=True)
    monkeypatch.setenv('JWT_SECRET_KEY','isolated-handoff-spectra-secret')
    from backend.api.manuscript_handoffs import return_to_author,ReturnRevision
    returned=return_to_author(paper.id,ReturnRevision(operation_id='spectra-return',
        expected_snapshot_id=h.latest(session,paper.id)['snapshot_id']),user=reviewer,session=session)
    snapshot=returned['handoff']['snapshot_id']
    saved=session.get(models.PaperRevisionDraft,paper.id)
    author_context=spectra.context(session,'revision',saved.revision_id,author,write=True)
    returned_collection=session.scalar(select(models.SpectrumCollection).where(models.SpectrumCollection.target_id==saved.revision_id))
    returned_run=session.get(models.SpectrumRun,returned_collection.current_run_id)
    assert returned_run.result_json['curves'][0]['points'][0]['value']==9
    modified=deepcopy(returned_run.result_json);modified['curves'][0]['points'][0]['value']=12
    returned_run.result_json=modified;session.commit()
    frozen=h.public_snapshot(session,paper,author,snapshot)['content']
    assert frozen['spectra']['items'][0]['result']['curves'][0]['points'][0]['value']==9
    assert '_spectrum_target_id' not in frozen['draft']
    with pytest.raises(HTTPException):spectra.context(session,'revision',private_id,reviewer,write=True)
