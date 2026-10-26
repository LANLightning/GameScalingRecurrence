import json,subprocess,socket,time,sys
from pathlib import Path
import requests
from process_control import identity
ROOT=Path(__file__).resolve().parents[1]
session=requests.Session();session.trust_env=False
for port in (8093,8094):
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',port))==0:raise SystemExit(f'Port {port} already occupied. No process changed. Use TEST.bat if GameScaling is already running.')
exe=ROOT/'llama-runtime/llama-server.exe'
cmd=[str(exe),'-m',str(ROOT/'models/gguf/GameScaling-0.8B-S3-Q8_0.gguf'),'--mmproj',str(ROOT/'models/gguf/mmproj-GameScaling-0.8B-S3-F16.gguf'),'--host','127.0.0.1','--port','8093','--alias','gamescaling','-c','16384','-ngl','99','--parallel','1','--flash-attn','on','--image-max-tokens','512','--jinja','--chat-template-file',str(ROOT/'models/GameScaling-0.8B-S3/chat_template.jinja'),'--reasoning-format','none','--special','--no-context-shift']
processes=[];files=[];records=[]
def spawn(command,log):
    f=(ROOT/'logs'/log).open('w',encoding='utf8');files.append(f)
    proc=subprocess.Popen(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    processes.append(proc);records.append({'pid':proc.pid,'identity':identity(proc.pid),'command':command});return proc
try:
    backend=spawn(cmd,'llama-server.log')
    for attempt in range(120):
        if backend.poll() is not None:raise RuntimeError('Backend exited; inspect logs/llama-server.log')
        try:
            if session.get('http://127.0.0.1:8093/health',timeout=1).ok:break
        except requests.RequestException:pass
        time.sleep(.5)
    else:raise TimeoutError('Backend readiness timeout')
    adapter=spawn([sys.executable,str(ROOT/'tools/api_adapter.py')],'adapter.log')
    for attempt in range(40):
        if adapter.poll() is not None:raise RuntimeError('Adapter exited; inspect logs/adapter.log')
        try:
            if session.get('http://127.0.0.1:8094/health',timeout=1).ok:break
        except requests.RequestException:pass
        time.sleep(.25)
    else:raise TimeoutError('Adapter readiness timeout')
    (ROOT/'data/service-session.json').write_text(json.dumps(records,indent=2),encoding='utf8')
    print('GameScaling ready: http://127.0.0.1:8094/v1 | model=gamescaling',flush=True)
    print('Keep this launcher running. Ctrl+C stops only these GameScaling processes.',flush=True)
    while all(proc.poll() is None for proc in processes):time.sleep(.5)
except KeyboardInterrupt:pass
finally:
    for proc in reversed(processes):
        if proc.poll() is None:proc.terminate()
    for proc in processes:
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill()
    for f in files:f.close()
