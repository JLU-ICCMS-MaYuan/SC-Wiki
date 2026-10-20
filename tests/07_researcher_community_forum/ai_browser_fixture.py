"""在一次性验收库上启动真实 Go API、Python AI 路由与构建制品。"""
import functools
import http.client
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.request


def run(root, directory, app, owner_id, question_id):
    from sqlalchemy.orm import Session
    from backend.database import engine
    from backend.models import User
    from backend.community.models import CommunityEntry
    from backend.security import create_access_token
    import uvicorn
    def port():
        with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
    app.dependency_overrides.clear()
    # 模型选择目录作为 UI 夹具；模型调用/权限/社区接口仍为真实后端。
    @app.get('/api/rag/llm/catalog')
    def catalog():return {'items':[], 'default_id':''}
    @app.get('/api/rag/llm/current')
    def current():return {'model':'fixture','provider_name':'fixture'}
    py_port,go_port=port(),port()
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=py_port,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    binary=directory/'goserver'
    subprocess.run([str(root/'.local/go/bin/go'),'build','-o',str(binary),'.'],cwd=root/'goserver',check=True)
    log=(directory/'go-browser.log').open('w')
    env={**os.environ,'PORT':str(go_port),'BIND_HOST':'127.0.0.1','PYTHON_BACKEND_URL':f'http://127.0.0.1:{py_port}','REDIS_ADDR':os.environ['REDIS_URL'].split('//')[1].split('/')[0]}
    process=subprocess.Popen([str(binary)],cwd=root/'goserver',env=env,stdout=log,stderr=log)
    proxy=None
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{go_port}/health',timeout=1):break
            except Exception:time.sleep(.1)
        class Proxy(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
            def request(self):
                if self.path.startswith('/api/'):
                    conn=http.client.HTTPConnection('127.0.0.1',go_port,timeout=30)
                    length=int(self.headers.get('Content-Length',0))
                    conn.request(self.command,self.path,body=self.rfile.read(length) if length else None,headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','connection')})
                    result=conn.getresponse();body=result.read();self.send_response(result.status)
                    self.send_header('Content-Type',result.getheader('Content-Type','application/json'));self.send_header('Content-Length',str(len(body)));self.end_headers()
                    try:self.wfile.write(body)
                    except (BrokenPipeError, ConnectionResetError):pass
                    finally:conn.close()
                else:
                    if not Path(self.translate_path(self.path.split('?')[0])).is_file():self.path='/index.html'
                    super().do_GET()
            do_GET=do_POST=do_PATCH=do_PUT=do_DELETE=request
        proxy=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Proxy,directory=str(root/'frontend/static')))
        threading.Thread(target=proxy.serve_forever,daemon=True).start()
        with Session(engine) as db,db.begin():
            owner=db.get(User,owner_id)
            identities={'guest':None}
            for role in ('user','admin','superadmin'):
                user=owner if role=='superadmin' else User(email=f'{role}@browser.test',username=f'browser_{role}',real_name=role,password_hash='unused',role=role,is_email_verified=True,account_status='active')
                if role!='superadmin':db.add(user);db.flush()
                identities[role]={'token':create_access_token({'sub':user.email,'sv':user.session_version}),'user':{'id':user.id,'username':user.username,'email':user.email,'role':role,'is_email_verified':True,'account_status':'active'}}
            question=db.get(CommunityEntry,question_id)
            fixture={'users':identities,'question_id':question_id,'question_title':question.title}
        fixture_path=directory/'browser-fixture.json';fixture_path.write_text(json.dumps(fixture))
        browser_env={**env,'COMMUNITY_BASE_URL':f'http://127.0.0.1:{proxy.server_port}','COMMUNITY_ARTIFACT_DIR':str(directory),'COMMUNITY_BROWSER_FIXTURE':str(fixture_path)}
        subprocess.run([str(Path(os.sys.executable).parent/'node'),str(root/'tests/07_researcher_community_forum'/os.environ.get('COMMUNITY_BROWSER_SCRIPT','ai-community-browser.mjs'))],env=browser_env,check=True)
    finally:
        (directory/'browser-fixture.json').unlink(missing_ok=True)
        if proxy:proxy.shutdown()
        process.terminate();process.wait(timeout=10);log.close()
        server.should_exit=True;thread.join(timeout=10)
