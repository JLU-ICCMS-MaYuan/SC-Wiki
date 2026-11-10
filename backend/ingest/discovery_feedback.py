"""将前置图像盘点的实际几何错误交回原模型；已成功页面保持。"""
from copy import deepcopy
import base64
import math

from .image_feedback import FeedbackProgress


def geometry_issues(rows):
    issues=[]
    for row in rows:
        boxes={}
        for index,figure in enumerate(row['figures']):
            key=tuple(figure['bbox'])
            boxes.setdefault(key,[]).append(index)
        for box,indices in boxes.items():
            if len(indices)>1:
                issues.append({'code':'DUPLICATE_PHYSICAL_REGION','pdf_page':row['page'],
                    'figure_indices':indices,'bbox':list(box),
                    'required_fix':'This exact outer rectangle occurs more than once. Return ONE physical '
                        'figure entry including all panel labels, or use distinct actual panel boxes. '
                        'Do not copy this same rectangle into each panel entry.'})
    return issues


def discover_pages(model, prompt, request, images, ir, path, source, geometries, *, cancelled, on_event):
    import json
    from .chart_reading import discovery_schema, page_inventory
    from .chart_calibration import ChartReadingError
    from .pdf_regions import complete_figure, render_region_image
    from backend.rag.structured_output import validate_output
    from backend.rag.llm import call_phase
    from .image_geometry import geometry_observations
    from PIL import Image
    import io

    answer = model(prompt, json.dumps(request, ensure_ascii=False), images=images,
                   response_schema=discovery_schema())
    validate_output(answer, discovery_schema())
    try:
        found, skipped = page_inventory(answer, geometries)
        return answer, found, skipped
    except ChartReadingError as initial_error:
        initial_message = str(initial_error)
    valid, failed = {}, {}
    for page in geometries:
        rows = [row for row in answer['pages'] if row['page'] == page]
        try:
            page_inventory({'pages': rows}, {page: geometries[page]})
            valid[page] = rows[0]
        except ChartReadingError as error:
            failed[page] = (rows, str(error))
    if not failed:
        # 额外/越权页同样必须重新获得合法回执，不能直接忽略错误条目。
        page = next(iter(geometries))
        failed[page] = ([row for row in answer['pages']], initial_message)
        valid.pop(page, None)
    progress = FeedbackProgress()
    calls = 1
    page_images = dict(zip(request['image_pages'], images))
    for page, (rejected, message) in failed.items():
        while calls < 13:  # 与既有图像动作预算一致，传输重试仍由#224单独处理。
            if cancelled():
                raise InterruptedError('图表盘点已取消')
            detail_images, details, panel_hints = [], [], []
            candidates = [figure for row in rejected if row['page'] == page for figure in row['figures']]
            candidates += [hint for hint in request['regions'] if hint['page'] == page]
            for figure in candidates:
                box = figure['bbox']
                if (len(box) != 4 or not all(math.isfinite(v) for v in box)
                        or not 0 <= box[0] < box[2] <= 1000 or not 0 <= box[1] < box[3] <= 1000):
                    continue
                width, height = geometries[page]
                locator = complete_figure(ir, path, {'page': page,
                    'bbox': [box[0]*width/1000, box[1]*height/1000, box[2]*width/1000, box[3]*height/1000],
                    'label': figure.get('label', '')})
                rendered = render_region_image(path, locator)
                observed = geometry_observations(Image.open(io.BytesIO(rendered['png'])))
                for index,band in enumerate(observed['band_candidates']):
                    bounds=locator['bbox_page'];local=band['bbox']
                    page_box=[bounds[0]+local[0]/1000*(bounds[2]-bounds[0]),
                        bounds[1]+local[1]/1000*(bounds[3]-bounds[1]),
                        bounds[0]+local[2]/1000*(bounds[2]-bounds[0]),
                        bounds[1]+local[3]/1000*(bounds[3]-bounds[1])]
                    panel_hints.append({'region_id':'geometry-'+observed['pixel_sha256'][:12]+'-'+str(index),
                        'block_id':None,'page':page,'bbox':[page_box[0]*1000/width,page_box[1]*1000/height,
                            page_box[2]*1000/width,page_box[3]*1000/height],
                        'method':'unlabelled_pixel_frame_candidate','coordinate_space':'page_normalized_0_1000',
                        'role':'geometry_only_identify_actual_panels_from_image'})
                detail_images.append('data:image/png;base64,' + base64.b64encode(rendered['png']).decode())
                details.append({'original_image': 2, 'pdf_page': page, 'locator': locator,
                    'source_sha256': source['sha256'], 'image_sha256': rendered['image_sha256'],
                    'reply_coordinate_space': 'page_normalized_0_1000'})
                break  # 一次只针对当前问题补读，保持其他原页及已完成结果。
            on_event({'stage': 'discovery_feedback', 'status': 'rejected', 'pages': [page],
                'response': {'pages': rejected}, 'error': message, 'additional_images': details,
                'geometry_issues':geometry_issues(rejected),'panel_hints':panel_hints})
            if not progress.observe('repair_discovery_page', {'page': page},
                    {'error': message, 'images': [item['image_sha256'] for item in details]}):
                raise ChartReadingError(message + '；同一盘点错误没有新依据，未采用无效区域')
            repair = {**request, 'image_pages': [page],
                'regions': [hint for hint in request['regions'] if hint['page'] == page]+panel_hints,
                'discovery_feedback': {'error': message, 'rejected_rows': rejected,
                    'geometry_issues':geometry_issues(rejected),
                    'status': 'rejected_model_observation_not_source'}, 'additional_images': details}
            with call_phase('chart_discovery', filename=source['filename'], pages=[page]):
                corrected = model(prompt + '\nThe prior discovery failed the supplied geometry check. '
                    'Re-inventory ONLY image_pages using the actual page and supplied original detail. '
                    'Keep every figure and its reason; use one outer entry with all labels or genuinely distinct '
                    'panel boxes. ALL reply boxes are normalized in the FULL ORIGINAL PAGE, never in the detail crop. '
                    'The rejected observation is not original scientific evidence.',
                    json.dumps(repair, ensure_ascii=False), images=[page_images[page], *detail_images],
                    response_schema=discovery_schema())
            calls += 1
            validate_output(corrected, discovery_schema())
            try:
                page_inventory(corrected, {page: geometries[page]})
            except ChartReadingError as error:
                rejected, message = corrected['pages'], str(error)
                continue
            valid[page] = corrected['pages'][0]
            on_event({'stage': 'discovery_feedback', 'status': 'completed', 'pages': [page],
                'response': corrected, 'progress': progress.state()})
            break
        else:
            raise ChartReadingError(message + '；图表盘点纠错动作预算已耗尽，未将无效区域当作完成')
    combined = {'pages': [deepcopy(valid[page]) for page in request['image_pages']]}
    found, skipped = page_inventory(combined, geometries)
    return combined, found, skipped
