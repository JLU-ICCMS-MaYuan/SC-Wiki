"""#234：同一主模型的可定位反馈；请求故障继续交现有运行器。"""
from __future__ import annotations

from copy import deepcopy
import json

from .document_ir import content_hash

VERSION = 'image-feedback-v2'


def issue_signature(issues):
    """模型措辞不作为新证据；真实程序位置/错误变化仍参与进展判断。"""
    import re
    def identity(value):
        return re.sub(r'\s+','',str(value)).translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉','0123456789'))
    return sorted([{'category':identity(row.get('category','')), 'series':identity(row.get('series','')),
        'scope':row.get('scope','element'),
        'point':{key:row['point'].get(key) for key in ('x','y','mu_star')} if row.get('point') else None,
        'reason':row['reason'] if row.get('point') or row.get('reason_code') else 'source_unresolved'} for row in issues],key=str)


class FeedbackProgress:
    def __init__(self, state=None):
        self.history = deepcopy((state or {}).get('history', []))

    def observe(self, action, arguments, evidence):
        identity = content_hash(action, arguments)
        observation = content_hash(evidence)
        repeated = any(h['action_identity'] == identity and h['evidence_identity'] == observation for h in self.history)
        self.history.append({'action_identity': identity, 'evidence_identity': observation,
            'action': action, 'arguments': deepcopy(arguments),
            'progress': 'no_new_evidence' if repeated else 'new_evidence'})
        return not repeated

    def state(self):
        return {'history': deepcopy(self.history)}


def _chart_panel_key(panel):
    return (panel['figure'], panel['panel'], panel['quantity'])


def _merge_chart_repair(previous, incoming, verified):
    """同一原图中只替换失败柱观察；已验证柱坐标与归属复用，不当成新提取。"""
    if previous is None:
        return deepcopy(incoming), []
    result = deepcopy(previous)
    result['notes'] = deepcopy(incoming['notes'])
    by_key = {_chart_panel_key(panel): index for index, panel in enumerate(result['panels'])}
    reused = [list(key) for key in sorted(verified)]
    for panel in incoming['panels']:
        key = _chart_panel_key(panel)
        if key not in by_key:
            # 新发现的物理量可以加入；同量改面板名不能伪装成另一份独立结果。
            if any(p['figure'] == panel['figure'] and p['quantity'] == panel['quantity'] for p in result['panels']):
                raise ValueError('局部图读修订须保留原面板身份，未猜测合并不同面板')
            by_key[key] = len(result['panels'])
            result['panels'].append(deepcopy(panel))
            continue
        index = by_key[key]
        old = result['panels'][index]
        if old['kind'] != 'bar' or panel['kind'] != 'bar':
            result['panels'][index] = deepcopy(panel)
            continue
        old_points = {(p['category'], p['series']): p for p in old['points']}
        incoming_ids = [(p['category'], p['series']) for p in panel['points']]
        if len(set(incoming_ids)) != len(incoming_ids):
            raise ValueError('图读局部修订包含重复柱身份')
        for point in panel['points']:
            point_key = (point['category'], point['series'])
            if (*key, *point_key) not in verified:
                old_points[point_key] = deepcopy(point)
        for item in panel['unresolved']:
            point_key=(item['category'],item['series'])
            if (*key,*point_key)not in verified:
                old_points.pop(point_key,None)  # 明确未读接替原失败观察，不能反复保留旧的错误坐标。
        revised = deepcopy(panel)
        revised['categories'] = list(dict.fromkeys(old['categories'] + panel['categories']))
        revised['series'] = list(dict.fromkeys(old['series'] + panel['series']))
        revised['points'] = list(old_points.values())
        # 没有修订的旧失败点仍留在观察中；真正补齐的点改走本轮正常校验。
        missing = {(u['category'], u['series']): deepcopy(u) for u in old['unresolved'] + panel['unresolved']}
        revised['unresolved'] = [u for pair, u in missing.items() if pair not in old_points]
        result['panels'][index] = revised
    return result, reused


