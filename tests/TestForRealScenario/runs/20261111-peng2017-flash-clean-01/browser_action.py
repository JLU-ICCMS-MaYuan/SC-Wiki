"""每次按实际URL重新定位浏览器标签，并保存网页脚本及结果。"""
import sys,json,subprocess,time
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scenario import call_browser,save_event
ROOT=Path(__file__).parent
ORIGINS={"safari":"http://127.0.0.1:5173","chrome":"http://localhost:5173"}
def act(browser,url,source,window=None):
    origin=ORIGINS[browser]
    matches=[]
    for line in call_browser(browser,origin).splitlines():
        w,t,u=line.split("\t")
        if u==url and (window is None or int(w)==window):matches.append((int(w),int(t)))
    if len(matches)!=1:raise ValueError(f"目标标签不唯一: {url} {matches}")
    w,t=matches[0]
    if browser=='safari':
        focus=f'''tell application "Safari"
set selectedTab to tab {t} of window id {w}
if URL of selectedTab is not {json.dumps(url)} then error "目标标签地址已变化"
set current tab of window id {w} to selectedTab
set index of window id {w} to 1
activate
end tell'''
        subprocess.run(['osascript','-'],input=focus,text=True,capture_output=True,check=True,timeout=15)
        time.sleep(.2)  # Safari切换到原标签后，先让原生窗口完成一次布局。
    script=ROOT/("action-"+uuid4().hex[:10]+".js")
    script.write_text(f"if(location.href!=={json.dumps(url)}) throw new Error('论文地址已变化');\n"+source)
    result=call_browser(browser,origin,w,t,script.read_text())
    save_event(ROOT,dict(kind="browser",browser=browser,url=url,window=w,tab=t,script=script.name,result=result))
    return result
if __name__=="__main__":
    print(json.dumps(act(*sys.argv[1:]),ensure_ascii=False))
