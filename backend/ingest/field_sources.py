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
    packed=compact_contexts(session,visit(result))
    session.execute(delete(ScientificFieldSourceUse).where(
        ScientificFieldSourceUse.work_key==work_key,ScientificFieldSourceUse.item_key==record['item_key']))
    for (source_id,role),bindings in uses.items():
        session.add(ScientificFieldSourceUse(work_key=work_key,item_key=record['item_key'],source_id=source_id,
            role=role,binding_json={'bindings':bindings}))
    return packed

CONTEXT_CONTRACT = 'shared-context-v1'
CONTEXT_KEYS = frozenset({'legacy_evidences', 'legacy_source_history'})


def compact_contexts(session, value, *, keys=CONTEXT_KEYS, store=None):
    """只共享大块只读资料；值、理由、范围和整稿身份不参与替换。"""
    def save(context_id, item, path):
        if session.get(ScientificSourceItem, context_id) is None:
            session.add(ScientificSourceItem(id=context_id, namespace=CONTEXT_CONTRACT,
                payload={'contract': CONTEXT_CONTRACT, 'value': deepcopy(item)}))
            session.flush()
    put = store or save
    def visit(item, path=()):
        if isinstance(item, list):
            return [visit(v, (*path, i)) for i,v in enumerate(item)]
        if not isinstance(item, dict):
            return deepcopy(item)
        if set(item) == {'shared_context_ref'}:
            return deepcopy(item)
        output = {}
        for key, content in item.items():
            here = (*path, key)
            if key in keys and isinstance(content, (dict,list)) and len(encode(content).encode()) >= 4096:
                identity = hashlib.sha256(encode([CONTEXT_CONTRACT, content]).encode()).hexdigest()
                put(identity, content, here)
                output[key] = {'shared_context_ref': identity}
            else:
                output[key] = visit(content, here)
        return output
    return visit(value)


def expand(session,value):
    # 两种引用共用不可变目录；按所需身份批量读取，不扫描整表。
    refs=set()
    def collect(item):
        if isinstance(item,dict):
            if set(item)=={'shared_context_ref'}:
                refs.add(item['shared_context_ref'])
            elif 'source_ref' in item:
                refs.add(item['source_ref'])
            else:
                for v in item.values(): collect(v)
        elif isinstance(item,list):
            for v in item: collect(v)
    collect(value)
    sources={}
    while refs-set(sources):
        missing=refs-set(sources)
        rows=list(session.scalars(select(ScientificSourceItem).where(ScientificSourceItem.id.in_(missing))))
        if {s.id for s in rows}!=missing:
            raise ValueError('采用来源引用不存在，拒绝使用当前稿替代')
        for source in rows:
            sources[source.id]=source.payload
            collect(source.payload)
    def visit(item, ancestors=frozenset()):
        if isinstance(item,dict):
            shared=set(item)=={'shared_context_ref'}
            identity=item.get('shared_context_ref') if shared else item.get('source_ref')
            if identity is not None:
                if identity in ancestors:
                    raise ValueError('采用来源引用循环')
                payload=sources[identity]
                if shared:
                    if not isinstance(payload,dict) or payload.get('contract')!=CONTEXT_CONTRACT or 'value' not in payload:
                        raise ValueError('共享上下文格式无效')
                    return visit(payload['value'],ancestors|{identity})
                if not isinstance(payload,dict):
                    raise ValueError('片段来源格式无效')
                return visit({**deepcopy(payload),**deepcopy(item.get('binding') or {})},ancestors|{identity})
            return {k:visit(v,ancestors) for k,v in item.items()}
        if isinstance(item,list):return [visit(v,ancestors) for v in item]
        return item
    return visit(value)