def _chart_repair_coverage(answer, required):
    issues=[]
    for entry in required:
        panels=[p for p in answer['panels'] if p['figure']==entry['figure'] and p['panel']==entry['panel']
                and (entry['quantity'] is None or p['quantity']==entry['quantity'])]
        present={(v['category'],v['series'])for p in panels for v in p['points']+p['unresolved']}
        missing=[pair for pair in entry['points'] if (pair['category'],pair['series'])not in present]
        if not panels or missing:
            issues.append({'scope':'panel','category':entry['figure']+' '+entry['panel'],
                'series':entry['quantity'] or 'legacy_quantity_unresolved', 'reason_code':'MISSING_REPAIR_CANDIDATES',
                'reason':'局部图读遗漏原待读面板或候选身份；请按原图补读或逐项保留真实未读原因，不能因精读其他面板而删除。',
                'missing_points':missing})
    return issues


def read_chart(model, prompt, request, images, ir, path, source, crop, *, cancelled, on_event):
    """图意由原模型识读；程序问题回到具体元素，可执行工具改变下一轮图片。"""
    import base64
    import io
    from PIL import Image
    from .chart_reading import reading_schema, calibrate_panel
    from .chart_calibration import ChartReadingError
    from .image_reading import ImageReadingTools, ACTIONS
    from .image_catalog import visual_objects
    from .image_geometry import geometry_observations
    from .review_tool_contract import tool_definitions
    from .pdf_regions import region_locator, render_region_image
    from backend.rag.structured_output import validate_output

    # 修复过程只修改本地观察；失败后重新编排须得到与原请求相同的IR输入。
    local = ImageReadingTools({source['file_id']: ir.model_copy(deep=True)}, {source['file_id']: path}, cancelled=cancelled)
    full = request['complete_figure']
    locator = region_locator(path, source['file_id'], source['sha256'], request['pdf_page'], crop,
        parent_region_id=full['region_id'])
    local.regions[full['region_id']] = deepcopy(full)
    local.regions[locator['region_id']] = deepcopy(locator)
    # 完整图没有IR图块的旧来源仍保留原位图；调整/识别/复算动作使用已登记区域。
    definitions = [t for t in tool_definitions(local.documents, [{'file_id':source['file_id'],'kind':'pdf'}])
                   if t['function']['name'] in ACTIONS]
    definitions.append({'type':'function','function':{'name':'report_chart_reading',
        'description':'提交目标图全部面板的原图观察；服务器标定和验证，不作批准。',
        'strict':True,'parameters':reading_schema()}})
    progress = FeedbackProgress()
    history = []
    exhausted = set()
    payload = {**request, 'region_id': locator['region_id'], 'image_receipt_version': 'image-reading-v1', 'feedback_version':VERSION,
        'available_actions': [t['function']['name'] for t in definitions]}
    current_crop = list(crop)
    current_rendered = render_region_image(path, locator)
    payload['current_crop_geometry'] = geometry_observations(Image.open(io.BytesIO(current_rendered['png'])))
    payload['current_crop_geometry']['region_id'] = locator['region_id']
    answer = None
    previous_answer, verified, reuse_events, calibration_cache = None, set(), [], {}
    objects = visual_objects(ir)
    for iteration in range(13):  # 复用文档工具已有动作预算，不另设无限循环。
        if cancelled(): raise InterruptedError('图像反馈已取消')
        available = deepcopy([d for d in definitions if d['function']['name'] not in exhausted
            and (iteration < 12 or d['function']['name']=='report_chart_reading')])
        for definition in available:
            properties = definition['function']['parameters']['properties']
            if 'region_id' in properties:
                properties['region_id'] = {'type':'string','enum':list(local.regions)}
        payload['available_regions'] = list(local.regions.values())
        payload['available_objects'] = [{'block_id':b.block_id,'kind':str(b.block_type),
            'pdf_page':b.pdf_page,'bbox':b.bbox,'text':b.text[:200]} for b in objects]
        payload['available_actions'] = [d['function']['name'] for d in available]
        if previous_answer:
            payload['repair_inventory'] = [{'figure':p['figure'], 'panel':p['panel'], 'quantity':p['quantity'],
                'verified_points':[{'category':a, 'series':b} for f,n,q,a,b in sorted(verified)
                                   if (f,n,q)==_chart_panel_key(p)]} for p in previous_answer['panels']]
        options = {'images': images, 'tool_definitions': available}
        if history: options['tool_history'] = history
        result = model(prompt + '\nUse the registered tools to inspect or repair a concrete issue. '
            'Keep the SAME task model. Report all target observations with report_chart_reading. '
            'All normalized coordinates refer to the CURRENT crop. Read true labels; do not force agreement '
            'with a shared body maximum. current_crop_geometry contains measured coordinates for IMAGE 2; '
            'rectangles may include legends, so identify material/series and read actual tick labels yourself. '
            'Use measured center_x and rectangle endpoints after identifying the actual bar; band_index and '
            'frame contact describe geometry only. Map materials by their printed x-axis labels, not list order. '
            'Image 2 and crop_bbox are the FIXED target coordinate frame. Detail images are supplementary; '
            'use additional_image_regions.coordinate_transform to map any detail coordinates back to image 2. '
            'Geometry in tool receipts belongs to its region_id, never copy detail coordinates into target coordinates. '
            'For bar-chart feedback, report ONLY corrected points or axis observations in the SAME figure/panel/quantity. '
            'The host retains verified points and their conditions; do not repeat or rewrite them. '
            'retained_tool_observations also preserve your earlier digitization of THIS target; '
            'repair_inventory identifies its verified points. Reuse them and report only pending changes, '
            'while still accounting for every other panel visible in the target. '
            'If an axis changes, the program recalculates its genuine dependents from retained image observations. '
            'retained_panels are already verified source panels OUTSIDE this repair scope: do not re-read them. '
            'required_repair_panels lists the original pending identities: preserve their exact figure/panel names '
            'and account for every category/series in points or unresolved. A detail crop never removes another target. '
            'No unsupported zero values or extra scientific fields.',
            json.dumps(payload, ensure_ascii=False), **options)
        action = result.get('action') or {}
        native = result.get('_tool_call')
        name = action.get('name')
        if name in ACTIONS:
            semantic_arguments = {k:v for k,v in (action.get('arguments') or {}).items() if k!='reason'}
            try:
                receipt, actual_images = local.call(name, action.get('arguments') or {})
            except ValueError as error:
                payload['previous_error'] = {'tool': name, 'reason': str(error),
                    'available_regions': list(local.regions)}
                if not progress.observe(name,semantic_arguments,{'error':str(error)}):
                    exhausted.add(name)
                if native:
                    history = [{'role':'assistant','content':None,'tool_calls':[native]},
                        {'role':'tool','tool_call_id':native['id'], 'content':json.dumps(payload['previous_error'],ensure_ascii=False)}]
                continue
            evidence = {'images':[row['image_sha256'] for row in receipt['images']],
                'observations':receipt['text_observations'], 'readings':receipt.get('readings'),
                'unresolved':receipt.get('unresolved'), 'context':receipt.get('context')}
            if not progress.observe(name, semantic_arguments, evidence):
                receipt = {**receipt, 'previous_error':'相同动作没有新依据，请选择另一项具体动作或说明来源缺失。'}
                exhausted.add(name)
            panel = (action.get('arguments') or {}).get('panel')
            protected = {_chart_panel_key(p) for p in payload.get('retained_panels', [])}
            if (name in {'digitize_image_elements', 'verify_image_reading'}
                    and receipt['locator']['region_id'] == locator['region_id']
                    and panel.get('kind') == 'bar' and receipt.get('readings')
                    and _chart_panel_key(panel) not in protected):
                # 同一模型已在当前原图取到且通过实际像素校验的观察，也属于有效步骤。
                # 精读图的不同坐标系不在这里合并；最终仍由模型提交完成报告及原有校验收口。
                previous_answer, _ = _merge_chart_repair(previous_answer,
                    {'panels': [panel], 'notes': []}, verified)
                verified.update((*_chart_panel_key(panel), row['point']['category'], row['point']['series'])
                                for row in receipt['readings'])
                calibration_cache[content_hash(panel, locator['region_id'])] = (
                    deepcopy(receipt['readings']), deepcopy(receipt['unresolved']))
                payload['retained_tool_observations'] = deepcopy(previous_answer['panels'])
                on_event({'stage': 'feedback', 'status': 'retained-tool-observation',
                    'iteration': iteration, 'region_id': locator['region_id'],
                    'receipt_id': receipt['receipt_id'],
                    'verified_observation_ids': [list(key) for key in sorted(verified)]})
            new = receipt['locator']
            if name == 'adjust_image_region':
                width,height = current_crop[2]-current_crop[0],current_crop[3]-current_crop[1]
                new = {**new, 'coordinate_transform': {
                    'kind':'detail_normalized_to_target_normalized', 'to_region_id':locator['region_id'],
                    'offset':[1000*(new['bbox_page'][0]-current_crop[0])/width,
                              1000*(new['bbox_page'][1]-current_crop[1])/height],
                    'scale':[(new['bbox_page'][2]-new['bbox_page'][0])/width,
                             (new['bbox_page'][3]-new['bbox_page'][1])/height]}}
            # 精读图只补充证据；原目标、原图2及所有待读面板的坐标系保持。
            images = images[:2] + [url for url in actual_images if url not in images[:2]]
            payload['additional_image_regions'] = [new]
            payload['observation'] = receipt
            on_event({'stage':'feedback','status':'completed','iteration':iteration,
                'action':name,'arguments':action.get('arguments'), 'receipt':receipt,'progress':progress.state()})
            if native:
                history = [{'role':'assistant','content':None,'tool_calls':[native]},
                    {'role':'tool','tool_call_id':native['id'],'content':json.dumps(receipt,ensure_ascii=False)}]
            continue
        answer = action.get('arguments') if name == 'report_chart_reading' else result
        validate_output(answer, reading_schema())
        protected = {_chart_panel_key(p) for p in payload.get('retained_panels',[])}
        repeated = [p for p in answer['panels'] if _chart_panel_key(p) in protected]
        if repeated:
            answer = deepcopy(answer)
            answer['panels'] = [p for p in answer['panels'] if _chart_panel_key(p) not in protected]
            rejected = [{k:p[k]for k in ('figure','panel','quantity')}for p in repeated]
            answer['notes'].append({'scope':'context','reason':'模型重复回答已核实的只读面板；新回答未采用，原来源保持：'+json.dumps(rejected,ensure_ascii=False)})
            on_event({'stage':'feedback','status':'scope-rejected','iteration':iteration,
                'rejected_panels':rejected,'reason':'当前修复范围之外的有效原记录只复用，不接受覆盖'})
        answer, reused = _merge_chart_repair(previous_answer, answer, verified)
        if reused:
            reuse_events.append({'iteration':iteration, 'region_id':locator['region_id'], 'reused_observation_ids':reused})
            on_event({'stage':'feedback','status':'reuse','iteration':iteration,
                'region_id':locator['region_id'],'reused_observation_ids':reused})
        rendered = render_region_image(path, locator)
        issues = []
        invalid = []
        for index, panel in enumerate(answer['panels']):
            try:
                check_key = content_hash(panel, locator['region_id'])
                if check_key not in calibration_cache:
                    calibration_cache[check_key] = calibrate_panel(panel, Image.open(io.BytesIO(rendered['png'])),
                        {**source,'page':request['pdf_page']},current_crop)
                found, missing = deepcopy(calibration_cache[check_key])
                if panel['kind'] == 'bar':
                    verified = {key for key in verified if key[:3] != _chart_panel_key(panel)}
                    verified.update((*_chart_panel_key(panel), r['point']['category'], r['point']['series']) for r in found)
            except ChartReadingError as error:
                invalid.append(index)
                missing = [{'scope':'panel','category':panel['figure']+' '+panel['panel'],
                    'series':panel['quantity'],'reason':str(error),'reason_code':'INVALID_PANEL_OBSERVATION',
                    'invalid_coordinates':[{'category':p['category'],'series':p['series'],'x':p['x'],'y':p['y']}
                        for p in panel['points'] if not (0<=p['x']<=1000 and 0<=p['y']<=1000)],
                    'coordinate_space':'crop_normalized_0_1000','crop_image_size':payload['crop_image_size'],
                    'correction':'Re-read image 2. If using actual image pixels, x_norm=1000*x_px/width and y_norm=1000*y_px/height; do not copy page pt or guess a scale.'}]
            # 程序定位失败才发出具体修复；模型明确申报的真实缺失仍保留原语义。
            issues.extend(missing)
        issues.extend({'reason':note['reason'],'scope':'target'} for note in answer['notes'] if note['scope']=='target')
        coverage_issues = _chart_repair_coverage(answer,payload.get('required_repair_panels',[]))
        issues.extend(coverage_issues)
        previous_answer = deepcopy(answer)
        if not issues: return answer, current_crop, {**progress.state(), 'reuse':reuse_events}
        declared_unread = {(u['category'],u['series'],u['reason'])
                           for p in answer['panels'] for u in p['unresolved']}
        def source_unread(issue):
            return (issue.get('reason_code') in {'BAR_HEIGHT_BELOW_IMAGE_RESOLUTION','BAR_INTERIOR_UNREADABLE'}
                    or (not issue.get('point') and not issue.get('reason_code')
                        and (issue.get('category'),issue.get('series'),issue['reason']) in declared_unread))
        inspected = any(row['action'] in ACTIONS for row in progress.history)
        # 实际取图后，诚实未读是应保留的来源限制；坐标、轴或范围错误仍须修复。
        # 不因无法读出的柱或其说明反复要求模型改写，更不能将其写成0。
        if (inspected and any(source_unread(issue) for issue in issues)
                and all(source_unread(issue) or (issue.get('scope') == 'target'
                        and not issue.get('reason_code')) for issue in issues)):
            return answer, current_crop, {**progress.state(), 'reuse':reuse_events, 'source_unresolved':True}
        fresh = progress.observe('program_verification', request['selected_regions'][0]['region_id'], issue_signature(issues))
        on_event({'stage':'feedback','status':'verification','iteration':iteration,
            'issues':issues,'progress':progress.state()})
        if not fresh:
            if coverage_issues:
                raise ValueError('图读局部修订未保留原面板或候选，失败回执已保留，未以局部数据替换完整范围')
            if invalid:
                answer = deepcopy(answer)
                answer['panels'] = [panel for i,panel in enumerate(answer['panels']) if i not in invalid]
                answer['notes'].extend({'scope':'target','reason':issue['category']+': '+issue['reason']}
                    for issue in issues if issue.get('reason_code')=='INVALID_PANEL_OBSERVATION')
            return answer, current_crop, {**progress.state(), 'reuse':reuse_events}
        payload['verification_issues'] = issues
        from .image_geometry import geometry_observations
        payload['current_crop_geometry'] = geometry_observations(Image.open(io.BytesIO(rendered['png'])))
        payload['current_crop_geometry']['region_id'] = locator['region_id']
        payload['required_next_step'] = '定位到上述元素，选择实际重裁/读刻度/复算动作；来源确实不足则保留明确未读。'
        suggestions=[]
        for issue in issues:
            box=issue.get('suggested_crop_bbox_normalized')
            if box:
                physical=[current_crop[0]+box[0]*(current_crop[2]-current_crop[0])/1000,
                    current_crop[1]+box[1]*(current_crop[3]-current_crop[1])/1000,
                    current_crop[0]+box[2]*(current_crop[2]-current_crop[0])/1000,
                    current_crop[1]+box[3]*(current_crop[3]-current_crop[1])/1000]
                action={'name':'adjust_image_region','arguments':{'region_id':locator['region_id'],
                    'bbox_page':physical,'dpi':600,'reason':'核对轴外印刷数字及其真实刻度位置，避免将无字短刻度当作数字标签'}}
                if action not in suggestions:suggestions.append(action)
        if suggestions:
            payload['suggested_detail_actions']=suggestions
            payload['required_next_step']='优先实际查看建议的轴外文字精读图，自己识别原数字及对应刻度；不要只删除有问题的刻度，也不要用正文目标值反推。'
        if native:
            history = [{'role':'assistant','content':None,'tool_calls':[native]},
                {'role':'tool','tool_call_id':native['id'],'content':json.dumps({'issues':issues},ensure_ascii=False)}]
    raise ValueError('图像工具动作预算已用尽，未将技术未完成当作没有科学数据')


