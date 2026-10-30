"""显式Tc组的规范存储与有界读取投影；不猜测旧记录的分组。"""
from copy import deepcopy
VERSION = 1
KEY = 'tc_contexts'

def expand_module(module):
    module=deepcopy(module)
    metadata=module.setdefault('metadata',{})
    directory=metadata.pop(KEY,None)
    if directory is None:return module
    if directory.get('version')!=VERSION:raise ValueError('未知Tc共同资料版本')
    groups=directory.get('groups') or {}
    methods=directory.get('methods') or {}
    for record in module.get('records') or []:
        payload=record.setdefault('payload',{})
        ref=payload.pop('tc_context_ref',None)
        if ref is None:continue
        if not isinstance(ref,dict) or ref.get('version')!=VERSION:
            raise ValueError('未知Tc共同资料引用版本')
        group=groups.get(ref.get('group_key'));method=methods.get(ref.get('group_key'),{}).get(ref.get('method_key'))
        if group is None or method is None:raise ValueError('Tc共同资料引用不存在')
        own=deepcopy(payload.get('parameters') or {})
        common=deepcopy(group.get('parameters') or {})
        if own.get('extensions'):
            common['extensions']=[*(common.get('extensions') or []),*own.pop('extensions')]
        payload['parameters']={**common,**own}
        payload['calculation_conditions']=deepcopy(group.get('calculation_conditions') or {})
        if ref.get('empty_parameter_extensions'):
            payload['parameters'].setdefault('extensions',[])
        if ref.get('empty_condition_extensions'):
            payload['calculation_conditions'].setdefault('extensions',[])
        layout=ref.get('association_layout')
        if isinstance(layout,list):
            shared=group.get('source_associations') or []
            own=payload.get('source_associations') or []
            restored=[]
            for index in layout:
                if not isinstance(index,dict) or len(index)!=1 or not set(index).issubset({'shared','point'}):
                    raise ValueError('共同来源使用位置无效')
                kind,position=next(iter(index.items()))
                values=shared if kind=='shared' else own
                if type(position) is not int or position<0 or position>=len(values):
                    raise ValueError('共同来源使用位置不存在')
                restored.append(deepcopy(values[position]))
            payload['source_associations']=restored
        record['method_code']=method.get('method_code');record['method_raw']=method.get('method_raw')
    return module

def compact_module(module):
    module=expand_module(module)
    groups,methods={},{}
    candidates={}
    def common_association(item):
        path=str(item.get('target_path') or '').replace('/','.').lstrip('.')
        return path.startswith('payload.calculation_conditions.') or path.startswith('payload.parameters.') and not path.startswith('payload.parameters.mu_star')
    for record in module.get('records') or []:
        identity=(record.get('payload') or {}).get('tc_group') or {}
        if record.get('record_type')!='predicted_tc' or not identity.get('group_key'):continue
        entries=(record.get('payload') or {}).get('source_associations') or []
        applicable=[item for item in entries if isinstance(item,dict) and common_association(item)]
        group_key=identity['group_key']
        candidates[group_key]=[item for item in candidates[group_key] if item in applicable] if group_key in candidates else applicable
    for record in module.get('records') or []:
        payload=record.get('payload') or {}
        identity=payload.get('tc_group')
        if record.get('record_type')!='predicted_tc' or not isinstance(identity,dict):continue
        group_key=identity.get('group_key');method_key=identity.get('method_key')
        if not group_key or not method_key:continue
        parameters=deepcopy(payload.get('parameters') or {})
        point={k:parameters.pop(k) for k in list(parameters) if k in {'mu_star','mu_star_status'}}
        extensions=parameters.pop('extensions',None)
        point_extensions=[e for e in extensions or [] if e.get('key') in {'mu_star','mu_star_reported','mu_star_reported_range'}]
        shared_extensions=[e for e in extensions or [] if e not in point_extensions]
        if shared_extensions:parameters['extensions']=shared_extensions
        if point_extensions:point['extensions']=point_extensions
        conditions=deepcopy(payload.get('calculation_conditions') or {})
        empty_conditions=conditions.get('extensions')==[]
        if empty_conditions:conditions.pop('extensions')
        shared_associations=candidates.get(group_key) or []
        group={'parameters':parameters,'calculation_conditions':conditions}
        if shared_associations:group['source_associations']=deepcopy(shared_associations)
        method={'method_code':record.get('method_code'),'method_raw':record.get('method_raw')}
        if group_key in groups and groups[group_key]!=group:
            raise ValueError('同一Tc组的共同条件不一致，不能静默合并')
        groups[group_key]=group
        methods.setdefault(group_key,{})
        if method_key in methods[group_key] and methods[group_key][method_key]!=method:
            raise ValueError('同一Tc方法身份对应不同方法')
        methods[group_key][method_key]=method
        payload['parameters']=point
        payload.pop('calculation_conditions',None)
        payload['tc_context_ref']={'version':VERSION,'group_key':group_key,'method_key':method_key,
            **({'empty_parameter_extensions':True} if extensions==[] else {}),
            **({'empty_condition_extensions':True} if empty_conditions else {})}
        if shared_associations:
            own_associations=[];layout=[]
            for item in payload.get('source_associations') or []:
                if item in shared_associations:layout.append({'shared':shared_associations.index(item)})
                else:
                    layout.append({'point':len(own_associations)});own_associations.append(item)
            payload['source_associations']=own_associations
            payload['tc_context_ref']['association_layout']=layout
        record['payload']=payload;record['method_code']=None;record['method_raw']=None
    if groups:module.setdefault('metadata',{})[KEY]={'version':VERSION,'groups':groups,'methods':methods}
    return module

def map_draft(draft,compact=False):
    draft=deepcopy(draft)
    for state in draft.get('material_states') or []:
        state['property_modules']=[(compact_module if compact else expand_module)(module)
            for module in state.get('property_modules') or []]
    return draft

def expanded_record(record):
    from backend.services.scientific_draft_rewrite import _record_snapshot
    data=_record_snapshot(record,module_code='')
    if not (record.payload_json or {}).get('tc_context_ref'):return data
    return expand_module({'metadata':record.module.metadata_json or {},'records':[data]})['records'][0]
