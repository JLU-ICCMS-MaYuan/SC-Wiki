"""#235：批准来源的精确定位和按需重建；缓存不构成访问授权。"""
from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select

from backend import models
from backend.ingest.document_ir import DocumentIR, content_hash
from backend.ingest.pdf_regions import object_region, render_region_image


def _entries(session, paper, *, files=None, block_ids=None):
    statement=select(models.PaperFile).where(models.PaperFile.paper_id==paper.id,
        models.PaperFile.paper_revision==paper.content_revision)
    allowed_hashes={f.get('sha256') for f in files} if files is not None else None
    entries=[]
    for file in session.scalars(statement):
        if allowed_hashes is not None and file.sha256 not in allowed_hashes:continue
        run=session.scalar(select(models.PaperDocumentParserRun).where(
            models.PaperDocumentParserRun.paper_file_id==file.id,
            models.PaperDocumentParserRun.paper_id==paper.id,
            models.PaperDocumentParserRun.paper_revision==paper.content_revision
            ).order_by(models.PaperDocumentParserRun.id.desc()))
        if run is None:continue
        ir=DocumentIR.model_validate(run.document_json)
        if ir.source_sha256!=file.sha256:continue
        for block in ir.blocks:
            if block.metadata.get('selected_for_reading') is False or block.bbox is None:continue
            reading=block.metadata.get('chart_reading') or {}
            registered_id=(ir.coverage.get('visual_source_regions') or {}).get(block.block_id)
            if block.block_type not in {'figure','table','formula','table_cell'} and not reading and not registered_id and not (block_ids is not None and block.block_id in block_ids):continue
            locator=reading.get('region_locator') or block.metadata.get('region_locator')
            if locator is None and registered_id:
                locator=(ir.coverage.get('visual_regions') or {}).get(registered_id)
            if locator is None:
                locator=next((v for v in (ir.coverage.get('visual_regions') or {}).values()
                    if v.get('pdf_page')==block.pdf_page and v.get('bbox_page')==list(block.bbox)),None)
            item={'source_id':'visual-'+content_hash(paper.id,paper.content_revision,file.sha256,block.block_id,run.id),
                'paper_id':paper.id,'paper_revision':paper.content_revision,'file_id':str(file.id),
                'source_sha256':file.sha256,'pdf_page':block.pdf_page,'block_id':block.block_id,
                'kind':str(block.block_type),'text':block.text,'locator':deepcopy(locator),
                'complete_figure':deepcopy(reading.get('complete_figure')),
                'reading':{k:deepcopy(reading[k]) for k in ('quantity','unit','value_number','value_raw','reading_precision','point') if k in reading}}
            entries.append((item,file,ir))
    return entries


def _approved(session, paper_id):
    from backend.rag.search.property_records import approved_paper_conditions
    return session.scalar(select(models.Paper).where(models.Paper.id==paper_id,*approved_paper_conditions()))


def visual_catalog(session, paper_id):
    paper=_approved(session,paper_id)
    frozen=_published_sources(session,paper) if paper else None
    if frozen is not None:return [deepcopy(item) for item in frozen[0].values()]
    return [item for item,_,_ in _entries(session,paper)] if paper else []


def _published_sources(session,paper):
    """已有新交接时只读批准快照；旧版无定位目录仍走有界原IR兼容。"""
    from backend.services.manuscript_handoffs import latest,snapshot_event
    from backend.ingest.field_sources import expand
    handoff=latest(session,paper.id)
    if not handoff or not handoff.get('published_snapshot_id'):return None
    event=snapshot_event(session,paper.id,handoff['published_snapshot_id'])
    frozen=expand(session,event.classification_snapshot['manuscript_snapshot'])
    if 'visual_sources' not in frozen:return None
    return frozen['visual_sources'],frozen['files']


