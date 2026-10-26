"""生成固定 Demo 样本；不调用 AI、业务 API 或数据库。需 Pillow。"""
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[5]
FEATURE = ROOT / 'docs/specs/161-spectrum-manual-editor-demo'
PUBLIC = FEATURE / 'demo/public/fixtures'
PUBLIC.mkdir(parents=True, exist_ok=True)
(FEATURE / 'assets').mkdir(parents=True, exist_ok=True)
source = ROOT / 'docs/specs/154-alpha2f-detail-demo/assets/false-peak-source.png'
shutil.copyfile(source, PUBLIC / 'source.png')
image = Image.open(source).convert('RGB')
digest = hashlib.sha256(source.read_bytes()).hexdigest()

def document(kind, title, viewport, plot):
    return dict(schemaVersion=1, id=kind, title=title,
        description='真实来源图 + 固定演示点；含人为设置的误识别和缺失，用于试用编辑，不作为材料科学结果。',
        source=dict(id='lasc-290-figure-A', sha256=digest, image='/fixtures/source.png', width=image.width, height=image.height, viewport=viewport, plot=plot),
        calibration=dict(direction='y', frequency=dict(pixels=[435, 65], values=[0, 60], unit='THz'),
            amplitude=dict(pixels=[plot[0], plot[2]], values=[0, plot[2]-plot[0]], unit='pixel'), amplitudeEvidence=''),
        curves=[], zero=None, operations=[])

alpha = document('alpha2f', 'α²F 谱函数', [632, 8, 170, 460], [637, 17, 790, 435])
snapshot_path = ROOT / 'docs/specs/154-alpha2f-detail-demo/assets/false-peak-after.json'
snapshot = json.loads(snapshot_path.read_text())
points = []
segment = 0
for i, p in enumerate(snapshot['points']):
    if p['amplitude_pixel'] is None or p['frequency_pixel'] > 429:
        segment += 1
        continue
    points.append(dict(id=f'a-{i}', x=p['amplitude_pixel'], y=p['frequency_pixel'], segment=f'a-seg-{segment}', status='固定提取样本'))
# 显式注入独立的图例误识别片段，频率不与既有整像素行重复。
points.extend(dict(id=f'a-legend-{i}', x=738+i*3, y=414.37-i*.8, segment='a-legend', status='演示误识别') for i in range(5))
alpha['curves'] = [dict(id='alpha', name='α²F', color='#e9526b', points=sorted(points, key=lambda p:-p['y']))]

dos = document('phdos', '声子 DOS', [470, 8, 162, 460], [474, 17, 627, 435])
predicates = [lambda r,g,b: b>140 and r<100 and g<110, lambda r,g,b: r>150 and b>80 and g<130, lambda r,g,b: g>65 and r<100 and b<110]
for name, color, predicate in zip(['La','Sc','H'], ['#6256dd','#d84491','#07996c'], predicates):
    pts, seg, previous = [], 0, None
    for y in range(429, 25, -1):
        xs = [x for x in range(474, 627) if predicate(*image.getpixel((x,y))) and not (x>=529 and 270<=y<=348)]
        if not xs:
            previous = None
            continue
        if previous is None: seg += 1
        # 固定像素读数仅供交互，不作为正式提取或科学校验。
        x = xs[len(xs)//2]
        pts.append(dict(id=f'{name}-{y}',x=x,y=y,segment=f'{name}-{seg}',status='演示像素取样'))
        previous = y
    if name == 'La':
        pts.extend(dict(id=f'La-legend-{i}', x=532+i*6, y=284.25-i*.1, segment='La-legend',status='演示误识别') for i in range(8))
    dos['curves'].append(dict(id=name,name=name,color=color,points=sorted(pts,key=lambda p:-p['y'])))

(FEATURE/'demo/src/fixtures.json').write_text(json.dumps([alpha,dos],ensure_ascii=False,indent=2)+'\n')
manifest = dict(source_file=str(source.relative_to(ROOT)), source_sha256=digest, source_size=[image.width,image.height],
    alpha_snapshot=str(snapshot_path.relative_to(ROOT)), alpha_snapshot_sha256=hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
    notes=['α²F 只复用 amplitude_pixel/frequency_pixel，未复用可能来自累计 λ 的物理幅值。', '两类样本均移除 y>429 的低频点供人工补点练习。','α²F 追加 a-legend-*；DOS La 追加 La-legend-* 图例误识别示例。','PhDOS 固定像素取样不代表正式重新提取或科学验收。'],
    counts={d['id']:{c['id']:len(c['points']) for c in d['curves']} for d in [alpha,dos]})
(FEATURE/'assets/fixtures.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
