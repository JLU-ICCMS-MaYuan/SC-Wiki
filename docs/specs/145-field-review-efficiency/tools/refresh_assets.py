"""将已测量的JSON同步到逐项清单、CSV及图；不连接业务服务。"""
import argparse
import csv
import json
from pathlib import Path
import re

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('measurement',type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
data=json.loads(args.measurement.read_text())
assert len({r['id'] for r in data['units']})==data['coverage']['review_units']
assert sum(len(r['fields']) for r in data['units'])==data['coverage']['editable_entries']
# 逐单元一行，避免审查时为机械缩进展开数万行；原始测量仍可独立保留。
header=json.dumps({k:v for k,v in data.items() if k!='units'},ensure_ascii=False,indent=2).rstrip()[:-1].rstrip()
serialized=header+',\n  "units": [\n'+',\n'.join(json.dumps(u,ensure_ascii=False,separators=(',',':')) for u in data['units'])+'\n  ]\n}\n'
(root/'assets/field-audit.json').write_text(serialized)
def esc(value):return str(value).replace('|','／').replace('\n',' ')
columns=[('status_check','状态检查'),('pdf_title','标题首页核验'),('pdf_authors','作者首页核验'),
         ('history_recovery','历史恢复入口'),('rule_assessment','条件验证'),
         ('quote_location','原文定位'),('association_validation','关联验证')]
old=(root/'field-catalog.md').read_text()
boundary='## 非当前实例与非可编辑内容'
tail=old[old.index(boundary):]
lines=['# 当前草稿逐核对单元清单','','当前447项；方法计数按一次preflight，不是历史累计或完整按钮链次数。',
       '入口可提前返回，0不代表永远不核对；原文定位嵌套于其他检查，列间不可相加。完整键和值见JSON和CSV。']
for group in dict.fromkeys(u['group'] for u in data['units']):
    lines+=['','## '+group,'','| 字段及所属记录 | 审核粒度 | '+' | '.join(label for _,label in columns)+' | 新LLM |',
            '| --- | --- | '+' | '.join('---:' for _ in columns)+' | ---: |']
    for unit in data['units']:
        if unit['group']==group:
            lines.append('| '+esc(unit['label']+' · '+unit['owner'])+' | '+unit['review_granularity']+' | '+
                         ' | '.join(str(unit['counts'].get(key,0)) for key,_ in columns)+' | 0 |')
(root/'field-catalog.md').write_text('\n'.join(lines)+'\n\n'+tail)
with (root/'assets/editable-fields.csv').open('w',encoding='utf-8-sig',newline='') as file:
    writer=csv.writer(file, lineterminator='\n')
    writer.writerow(['分组','核对单元','所属记录','字段路径','入口名称','当前值摘要','字段类型','允许空值','审核粒度']+
                    [label for _,label in columns]+['新LLM请求'])
    for unit in data['units']:
        for field in unit['fields']:
            writer.writerow([unit['group'],unit['id'],unit['owner'],field['path'],field['name'],field['value'],
                             field['type'],field['nullable'],unit['review_granularity']]+
                            [unit['counts'].get(key,0) for key,_ in columns]+[0])
fragment=root/'assets/field-review-map.fragment.html'
payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
html=fragment.read_text()
html,n=re.subn(r'(<script type="application/json" data-audit>).*?(</script>)',lambda m:m[1]+payload+m[2],html,flags=re.S)
assert n==1
fragment.write_text(html)
assert fragment.stat().st_size<1000000
print('同步447项清单、518入口CSV及图；未写业务数据。')
