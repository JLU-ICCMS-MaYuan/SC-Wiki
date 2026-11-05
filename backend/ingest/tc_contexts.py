"""显式Tc组的规范存储与有界读取投影；不猜测旧记录的分组。"""
from copy import deepcopy
from .tc_methods import field_owns_record, method_identity
VERSION = 2
KEY = 'tc_contexts'

def expand_module(module):
    module=deepcopy(module)
    metadata=module.setdefault('metadata',{})
    directory=metadata.pop(KEY,None)
    if directory is None:return module
    if directory.get('version') not in (1, VERSION):raise ValueError('未知Tc共同资料版本')
    groups=directory.get('groups') or {}
    methods=directory.get('methods') or {}
    for record in module.get('records') or []:
        payload=record.setdefault('payload',{})
        ref=payload.pop('tc_context_ref',None)
        if ref is None:continue
        if not isinstance(ref,dict) or ref.get('version') not in (1, VERSION) or ref['version']>directory['version']:
            raise ValueError('未知Tc共同资料引用版本')
        identity=payload.get('tc_group') or {}
        if any(identity.get(key) is not None and identity[key]!=ref.get(key) for key in ('group_key','method_key')):
            raise ValueError('Tc共同资料引用与显式方法身份不一致')
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
        record['method_code']=method.get('method_code')
        if ref['version']==1 and ref.get('method_raw_owner')!='point':
            record['method_raw']=method.get('method_raw')
        elif ref.get('method_name_present'):
            payload['tc_group']['method_name']=method['method_name']
    return module

def compact_module(module):
    module=expand_module(module)
    groups,methods,method_records={},{},{}
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
        code,name=method_identity(record)
        method={'method_code':code}
        if code in {'other','unknown'} and 'method_name' in identity:
            method['method_name']=name
        elif 'method_name' in identity:
            method['method_name']=identity['method_name']
        if group_key in groups and groups[group_key]!=group:
            raise ValueError('同一Tc组的共同条件不一致，不能静默合并')
        groups[group_key]=group
        methods.setdefault(group_key,{})
        if method_key in methods[group_key] and methods[group_key][method_key]!=method:
            previous=method_records[group_key,method_key]
            raise ValueError(f'同一Tc方法身份对应不同方法：组 {group_key}，方法 {method_key}，'
                             f'记录 {previous} 与 {record.get("record_key")}；'
                             f'{methods[group_key][method_key]} 与 {method}')
        methods[group_key][method_key]=method
        method_records.setdefault((group_key,method_key),record.get('record_key'))
        payload['parameters']=point
        payload.pop('calculation_conditions',None)
        # 引用的组/方法寻址协议仍为 v1，保持既有数据库约束；v2 目录单独声明原文归点。
        payload['tc_context_ref']={'version':1,'group_key':group_key,'method_key':method_key,'method_raw_owner':'point',
            **({'empty_parameter_extensions':True} if extensions==[] else {}),
            **({'empty_condition_extensions':True} if empty_conditions else {})}
        if 'method_name' in identity:
            # 共同描述只存一次；投影标记保留调用方原本是否显式携带该描述。
            payload['tc_context_ref']['method_name_present']=True
            method['method_name']=identity.pop('method_name')
        if shared_associations:
            own_associations=[];layout=[]
            for item in payload.get('source_associations') or []:
                if item in shared_associations:layout.append({'shared':shared_associations.index(item)})
                else:
                    layout.append({'point':len(own_associations)});own_associations.append(item)
            payload['source_associations']=own_associations
            payload['tc_context_ref']['association_layout']=layout
        record['payload']=payload;record['method_code']=None
    if groups:module.setdefault('metadata',{})[KEY]={'version':VERSION,'groups':groups,'methods':methods}
    return module

def map_draft(draft,compact=False):
    draft=deepcopy(draft)
    for state in draft.get('material_states') or []:
        state.pop('structure_optimization_details', None)
        if state.get('structure_optimization') == 'anharmonic_quantum':
            state['structure_optimization'] = 'unknown'
        if isinstance(state.get('field_evidence'), dict):
            state['field_evidence'] = {k:v for k,v in state['field_evidence'].items() if not k.startswith('structure_optimization_details')}
        state['property_modules']=[(compact_module if compact else expand_module)(module)
            for module in state.get('property_modules') or []]
    return draft

def expanded_record(record):
    from backend.services.scientific_draft_rewrite import _record_snapshot
    data=_record_snapshot(record,module_code='')
    if not (record.payload_json or {}).get('tc_context_ref'):return data
    return expand_module({'metadata':record.module.metadata_json or {},'records':[data]})['records'][0]
