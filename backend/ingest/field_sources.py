"""不可变来源目录与当前采用关系；字段值仍由工作稿持有。"""
from copy import deepcopy
import hashlib
import json
from sqlalchemy import delete, select, inspect
from backend.workdraft_models import ScientificSourceItem, ScientificFieldSourceUse

LISTS = {'evidences','supplemental_evidences','fact_evidences','scope_evidences'}
BINDING = {'field_path','scope','explanation','basis_kind','stage'}

def encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)

def compact(session,snapshot,record,result):
    if not inspect(session.connection()).has_table(ScientificSourceItem.__tablename__):
        if snapshot.get('_workdraft_epoch'):
            raise ValueError('字段采用来源目录尚未完成迁移')
        return deepcopy(result)  # 有界旧schema兼容，不在读取时迁移。
    namespace=str(snapshot.get('_source_digest') or record.get('paper_source_hash') or record['source_hash'])
    work_key=snapshot['target']+':'+str(snapshot['target_id'])
    uses={}
    def visit(value):
        if isinstance(value,list):return [visit(v) for v in value]
        if not isinstance(value,dict):return deepcopy(value)
        out={}
        for key,item in value.items():
            if key in LISTS and isinstance(item,list):
                refs=[]
                for evidence in item:
                    if not isinstance(evidence,dict):continue
                    source={k:v for k,v in evidence.items() if k not in BINDING}
                    binding={k:v for k,v in evidence.items() if k in BINDING}
                    source_id=hashlib.sha256(encode([namespace,source]).encode()).hexdigest()
                    if session.get(ScientificSourceItem,source_id) is None:
                        session.add(ScientificSourceItem(id=source_id,namespace=namespace,payload=source))
                        session.flush()
                    refs.append({'source_ref':source_id,'binding':binding})
                    role=('shared' if record.get('record_group_key') else 'direct') if key in {'evidences','fact_evidences'} else 'context'
                    uses.setdefault((source_id,role),[]).append(binding)
                out[key]=refs
            else:out[key]=visit(item)
        return out
    packed=visit(result)
    session.execute(delete(ScientificFieldSourceUse).where(
        ScientificFieldSourceUse.work_key==work_key,ScientificFieldSourceUse.item_key==record['item_key']))
    for (source_id,role),bindings in uses.items():
        session.add(ScientificFieldSourceUse(work_key=work_key,item_key=record['item_key'],source_id=source_id,
            role=role,binding_json={'bindings':bindings}))
    return packed

def expand(session,value):
    refs=set()
    def collect(item):
        if isinstance(item,dict):
            if 'source_ref' in item:refs.add(item['source_ref'])
            else:
                for v in item.values():collect(v)
        elif isinstance(item,list):
            for v in item:collect(v)
    collect(value)
    sources={s.id:s.payload for s in session.scalars(select(ScientificSourceItem).where(ScientificSourceItem.id.in_(refs)))} if refs else {}
    def visit(item):
        if isinstance(item,dict):
            if 'source_ref' in item:
                if item['source_ref'] not in sources:raise ValueError('采用来源引用不存在，拒绝使用当前稿替代')
                return {**deepcopy(sources[item['source_ref']]),**deepcopy(item.get('binding') or {})}
            return {k:visit(v) for k,v in item.items()}
        if isinstance(item,list):return [visit(v) for v in item]
        return item
    return visit(value)
