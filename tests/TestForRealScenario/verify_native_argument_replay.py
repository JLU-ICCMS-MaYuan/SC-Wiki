"""真实失败的编码重放继续经过原图标定，不把编码恢复当作科学通过。"""
from pathlib import Path
from copy import deepcopy
import json
import base64
import hashlib
import io
from PIL import Image
from backend.rag.structured_output import decode_tool_arguments, validate_output
from backend.ingest.chart_reading import reading_schema, calibrate_panel


def main():
    root = Path(__file__).parent/'runs/20261111-peng2017-flash-clean-01/native-json-failure'
    failed = json.loads(next(p for p in root.glob('failure-*.json') if 'b861' in p.name).read_text())
    raw = json.loads(failed['partial_response'])['tool_calls'][0]['arguments']
    value, encoding = decode_tool_arguments(raw)
    expected, _ = json.JSONDecoder().raw_decode(raw)
    assert value == expected
    validate_output(value, reading_schema())
    prepared = json.loads((root/'prepared-request.json').read_text())['request']
    payload = json.loads(prepared['user_prompt'])
    pdf = Path(__file__).parent/'runs/20261106-peng2017/sources/2017 YHn LaHn-彭枫 Supplementary.pdf'
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == '361ad424b516ced961f64c3aa37ee4e05b1539d3c3d5ed4fbb2659a39413ed93'
    pixels = base64.b64decode(prepared['images'][1].split(',', 1)[1])
    image = Image.open(io.BytesIO(pixels)).convert('RGB')
    source = {'file_id': payload['document']['file_id'], 'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
              'page': payload['pdf_page']}
    results = []
    for panel in value['panels']:
        try:
            readings, issues = calibrate_panel(deepcopy(panel), image, source, payload['crop_bbox'])
            results.append({'panel': panel['panel'], 'readings': readings, 'issues': issues})
        except Exception as error:
            results.append({'panel': panel['panel'], 'error_type': type(error).__name__, 'error': str(error)})
    (root/'canonical-arguments.json').write_text(json.dumps(value, ensure_ascii=False))
    assert json.loads((root/'canonical-arguments.json').read_text()) == expected
    report = {'scope': '真实原图/响应→共享编码器→原Schema→正式标定→隔离保存重读，非科学通过',
        'encoding': encoding, 'all_original_values_unchanged': True, 'model_calls': 0,
        'crop_sha256': hashlib.sha256(pixels).hexdigest(), 'claimed_crop_sha256': payload['crop_sha256'],
        'image_size': image.size, 'calibration_results': results}
    (root/'replay-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__': main()
