"""交接只保存当前谱事实；不读取旧运行或复制编辑器中间历史。"""
from copy import deepcopy
from backend.services import spectra
from backend.ingest.property_evidence import digest

def capture(session,paper,draft,files):
    if not spectra.available(session):
        return None
    states=deepcopy(draft.get('material_states') or [])
    for index,state in enumerate(states):
        state['state_key']=state.get('state_key') or f'state-{index+1}'
        state['_spectrum_structure_hashes']=spectra.structure_dependencies(draft,index)
    source=draft.get('_spectrum_target_id')
    context=dict(target='revision' if source else 'paper',target_id=source or str(paper.id),
        paper_revision=paper.content_revision,states=states,files=files,privileged=True,
        version='frozen',can_edit=False,can_review=False)
    listing=spectra.listing(session,context)
    output=[]
    for item in listing['items']:
        item=deepcopy(item)
        stable=digest([item.get('state_key'),sorted(curve.get('id','') for curve in item['result'].get('curves') or []),item['source'].get('source_sha256'),item['source'].get('pdf_page'),
                       item['source'].get('panel_id'),item['source'].get('bbox_pdf_pt')])
        item.update(id=stable,version=1,historical=False)
        item.pop('recorded_at',None)
        item['run']={k:v for k,v in item['run'].items() if k not in {'id','error_message'}}
        for name in ('manual_documents','manual_provenance','state_revalidation'):
            item['result'].pop(name,None)
        for name in ('manual_zero_checks','recalculations','trace_diagnostics','automatic_repairs'):
            (item['result'].get('quality') or {}).pop(name,None)
        image=item['source'].pop('image',None)
        if image:
            file_id='spectrum-image-'+image['sha256']
            if not any(f['file_id']==file_id for f in files):
                files.append(dict(file_id=file_id,stored_path=image['key'],sha256=image['sha256'],
                    size=image['size'],media_type=image['media_type'],kind='png',role='spectrum',
                    original_filename='谱原图-'+image['sha256'][:12]+'.png'))
            item['source']['snapshot_image_file_id']=file_id
        output.append(item)
    return dict(items=output,jobs=[],version='frozen',can_edit=False,can_review=False)
