import os,sys,json,socket,subprocess,time,argparse
from pathlib import Path
import requests
from process_control import identity
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--no-graph',action='store_true');p.add_argument('--port',type=int,default=8095);a=p.parse_args()
with socket.socket() as sock:
 if sock.connect_ex(('127.0.0.1',a.port))==0:raise SystemExit(f'Port {a.port} already occupied. Existing process left running.')
env=os.environ.copy();env['PATH']=str(ROOT/'engine')+';'+env['PATH']
env.update(NINFER_KV_WINDOW='4096',NINFER_KV_RETRIEVE='2048',NINFER_KV_RING='1',NINFER_HOST_PAGEABLE='1',NINFER_KV_REUSE_HOSTBACKED='1',NINFER_TERNARY_KVMEM='1',NINFER_TERNARY_KVMEM_SCORE_QUERY_TAIL='64')
cmd=[str(ROOT/'ninfer-small/ninfer-serve-small.exe'),str(ROOT/'models/ninfer/gamescaling-0.8b-s3-bf16.ninfer'),'--host','127.0.0.1','--port',str(a.port),'--model-id','gamescaling','--max-context','32768','--kv-capacity','8192','--host-kv-mib','512','--host-state-slots','2','--max-shared-prefixes','0','--prefill-chunk','128','--vision','--vision-max-merged','512','--assistant-prefill','--device-profile','off','--chat-template',str(ROOT/'models/GameScaling-0.8B-S3/chat_template.jinja')]
if a.no_graph:cmd.append('--no-cuda-graph')
log=(ROOT/'logs/ninfer-server.log').open('w',encoding='utf8');proc=None
try:
 proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 session=requests.Session();session.trust_env=False
 for _ in range(240):
  if proc.poll() is not None:raise RuntimeError('NInfer exited; inspect logs/ninfer-server.log')
  try:
   if session.get(f'http://127.0.0.1:{a.port}/v1/models',timeout=1).ok:break
  except requests.RequestException:pass
  time.sleep(.5)
 else:raise TimeoutError('NInfer readiness timeout')
 (ROOT/'data/ninfer-session.json').write_text(json.dumps([{'pid':proc.pid,'identity':identity(proc.pid),'command':cmd,'environment':{k:v for k,v in env.items() if k.startswith('NINFER_')}}],indent=2),encoding='utf8')
 print(f'GameScaling NInfer ready: http://127.0.0.1:{a.port}/v1 | BF16 | KVMem/ring | SSE',flush=True)
 print('Ctrl+C stops this NInfer process only.',flush=True)
 while proc.poll() is None:time.sleep(.5)
finally:
 if proc is not None and proc.poll() is None:
  proc.terminate()
  try:proc.wait(timeout=10)
  except subprocess.TimeoutExpired:proc.kill()
 log.close()