def capture_visual_sources(session, paper, files, records=None):
    """交接事务内捕获当时定位；无新来源时不改变旧稿指纹。"""
    if not files:return {}
    referenced=set()
    def collect(value):
        if isinstance(value,dict):
            if value.get('block_id'):referenced.add(value['block_id'])
            for child in value.values():collect(child)
        elif isinstance(value,list):
            for child in value:collect(child)
    if records is not None:
        from backend.ingest.field_sources import expand
        records=expand(session,records)
        collect(records)
    if records is not None and not referenced:return {}
    captured={}
    for item,file,ir in _entries(session,paper,files=files,block_ids=referenced if records is not None else None):
        if records is not None and item['block_id'] not in referenced:continue
        if item['locator'] is None and records is not None:
            from backend.storage.paths import resolve_file
            path=resolve_file(file.stored_path,size=int(file.size),sha256=file.sha256,
                media_type=file.media_type or 'application/pdf',namespace=str(paper.id))
            item['locator']=object_region(ir,path,item['block_id'])
        if item['locator']:captured[item['source_id']]=item
    hashes={f.get('sha256') for f in files}
    def adopted(value):
        if isinstance(value,list):
            for child in value:adopted(child)
        elif isinstance(value,dict):
            locator=value.get('region_locator')
            if locator and locator.get('source_sha256') in hashes and value.get('block_id'):
                for key,item in list(captured.items()):
                    if item['source_sha256']==locator['source_sha256'] and item['block_id']==value['block_id']:
                        del captured[key]
                identity='visual-'+content_hash(paper.id,paper.content_revision,locator['region_id'],value['block_id'])
                captured[identity]={'source_id':identity,'paper_id':paper.id,'paper_revision':paper.content_revision,
                    'file_id':locator['file_id'],'source_sha256':locator['source_sha256'],'pdf_page':locator['pdf_page'],
                    'block_id':value['block_id'],'kind':locator['kind'],'text':value.get('quote',''),
                    'locator':deepcopy(locator),'complete_figure':deepcopy(value.get('complete_figure')),'reading':{}}
            for child in value.values():adopted(child)
    if records is not None:adopted(records)
    return captured


def read_visual_source(session, paper_id, source_id, *, cache_dir=None):
    paper=_approved(session,paper_id)
    if paper is None:raise ValueError('论文版本未批准或不可公开读取')
    frozen=_published_sources(session,paper)
    if frozen is not None:
        item=frozen[0].get(source_id)
        if item is None:raise ValueError('来源不属于当前批准快照')
        file=next((f for f in frozen[1] if f.get('sha256')==item['source_sha256']),None)
        if file is None:raise ValueError('批准来源的原件引用缺失')
        from backend.storage.paths import resolve_file
        path=resolve_file(file['stored_path'],size=int(file['size']),sha256=file['sha256'],
            media_type=file.get('media_type') or 'application/pdf')
        return {'source':deepcopy(item),'image':render_region_image(path,item['locator'],cache_dir=cache_dir)}
    entry=next((v for v in _entries(session,paper) if v[0]['source_id']==source_id),None)
    if entry is None:raise ValueError('来源不属于当前已批准论文版本')
    item,file,ir=entry
    from backend.storage.paths import resolve_file
    path=resolve_file(file.stored_path,size=int(file.size),sha256=file.sha256,
        media_type=file.media_type or 'application/pdf',namespace=str(paper.id))
    locator=item['locator'] or object_region(ir,path,item['block_id'])
    if locator['source_sha256']!=file.sha256:raise ValueError('来源定位与原件摘要不一致')
    return {'source':item,'image':render_region_image(path,locator,cache_dir=cache_dir)}


def read_snapshot_visual_source(session, paper, user, snapshot_id, source_id, *, cache_dir=None):
    """复用历史访问权限；只用冻结的文件和区域，不查询当前定位替代。"""
    from backend.services.manuscript_handoffs import readable, snapshot_event
    from backend.ingest.field_sources import expand
    from backend.storage.paths import resolve_file
    readable(paper,user)
    event=snapshot_event(session,paper.id,snapshot_id)
    frozen=expand(session,event.classification_snapshot['manuscript_snapshot'])
    source=(frozen.get('visual_sources') or {}).get(source_id)
    if source is None:raise ValueError('历史快照没有该定位来源')
    file=next((f for f in frozen['files'] if f.get('sha256')==source['source_sha256']),None)
    if file is None:raise ValueError('历史原件引用缺失，未改用当前原件')
    path=resolve_file(file['stored_path'],size=int(file['size']),sha256=file['sha256'],
        media_type=file.get('media_type') or 'application/pdf')
    return {'source':source,'image':render_region_image(path,source['locator'],cache_dir=cache_dir)}
