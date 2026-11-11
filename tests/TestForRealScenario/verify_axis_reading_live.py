"""原SI受影响轴新模型读取、正式标定与IR隔离保存，不复用旧AI读数。"""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import json, base64, hashlib, io
from dotenv import load_dotenv


def main():
    load_dotenv('.env')
    import pymupdf
    from PIL import Image
    from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config
    from backend.rag.llm import complete_json
    from backend.ingest.upload_tasks import artifact_directory
    from backend.ingest.document_ir import DocumentIR
    from backend.ingest.chart_reading import VERSION, READING_PROMPT, calibrate_panel, append_readings, _chart_image
    from backend.ingest.image_feedback import read_chart
    from backend.ingest.pdf_regions import render_region_image
    root = Path(__file__).parent/'runs/20261111-peng2017-flash-clean-01'
    out = root/'axis-calibration-live'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    request = json.loads((root/'native-json-failure/prepared-request.json').read_text())['request']
    old = json.loads(request['user_prompt'])
    keep = ['document', 'pdf_page', 'crop_bbox', 'crop_bbox_coordinate_space', 'reading_coordinate_space',
            'crop_image_size', 'selected_regions', 'source_pages', 'crop_sha256', 'image_origin', 'complete_figure', 'context_image_size']
    payload = {key: deepcopy(old[key]) for key in keep}; payload['reader_version'] = VERSION
    source = payload['document']
    path = Path(__file__).parent/'runs/20261106-peng2017/sources/2017 YHn LaHn-彭枫 Supplementary.pdf'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256']
    ir = DocumentIR.model_validate_json((artifact_directory('b5a836764aa24e7cbb88b243a1ed2768')/
        'document_ir'/(source['file_id']+'.json')).read_text()).model_copy(deep=True)
    context = render_region_image(path, payload['complete_figure']); crop = payload['crop_bbox']
    with pymupdf.open(path) as pdf:
        crop, png, origin = _chart_image(pdf, pdf[payload['pdf_page']-1], payload['selected_regions'], crop)
    images = ['data:image/png;base64,'+base64.b64encode(raw).decode() for raw in [context['png'], png]]
    count = [0]; events = []
    def model(prompt, content, **options):
        count[0] += 1
        (out/f'request-{count[0]}.json').write_text(json.dumps({'prompt': prompt, 'content': content, **options}, ensure_ascii=False))
        result = complete_json(prompt, content, **options, _single_attempt=True)
        (out/f'response-{count[0]}.json').write_text(json.dumps(result, ensure_ascii=False))
        print('model_request', count[0], (result.get('action') or {}).get('name'), flush=True)
        return result
    def event(value):
        events.append(value); (out/f'event-{len(events)}.json').write_text(json.dumps(value, ensure_ascii=False))
    token = set_llm_config(catalog_config('LLM1'))
    try:
        answer, crop, feedback = read_chart(model, READING_PROMPT, payload, images, ir, path, source, crop,
            cancelled=lambda: False, on_event=event)
        image = Image.open(io.BytesIO(png)); readings = []; unresolved = []
        for panel in answer['panels']:
            got, missing = calibrate_panel(panel, image, {**source, 'page': payload['pdf_page']}, crop)
            readings.extend(got); unresolved.extend(missing)
        append_readings(ir, readings)
        saved = out/'document-ir.json'; saved.write_text(ir.model_dump_json())
        restored = DocumentIR.model_validate_json(saved.read_text())
        assert len(restored.blocks) == len(ir.blocks)
        result = {'scope': '原SI受影响轴新Flash提取→正式标定→IR隔离保存重读，非整篇或业务验收',
            'model': 'server:LLM1/deepseek-flash', 'calls': count[0], 'readings': len(readings),
            'unresolved': unresolved, 'feedback': feedback, 'source_sha256': source['sha256'],
            'saved_and_reread': True, 'values': [{k:r.get(k) for k in ['panel','value_number','reading_precision','x_reading']} for r in readings]}
        (out/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({k:v for k,v in result.items() if k not in ['feedback','values','unresolved']}, ensure_ascii=False), flush=True)
    except BaseException as error:
        (out/'failure.json').write_text(json.dumps({'error_type': type(error).__name__, 'error': str(error), 'calls': count[0]}, ensure_ascii=False))
        raise
    finally: reset_llm_config(token)


if __name__ == '__main__': main()
