"""只读统计一次preflight的逐核对项调用；禁止模型请求，不写业务数据。"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from backend.api import evidence as api
from backend.database import SessionLocal
from backend.ingest import (property_evidence as ev, scientific_evidence as science,
    condition_rules as rules, condition_lifecycle as lifecycle, association_review as associations,
    evidence_proposals as proposals, manual_evidence as manual, pdf_source_pages as pdf,
    pdf_front_matter as front)
from backend.rag import llm

LABELS = {'name_raw':'名称','value_raw':'原始值','unit_raw':'单位','value_number':'数值',
          'value_min':'下界','value_max':'上界','value_text':'文本值','value_boolean':'布尔值',
          'canonical_unit':'规范单位','uncertainty':'不确定度','method_code':'方法编码',
          'method_raw':'方法原文','criterion_code':'判据编码','criterion_raw':'判据原文',
          'payload':'物性扩展内容','value_kind':'值类型'}


def compact(value):
    if isinstance(value, dict):
        if 'value_raw' in value:
            return str(value.get('value_raw') or '空白') + (' ' + str(value['unit_raw']) if value.get('unit_raw') else '')
        return '对象：' + '、'.join(list(value)[:6])
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else str(value) if value is not None else '空白'
    return text[:160] + ('…' if len(text) > 160 else '')


def category(row):
    path = row['field']
    if path.startswith('paper.'):
        return '论文信息'
    if row.get('condition_context') or 'calculation_conditions' in path:
        return '计算条件'
    if row.get('kind') == 'structure':
        return '结构资料'
    if row.get('record_key'):
        return {'superconductive_properties':'超导性质','electronic_properties':'电子性质',
                'dynamical_properties':'动力学性质','thermodynamic_properties':'热力学性质'}.get(row.get('module_code'), '其他物性')
    return '材料状态基础信息'


def method_ids(row):
    methods = ['格式/类型', '当前版本', '人工决定']
    if row.get('kind') == 'derived' or (row.get('provenance') or {}).get('kind') == 'derived':
        methods.append('确定性推导')
    else:
        methods += ['原文定位', '模型科学判断']
    if row.get('condition_context'):
        methods += ['条件规则', '历史恢复']
    if row.get('source_associations'):
        methods.append('共用范围关联')
    if str(row.get('record_field') or '').startswith('value_'):
        methods.append('结果流程归属（按需）')
    return methods


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--owner', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    totals, by_item, successes = Counter(), defaultdict(Counter), defaultdict(Counter)
    current = ContextVar('audit_item', default=None)
    bindings = [
        (ev,'upload_snapshot','snapshot'), (science,'load_results','history_load'),
        (science,'ordered_check_rows','history_query'), (ev,'public_snapshot','public_snapshot'),
        (ev,'checked_result','status_check'), (rules,'current_review','rule_entry'),
        (rules,'validate_assessment','rule_assessment'), (lifecycle,'recover','history_recovery'),
        (associations,'effective_associations','association_entry'), (associations,'checked_review','association_validation'),
        (ev,'locate_with_reason','quote_location'), (proposals,'validate_values','value_schema'),
        (science,'human_confirmed','human_binding'), (lifecycle,'result_scope_issue','result_scope_entry'),
        (front,'verified_title_source','pdf_title'), (front,'verified_author_source','pdf_authors'),
        (pdf,'current_pdf_results','pdf_pass'), (manual,'changed_records','manual_diff_pass'),
        (manual,'complete_keys','manual_completion_pass'), (science,'apply_derived','derived_pass'),
    ]
    def wrap(function, name):
        @wraps(function)
        def call(*a, **kw):
            candidate = a[0] if a and isinstance(a[0], dict) else kw.get('record')
            if name in {'pdf_title','pdf_authors'} and len(a)>1:
                candidate = next((r for r in a[1]['records'] if r['field'] == ('paper.title' if name=='pdf_title' else 'paper.authors')), None)
            item = candidate.get('item_key') if candidate else None
            token = current.set(item) if item else None
            key = current.get()
            totals[name] += 1
            if key: by_item[key][name] += 1
            try:
                result = function(*a, **kw)
                if key and name in {'rule_assessment','history_recovery'} and result:
                    successes[key][name] += 1
                return result
            finally:
                if token is not None: current.reset(token)
        return call
    def no_llm(*a, **kw):
        totals['llm_requests'] += 1
        raise AssertionError('只读审计不允许调用模型')

    user = SimpleNamespace(id=args.owner, role='user')
    target = api.Target(target='upload', target_id=args.task)
    # 未插桩的一次完整处理耗时，另一次只计数；二者不混为同一次计时。
    with patch.object(llm, 'complete_json', no_llm):
        start = time.perf_counter()
        plain = api.preflight(target, user)
        elapsed = time.perf_counter() - start
    plain_bytes = len(json.dumps(plain, ensure_ascii=False, default=str).encode())
    totals.clear()
    with ExitStack() as stack:
        for module, attribute, name in bindings:
            stack.enter_context(patch.object(module, attribute, wrap(getattr(module, attribute), name)))
        stack.enter_context(patch.object(llm, 'complete_json', no_llm))
        traced = api.preflight(target, user)
    totals.setdefault('llm_requests', 0)
    assert traced['version'] == plain['version'], '审计期间内容版本变化，不能合并两次结果'
    snapshot = ev.upload_snapshot(args.task, args.owner)
    assert snapshot['version'] == traced['version']
    with SessionLocal() as db:
        history = science.ordered_check_rows(db, 'upload', args.task)
        histories = Counter(row.item_key for row in history)
        history_size = sum(len(json.dumps(row.result, ensure_ascii=False, default=str).encode()) for row in history)
    units = []
    public = {r['item_key']:r for r in traced['records']}
    for r in snapshot['records']:
        key = r['item_key']
        fields = proposals.editable_fields(r)
        form_fields = []
        for f in fields:
            path = r['field'] + ('.' + f['path'] if f['path'] else '')
            schema = f['schema']
            form_fields.append({'path':path,'name':LABELS.get(f['path'],f['label']),
                'value':compact(f['value']),'type':schema.get('type'),'nullable':schema.get('nullable',False)})
        units.append({'id':key, 'field':r['field'], 'label':r['label'],
            'group':category(r),'owner':r.get('owner_label') or r.get('state_key') or '论文',
            'kind':r.get('kind'),'required':r.get('required',True),'value':compact(r.get('current_value')),
            'status':public.get(key,{}).get('status'),'methods':method_ids(r),'fields':form_fields,
            'record_field':r.get('record_field'), 'condition':r.get('condition_context'),
            'dependencies':r.get('record_dependencies') or [],'state_dependencies':r.get('state_dependencies') or [],
            'history_rows':histories[key],'counts':dict(by_item[key]),'successes':dict(successes[key]),
            'review_granularity':'整条物性共享一个核对结果' if r.get('kind')=='property' else '子项或独立字段',
            'llm_requests_measured':0})
    assigned = sum((Counter(v) for v in by_item.values()),Counter())
    result = {'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'snapshot_version':snapshot['version'], 'scope':'一次当前上传草稿preflight，后台函数直接调用；无浏览器/网络时间，无写入，无模型请求',
        'units':units,'total_counts':dict(totals),'unattributed_counts':dict(totals-assigned),
        'timing':{'plain_preflight_seconds':round(elapsed,3),'response_MiB':round(plain_bytes/1048576,2)},
        'history':{'rows':len(history),'json_MiB':round(history_size/1048576,2)},
        'coverage':{'review_units':len(units),'editable_entries':sum(len(r['fields']) for r in units),
                    'groups':dict(Counter(r['group'] for r in units))},
        'limits':['函数入口计数不等于成功审核次数','历史和基线复用同一item_key计入对应项',
                  'quote_location为片段定位调用，可嵌套，不与规则次数相加作为总审核数',
                  '整条物性子键共享审核单元，计数不可按子键重复累加',
                  'PDF循环/确定性推导批处理只统计遍历次数，不伪造每键内部分支次数',
                  '修改后的动态次数依具体修改与历史而变化，本次只读未测；AI首次提取及历史模型调用次数未追溯']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:result[k] for k in ['coverage','timing','history','total_counts']},ensure_ascii=False))
    for u in units:
        if u['field'] in {'paper.title','paper.authors','paper.superconductor_kind','paper.key_finding'} or (u['condition'] and u['condition']['stage']=='sscha' and u['condition']['parameter']=='calculation_code'):
            print(u['label'],u['owner'],u['counts'])


if __name__ == '__main__':
    main()
