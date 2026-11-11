"""通过现有 Safari / Chrome 会话进行人工黑盒测试；仅使用 Python 标准库。"""

import argparse
import base64
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
APPLICATIONS = {"safari": "Safari", "chrome": "Google Chrome"}
SNAPSHOT = """
const visible = el => !!el.getClientRects().length;
return {
  url: location.href, title: document.title,
  text: document.body.innerText,
  controls: [...document.querySelectorAll('button,a,input,textarea,select,[role=button]')]
    .filter(visible).map(el => ({
      tag: el.tagName, role: el.getAttribute('role'), type: el.type,
      text: el.innerText, label: el.getAttribute('aria-label'),
      placeholder: el.getAttribute('placeholder'), disabled: !!el.disabled,
      name: el.name, id: el.id
    }))
};
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        path.chmod(0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_case(case):
    for role, browser in (("user", "safari"), ("superadmin", "chrome")):
        account = case["accounts"][role]
        if account["browser"] != browser:
            raise ValueError(f"{role} 必须使用 {browser}")
        url = urlsplit(account["origin"])
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("本用例仅操作明确指定的本机网站")
        if url.port != 5173 or url.path or url.query or url.fragment or url.username:
            raise ValueError("origin 必须是本机 5173 端口的完整源地址")
    files = case["files"]
    if sum(item["role"] == "main" for item in files) != 1:
        raise ValueError("必须恰好有一个正文 PDF")
    result = []
    for item in files:
        path = Path(item["path"])
        if item["role"] not in {"main", "supplementary"} or not path.is_absolute():
            raise ValueError("PDF 必须使用绝对路径并明确正文或补充材料角色")
        content = path.read_bytes()
        if not content.startswith(b"%PDF-") or len(content) > 50 * 1024 * 1024:
            raise ValueError(f"PDF 格式或大小不合法：{path}")
        result.append({**item, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return result


def apple_script(browser, mode):
    app = APPLICATIONS[browser]
    if mode == "tabs":
        identity = "index of t" if browser == "safari" else "id of t"
        return f'''on run argv
set output to ""
tell application "{app}"
repeat with w in windows
repeat with t in tabs of w
set tabURL to URL of t
if tabURL is item 1 of argv or tabURL starts with ((item 1 of argv) & "/") then
set output to output & (id of w as text) & (character id 9) & ({identity} as text) & (character id 9) & tabURL & linefeed
end if
end repeat
end repeat
end tell
return output
end run'''
    target = "tab (item 3 of argv as integer)" if browser == "safari" else "tab id (item 3 of argv as integer)"
    execution = "do JavaScript (item 4 of argv) in targetTab" if browser == "safari" else "execute targetTab javascript (item 4 of argv)"
    return f'''on run argv
tell application "{app}"
set targetTab to {target} of window id (item 2 of argv as integer)
set tabURL to URL of targetTab
if tabURL is not item 1 of argv and tabURL does not start with ((item 1 of argv) & "/") then
error "目标标签页不属于本次测试网站"
end if
return {execution}
end tell
end run'''


def call_browser(browser, origin, window=None, tab=None, source=None):
    mode = "tabs" if source is None else "exec"
    args = [origin]
    if source is not None:
        if not window or not tab or window < 1 or tab < 1:
            raise ValueError("必须明确指定正整数 window 和 tab")
        # 原生 URL 检查后再核对当前 origin，防止页面在两次读取之间跳转。
        script = (
            "JSON.stringify((function(){try{"
            f"if(location.origin!=={json.dumps(origin)}) throw new Error('网站来源已变化');"
            + source + "\n}catch(error){return {__scwiki_browser_exception__:String(error)};}})())"
        )
        args += [str(window), str(tab), script]
    result = subprocess.run(
        ["osascript", "-", *args], input=apple_script(browser, mode),
        text=True, capture_output=True, timeout=30, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    output = result.stdout.strip()
    if mode == 'tabs':
        return output
    result = json.loads(output or 'null')
    if isinstance(result,dict) and set(result)=={'__scwiki_browser_exception__'}:
        raise RuntimeError(result['__scwiki_browser_exception__'])
    return result


def run_dir(value):
    path = Path(value).resolve()
    if path.parent != (ROOT / "runs").resolve() or not path.is_dir():
        raise ValueError("run 必须是本目录 runs 下已经建立的一次测试")
    return path


def attach_pdfs(run, case, window, tab, *, method="input"):
    """将真实PDF字节交给正常文件输入或拖放入口，不调用业务API。"""
    if method not in {"input", "drop"}:
        raise ValueError("附件入口仅支持正常文件输入或组件拖放")
    files = validate_case(case)
    if files != case["files"]:
        raise ValueError("PDF 已变化，需要建立新一轮来源记录")
    account = case["accounts"]["user"]
    def execute(source):
        return call_browser(account["browser"], account["origin"], window, tab, source)
    labels = {"main": "论文正文", "supplementary": "补充材料"}
    buffer_key = "__scwiki_test_files_" + uuid4().hex
    key = json.dumps(buffer_key)
    event = {"kind": "attach_pdfs", "actor": "user", "window": window, "tab": tab, "method": method,
             "files": files}
    remove_selector = json.dumps('button[aria-label^="移除 "]')
    selected_selector = json.dumps('[role="region"] button[aria-label^="移除 "]')
    try:
        execute(f"if(document.querySelector({selected_selector})) "
                "throw new Error('上传清单已有选择，请先核对并移除本轮旧选择'); return true;")
        for role in labels:
            role_files = [item for item in files if item["role"] == role]
            if not role_files:
                continue
            selector = json.dumps(f'[role="region"][aria-label="{labels[role]}"] input[type="file"]')
            execute(f"if(document.querySelectorAll({selector}).length!==1) throw new Error('上传区不唯一');"
                    f"if(document.querySelector({selector}).files.length) throw new Error('上传区已有文件');"
                    f"window[{key}]={{files:[],chunks:[]}}; return true;")
            for item in role_files:
                content = Path(item["path"]).read_bytes()
                for offset in range(0, len(content), 24 * 1024):
                    chunk = json.dumps(base64.b64encode(content[offset:offset + 24 * 1024]).decode())
                    execute(f"window[{key}].chunks.push(Uint8Array.from(atob({chunk}),c=>c.charCodeAt(0))); return true;")
                name = json.dumps(Path(item["path"]).name, ensure_ascii=True)
                modified = int(Path(item["path"]).stat().st_mtime_ns // 1_000_000)
                execute(f"window[{key}].files.push(new File(window[{key}].chunks,{name},{{type:'application/pdf',lastModified:{modified}}}));"
                        f"window[{key}].chunks=[]; return true;")
            dispatch = (
                "input.closest('[role=region]').dispatchEvent(new DragEvent('drop',"
                "{bubbles:true,cancelable:true,dataTransfer:dt}));"
                if method == "drop" else
                "input.files=dt.files;input.dispatchEvent(new Event('change',{bubbles:true}));"
            )
            execute(
                f"const dt=new DataTransfer(); for(const file of window[{key}].files) dt.items.add(file);"
                f"const input=document.querySelector({selector});" + dispatch +
                "return true;"
            )
            # React提交DOM可晚于事件返回；仍要求原数量，不放宽文件角色/数量断言。
            import time
            for _ in range(10):
                event[role] = execute(
                    f"return [...document.querySelector({selector}).closest('[role=region]')"
                    f".querySelectorAll({remove_selector})].map(b=>b.getAttribute('aria-label'));"
                )
                if len(event[role]) == len(role_files):
                    break
                time.sleep(.2)
            if len(event[role]) != len(role_files):
                raise ValueError("网页文件清单数量与本轮来源不一致，停止上传")
            execute(f"delete window[{key}]; return true;")
    except Exception as error:
        event["error"] = str(error)
        try:
            execute(f"delete window[{key}]; return true;")
        except Exception:
            pass
        save_event(run, event)
        raise
    print(save_event(run, event))
    print(json.dumps(event, ensure_ascii=False, indent=2))


def save_event(run, event):
    path = run / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{uuid4().hex[:8]}.json"
    write_json(path, {"time": now(), **event})
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "start", "tabs"):
        sub = commands.add_parser(command)
        sub.add_argument("--case", type=Path, default=ROOT / "h3s.json")
        if command == "tabs":
            sub.add_argument("--actor", choices=("user", "superadmin"), required=True)
    for command in ("inspect", "exec", "note", "attach"):
        sub = commands.add_parser(command)
        sub.add_argument("--run", required=True)
        sub.add_argument("--actor", choices=("user", "superadmin"), required=True)
        if command == "note":
            sub.add_argument("--phase", required=True)
            sub.add_argument("--text", required=True)
        else:
            sub.add_argument("--window", type=int, required=True)
            sub.add_argument("--tab", type=int, required=True)
            if command == "exec":
                sub.add_argument("--script", type=Path, required=True)
    args = parser.parse_args()
    if args.command in {"check", "start", "tabs"}:
        case = read_json(args.case)
        if args.command == "tabs":
            account = case["accounts"][args.actor]
            print(call_browser(account["browser"], account["origin"]))
            return
        files = validate_case(case)
        if args.command == "check":
            print(json.dumps(files, ensure_ascii=False, indent=2))
            return
        run = ROOT / "runs" / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
        run.mkdir(parents=True, mode=0o700)
        source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                text=True, capture_output=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--short"], cwd=ROOT,
                               text=True, capture_output=True, check=True).stdout
        write_json(run / "case.json", {**case, "files": files, "source_sha": source,
                                      "worktree_status": dirty, "started": now()})
        print(run)
        return
    run = run_dir(args.run)
    case = read_json(run / "case.json")
    if args.command == "attach":
        if args.actor != "user":
            raise ValueError("PDF 上传仅使用指定用户侧 Safari")
        attach_pdfs(run, case, args.window, args.tab)
        return
    if args.command == "note":
        if args.phase not in {phase["id"] for phase in case["phases"]}:
            raise ValueError("phase 必须来自用例流程")
        print(save_event(run, {"kind": "operator_note", "actor": args.actor,
                               "phase": args.phase, "text": args.text}))
        return
    account = case["accounts"][args.actor]
    source = SNAPSHOT if args.command == "inspect" else args.script.read_text(encoding="utf-8")
    event = {"kind": args.command, "actor": args.actor, "browser": account["browser"],
             "origin": account["origin"], "window": args.window, "tab": args.tab}
    if args.command == "exec":
        script_path = args.script.resolve()
        if not script_path.is_relative_to(run):
            raise ValueError("交互脚本必须保存在本轮 run 目录，便于复查")
        event["script"] = str(script_path.relative_to(run))
        event["script_sha256"] = hashlib.sha256(source.encode()).hexdigest()
    try:
        event["result"] = call_browser(account["browser"], account["origin"], args.window, args.tab, source)
    except Exception as error:
        event["error"] = str(error)
        save_event(run, event)
        raise
    print(save_event(run, event))
    print(json.dumps(event["result"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
