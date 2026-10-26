"""Sequential, isolated local inference benchmark; does not control Minecraft."""
from pathlib import Path
import sys,os,time,json,subprocess,socket,shutil
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from process_control import identity,terminate
TAG='isolated-20261026'
for port in (8093,8094,8095):
 with socket.socket() as s:
  if s.connect_ex(('127.0.0.1',port))==0:raise SystemExit(f'Port {port} is occupied; isolated comparison would be invalid.')
session=requests.Session();session.trust_env=False
results=[]
for name,launch,url,recordfile,lognames in [
 ('ninfer','start_ninfer.py','http://127.0.0.1:8095/v1','ninfer-session.json',['ninfer-server.log']),
 ('llama-q8','start_server.py','http://127.0.0.1:8094/v1','service-session.json',['llama-server.log','adapter.log'])]:
 start=time.perf_counter();proc=None;owned=[]
 log=(ROOT/'logs'/f'{name}-{TAG}-launcher.log').open('w',encoding='utf8')
 try:
  proc=subprocess.Popen([sys.executable,str(ROOT/'tools'/launch)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  for _ in range(240):
   if proc.poll() is not None:raise RuntimeError(f'{name} launcher exited')
   try:
    if session.get(url+'/models',timeout=1).ok:break
   except requests.RequestException:pass
   time.sleep(.5)
  else:raise TimeoutError(name+' readiness timeout')
  # Launcher records only child processes it created, with creation-time identities.
  for _ in range(20):
   try:
    owned=json.loads((ROOT/'data'/recordfile).read_text(encoding='utf8'))
    if owned and all(identity(x['pid'])==x['identity'] for x in owned):break
   except (OSError,ValueError):pass
   time.sleep(.1)
  if not owned or not all(identity(x['pid'])==x['identity'] for x in owned):raise RuntimeError('Cannot verify owned service processes')
  ready_ms=(time.perf_counter()-start)*1000
  gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv,noheader'],text=True).strip()
  print(json.dumps({'backend':name,'ready_ms':ready_ms,'gpu':gpu}),flush=True)
  with (ROOT/'logs'/f'{name}-{TAG}.log').open('w',encoding='utf8') as benchlog:
   run=subprocess.run([sys.executable,str(ROOT/'tools/benchmark_decisions.py'),'--backend','ninfer' if name=='ninfer' else 'llama','--base-url',url,'--name',f'{name}-{TAG}'],stdout=benchlog,stderr=subprocess.STDOUT)
  report=json.loads((ROOT/'reports'/f'{name}-{TAG}-decision-benchmark.json').read_text(encoding='utf8'))
  results.append({'backend':name,'startup_ms':ready_ms,'gpu_after_ready':gpu,'exit_code':run.returncode,'summary':report['summary']})
  print(json.dumps(results[-1]),flush=True)
 finally:
  for record in reversed(owned):terminate(record)
  if proc is not None:
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.terminate()
  log.close()
  for logfile in lognames:
   if (ROOT/'logs'/logfile).exists():shutil.copy2(ROOT/'logs'/logfile,ROOT/'logs'/f'{TAG}-{logfile}')
(ROOT/'reports'/f'{TAG}-comparison.json').write_text(json.dumps(results,indent=2),encoding='utf8')
if any(x['exit_code'] for x in results):raise SystemExit(1)
