"""校验科学字段基线；更新基线必须先登记已审查的Issue/Spec变更。"""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
path = root / 'backend/data/scientific_form_contract.v1.json'
lock = json.loads((root / 'backend/data/scientific_form_contract.lock.json').read_text())
contract = json.loads(path.read_text())
if hashlib.sha256(path.read_bytes()).hexdigest() != lock['sha256']:
    raise SystemExit('字段契约发生未登记变化；请先审查Issue/Spec，不能自动重录快照')
if contract['version'] != lock['version'] or contract['issue'] != lock['issue']:
    raise SystemExit('字段契约版本或Issue不匹配')
if len(contract['paper_fields']) != 21 or len(contract['state_fields']) != 11:
    raise SystemExit('通用字段数量与已审定基线不一致')
if set(contract['software']) != {'qe', 'epw', 'sscha'} or 'phonon_method' not in contract['condition_fields']:
    raise SystemExit('软件分组或声子方法路径与已审定要求不一致')
for software, keys in contract['software'].items():
    if len(keys) != len(set(keys)) or any(key not in contract['labels'] for key in keys):
        raise SystemExit('软件参数重复或缺少固定名称：' + software)
if (root / 'goserver/models/scientific_form_contract.v1.json').read_bytes() != path.read_bytes():
    raise SystemExit('Go内嵌契约副本与权威清单不一致')
if not (root / lock['spec']).is_file():
    raise SystemExit('契约缺少对应Spec')
print('科学字段契约v' + str(contract['version']) + '基线通过：21论文字段、11材料字段、3软件组')
