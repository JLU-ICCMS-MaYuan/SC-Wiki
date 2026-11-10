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


def read_chart(model, prompt, request, images, ir, path, source, crop, *, cancelled, on_event):
    """图意由原模型识读；程序问题回到具体元素，可执行工具改变下一轮图片。"""
    import base64
    import io
    from PIL import Image
    from .chart_reading import reading_schema, calibrate_panel
    from .chart_calibration import ChartReadingError
    from .image_reading import ImageReadingTools, ACTIONS
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
    answer = None
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
            'pdf_page':b.pdf_page,'bbox':b.bbox,'text':b.text[:200]} for b in ir.blocks if b.bbox]
        payload['available_actions'] = [d['function']['name'] for d in available]
        options = {'images': images, 'tool_definitions': available}
        if history: options['tool_history'] = history
        result = model(prompt + '\nUse the registered tools to inspect or repair a concrete issue. '
            'Keep the SAME task model. Report all target observations with report_chart_reading. '
            'All normalized coordinates refer to the CURRENT crop. Read true labels; do not force agreement '
            'with a shared body maximum. No unsupported zero values or extra scientific fields.',
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
            new = receipt['locator']
            if name == 'adjust_image_region':
                current_crop = list(new['bbox_page'])
                payload.update(region_id=new['region_id'], crop_bbox=current_crop,
                    crop_image_size=[receipt['images'][0]['width'],receipt['images'][0]['height']],
                    crop_sha256=receipt['images'][0]['image_sha256'])
                images = [images[0], actual_images[0]]
                locator = new
            if name != 'adjust_image_region':
                images = images[:2] + [url for url in actual_images if url not in images[:2]]
                payload['additional_image_regions'] = [receipt['locator']]
            payload['observation'] = receipt
            on_event({'stage':'feedback','status':'completed','iteration':iteration,
                'action':name,'arguments':action.get('arguments'), 'receipt':receipt,'progress':progress.state()})
            if native:
                history = [{'role':'assistant','content':None,'tool_calls':[native]},
                    {'role':'tool','tool_call_id':native['id'],'content':json.dumps(receipt,ensure_ascii=False)}]
            continue
        answer = action.get('arguments') if name == 'report_chart_reading' else result
        validate_output(answer, reading_schema())
        rendered = render_region_image(path, locator)
        issues = []
        invalid = []
        for index, panel in enumerate(answer['panels']):
            try:
                _, missing = calibrate_panel(panel, Image.open(io.BytesIO(rendered['png'])),
                    {**source,'page':request['pdf_page']},current_crop)
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
        if not issues: return answer, current_crop, progress.state()
        fresh = progress.observe('program_verification', request['selected_regions'][0]['region_id'], issue_signature(issues))
        on_event({'stage':'feedback','status':'verification','iteration':iteration,
            'issues':issues,'progress':progress.state()})
        if not fresh:
            if invalid:
                answer = deepcopy(answer)
                answer['panels'] = [panel for i,panel in enumerate(answer['panels']) if i not in invalid]
                answer['notes'].extend({'scope':'target','reason':issue['category']+': '+issue['reason']}
                    for issue in issues if issue.get('reason_code')=='INVALID_PANEL_OBSERVATION')
            return answer, current_crop, progress.state()
        payload['verification_issues'] = issues
        payload['required_next_step'] = '定位到上述元素，选择实际重裁/读刻度/复算动作；来源确实不足则保留明确未读。'
        if native:
            history = [{'role':'assistant','content':None,'tool_calls':[native]},
                {'role':'tool','tool_call_id':native['id'],'content':json.dumps({'issues':issues},ensure_ascii=False)}]
    raise ValueError('图像工具动作预算已用尽，未将技术未完成当作没有科学数据')


def read_spectrum(model,prompt,payload,figure,states,images):
    """谱专用像素坐标保持原目标图；局部重裁作为附加证据，不改积分输入。"""
    import base64
    import io
    from PIL import Image
    from pydantic import BaseModel,ConfigDict
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
        'strict':True,'parameters':_strict(Reading.model_json_schema())}})
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
        parsed=Reading.model_validate(answer)
        failures=[]
        for panel in parsed.panels:
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