def _spectrum_wire_schema(node):
    """同类型定长元组可无损用 items 表示；不放宽不同位置的类型。"""
    if isinstance(node, list):
        return [_spectrum_wire_schema(value) for value in node]
    if not isinstance(node, dict):
        return node
    result = {key: _spectrum_wire_schema(value) for key, value in node.items()}
    if 'prefixItems' in result:
        slots = result.pop('prefixItems')
        if (not slots or 'items' in result or result.get('type') != 'array'
                or result.get('minItems') != len(slots) or result.get('maxItems') != len(slots)
                or any(slot != slots[0] for slot in slots[1:])):
            raise ValueError('谱工具含不能无损转换的定长数组声明')
        result['items'] = slots[0]
    return result


def read_spectrum(model,prompt,payload,figure,states,images):
    """谱专用像素坐标保持原目标图；局部重裁作为附加证据，不改积分输入。"""
    import base64
    import io
    from PIL import Image
    from pydantic import BaseModel,ConfigDict,ValidationError
    from backend.spectra.contracts import PanelCalibration
    from backend.spectra.engine import extract_panel
    from backend.spectra.context import references_for
    from .scientific_output_schema import _strict
    from .document_ir import DocumentIR
    from .image_reading import ImageReadingTools,ACTIONS
    from .review_tool_contract import tool_definitions
    import numpy as np
    class Reading(BaseModel):
        model_config=ConfigDict(extra='forbid')
        panels:list[PanelCalibration]
        issues:list[str]
    ir=DocumentIR.model_validate(figure['document_ir'])
    tools=ImageReadingTools({ir.source_file_id:ir},{ir.source_file_id:figure['_pdf_path']})
    tools.regions[figure['region_locator']['region_id']]=figure['region_locator']
    # 这些动作共同取源；谱计算在下方专用engine中完成，不暴露标量panel协议。
    names={'read_complete_object','read_image_context','adjust_image_region','recognize_image_text'}
    definitions=[t for t in tool_definitions(tools.documents,[{'file_id':ir.source_file_id,'kind':'pdf'}]) if t['function']['name'] in names]
    definitions.append({'type':'function','function':{'name':'report_spectrum_calibration',
        'description':'提交谱专用标定；像素坐标始终属于原目标图，不属于附加放大图。',
        'strict':True,'parameters':_spectrum_wire_schema(_strict(Reading.model_json_schema()))}})
    request={**payload,'region_id':figure['region_locator']['region_id'],
        'target_bbox_pdf_pt':figure['bbox_pdf_pt'],'feedback_version':VERSION}
    progress=FeedbackProgress();history=[];target_images=list(images);exhausted=set()
    for iteration in range(13):
        available=deepcopy([d for d in definitions if d['function']['name'] not in exhausted
            and (iteration<12 or d['function']['name']=='report_spectrum_calibration')])
        for definition in available:
            properties=definition['function']['parameters']['properties']
            if 'region_id' in properties:properties['region_id']={'type':'string','enum':list(tools.regions)}
        request['available_regions']=list(tools.regions.values())
        result=model(prompt+'\nUse report_spectrum_calibration; extra crops are evidence only. '
            'Report pixel coordinates in the ORIGINAL target image (attachment 2 when context is present), never in an extra crop.',
            json.dumps(request,ensure_ascii=False),images=images,tool_definitions=available,
            **({'tool_history':history} if history else {}),read_timeout=180)
        action=result.get('action') or {};native=result.get('_tool_call');name=action.get('name')
        if name in names:
            arguments={k:v for k,v in (action.get('arguments') or {}).items() if k!='reason'}
            try:
                receipt,extra=tools.call(name,action.get('arguments') or {})
                request['observation']=receipt
                images=target_images+[url for url in extra if url not in target_images]
                evidence={'images':[r['image_sha256'] for r in receipt['images']],
                    'observations':receipt['text_observations'],'context':receipt.get('context')}
                if not progress.observe(name,arguments,evidence):
                    exhausted.add(name)
                    request['observation']={**receipt,'previous_error':'相同动作没有新证据，请换方法或报告真实未读。'}
            except ValueError as error:
                request['observation']={'error':str(error),'available_regions':list(tools.regions)}
                if not progress.observe(name,arguments,{'error':str(error)}):exhausted.add(name)
            if native:history=[{'role':'assistant','content':None,'tool_calls':[native]},
                {'role':'tool','tool_call_id':native['id'],'content':json.dumps(request['observation'],ensure_ascii=False)}]
            continue
        answer=action.get('arguments') if name=='report_spectrum_calibration' else result
        if not isinstance(answer, dict) or not isinstance(answer.get('panels'), list):
            raise ValueError('读图模型未返回谱面板列表')
        failures=[]
        for index, raw in enumerate(answer['panels']):
            try:
                panel=PanelCalibration.model_validate(raw)
            except ValidationError as error:
                failures.extend({'panel_index':index, 'field':'.'.join(map(str, item['loc'])),
                    'reason':item['msg']} for item in error.errors(
                        include_input=False, include_context=False, include_url=False))
                continue
            state=next((s for s in states if s.get('state_key')==panel.state_key),None)
            check=extract_panel(np.asarray(Image.open(io.BytesIO(figure['image'])).convert('RGB')),
                panel.model_dump(),references=references_for(state))
            failures.extend(check.get('failures',[]))
        if not failures:return answer
        if not progress.observe('spectrum_verification',figure['region_locator']['region_id'],failures):return answer
        request['verification_issues']=failures
        if native:history=[{'role':'assistant','content':None,'tool_calls':[native]},
            {'role':'tool','tool_call_id':native['id'],'content':json.dumps({'failures':failures},ensure_ascii=False)}]
    raise ValueError('谱图工具预算已耗尽，原标定与成功结果保留')
