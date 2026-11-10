"""原PDF字节进入真实Safari上传组件；每次交互按当前URL重新定位标签。"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]))
import scenario
original=scenario.call_browser
URL='http://127.0.0.1:5173/upload'
WINDOW=7839

def safe_browser(browser,origin,window=None,tab=None,source=None):
    if source is None:return original(browser,origin)
    matches=[]
    for line in original(browser,origin).splitlines():
        w,t,u=line.split('\t')
        if int(w)==WINDOW and u==URL:matches.append((int(w),int(t)))
    if len(matches)!=1:raise RuntimeError('本轮上传标签不唯一或网址已变化')
    w,t=matches[0]
    return original(browser,origin,w,t,'if(location.href!=='+json.dumps(URL)+') throw new Error("上传网址变化");\n'+source)

scenario.call_browser=safe_browser
case=json.loads((ROOT/'case.json').read_text())
scenario.attach_pdfs(ROOT,case,WINDOW,1)
