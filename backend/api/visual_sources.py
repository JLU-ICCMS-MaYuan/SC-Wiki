"""仅公开当前已批准版本的可重建来源，不需要模型请求或模型凭据。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from backend.database import get_db
from backend.rag.config import settings
from backend.rag.visual_sources import visual_catalog, read_visual_source

router=APIRouter(prefix='/api/rag/visual-sources',tags=['visual-sources'])


@router.get('/{paper_id}')
def sources(paper_id:int,session=Depends(get_db,use_cache=False)):
    return {'paper_id':paper_id,'sources':visual_catalog(session,paper_id)}


@router.get('/{paper_id}/{source_id}/image')
def image(paper_id:int,source_id:str,session=Depends(get_db,use_cache=False)):
    try:
        result=read_visual_source(session,paper_id,source_id,cache_dir=settings.sc_wiki_data_dir/'visual_region_cache')
    except ValueError as exc:
        raise HTTPException(404,detail=str(exc)) from exc
    return Response(result['image']['png'],media_type='image/png',
        headers={'Cache-Control':'private, no-cache','ETag':result['image']['image_sha256']})
