"""One entry point: dual-backend smoke test, or recorded pure-model Minecraft episodes."""
import argparse,json,os,shutil,subprocess,sys,time,uuid
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
SESSION=requests.Session();SESSION.trust_env=False

def ready(port):
 try:
  r=SESSION.get(f'http://127.0.0.1:{port}/v1/models',timeout=2)
  return r.ok and any(x.get('id')=='gamescaling' for x in r.json().get('data',[]))
 except (requests.RequestException,ValueError):return False

def run(*args,**kwargs):return subprocess.run([str(x) for x in args],check=True,**kwargs)

def java_executable(home):
 candidates=[Path(home)/'bin/java.exe'] if home else []
 if not home:
  if os.getenv('JAVA_HOME'):candidates.append(Path(os.environ['JAVA_HOME'])/'bin/java.exe')
  candidates.append(Path(os.environ.get('APPDATA',''))/'.minecraft/runtime/java-runtime-delta/bin/java.exe')
  if shutil.which('java'):candidates.append(Path(shutil.which('java')))
 for f in candidates:
  if f.is_file():return f.resolve()
 raise RuntimeError('JDK 21 required: pass --java-home (or -JavaHome in PowerShell).')

def attach(java,game,pid):
 base=ROOT/'bridge';runtime=base/'runtime';runtime.mkdir(exist_ok=True)
 if not pid:
  result=run(java.with_name('jcmd.exe'),'-l',capture_output=True,text=True,encoding='utf8')
  candidates=[int(line.split()[0]) for line in result.stdout.splitlines() if any(t in line.lower() for t in ['minecraft','bootstraplauncher','modlauncher']) and line.split()[0].isdigit()]
  if len(candidates)!=1:raise RuntimeError('Cannot identify one Minecraft JVM; pass --pid / -GamePid explicitly.')
  pid=candidates[0]
 # A stopped v6 bootstrap stays in the old JVM: use a fresh Minecraft JVM per complete run.
 if (runtime/'status.json').exists():
  previous=json.loads((runtime/'status.json').read_text())
  if previous.get('status')!='shutdown':raise RuntimeError('Existing bridge runtime not cleanly shut down. Inspect bridge/runtime/status.json before reusing.')
 config=f'gameDir={game.as_posix()}\nruntime={runtime.as_posix()}\npid={pid}\n'
 (base/'bridge.properties').write_text(config,encoding='utf8')
 (base/'reload.properties').write_text(f'id={uuid.uuid4().hex}\nop=load\njar=craft-bridge-5min.jar\n',encoding='utf8')
 run(java,'--add-modules','jdk.attach','-cp',base/'craft-bridge-5min.jar','AttachWaterBridge',base/'bridge.properties')
 sys.path.insert(0,str(base));from bridge_client import snapshot
 for _ in range(120):
  try:
   s=snapshot()
   if s.get('error'):raise RuntimeError(s['error'])
   return
  except (OSError,RuntimeError):time.sleep(.25)
 raise RuntimeError('Bridge not ready: inspect bridge/initialization-error.txt and bootstrap-status.txt.')

def main():
 p=argparse.ArgumentParser();p.add_argument('--backend',choices=['both','ninfer','llama'],default='both');p.add_argument('--seconds',type=int,default=300);p.add_argument('--game-dir');p.add_argument('--world');p.add_argument('--java-home');p.add_argument('--pid',type=int,default=0);a=p.parse_args()
 owned=[];logs=[];attached=False;origin=None;report=None
 if a.game_dir:
  game=Path(a.game_dir).resolve();world=Path(a.world).resolve()
  if not game.is_dir() or not (world/'level.dat').is_file():raise RuntimeError('Valid game directory and current world save required.')
  java=java_executable(a.java_home)
  if a.seconds<=0:raise RuntimeError('Seconds must be positive')
 try:
  for name,port,launcher in [('ninfer',8095,'start_ninfer.py'),('llama',8094,'start_server.py')]:
   if ready(port):
    print(f'Reusing GameScaling on {port}; it will not be stopped by this command.',flush=True);continue
   log=(ROOT/'logs'/f'reproduce-{name}.log').open('w',encoding='utf8');logs.append(log)
   proc=subprocess.Popen([sys.executable,str(ROOT/'tools'/launcher)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);owned.append(proc)
   deadline=time.monotonic()+180
   while not ready(port):
    if proc.poll() is not None or time.monotonic()>deadline:raise RuntimeError(f'{name} did not become ready; see logs/reproduce-{name}.log')
    time.sleep(.5)
  if not a.game_dir:
   for name,port in [('ninfer',8095),('llama',8094)]:
    run(sys.executable,ROOT/'tools/streaming_policy.py','--backend',name,'--base-url',f'http://127.0.0.1:{port}/v1','--trials','3','--report',f'reproduce-{name}.json')
   print('Both backends returned parseable actions. Reports: reports/reproduce-*.json. This is inference validation, not Minecraft task success.')
   return
  print('Entering live mode: GameScaling will control the player; switch to Minecraft and close menus within 120 seconds. Losing focus stops input. Use a disposable single-player world.',flush=True)
  attach(java,game,a.pid);attached=True
  from bridge_client import snapshot,command,reset
  deadline=time.monotonic()+120
  while not snapshot()['ready']:
   if time.monotonic()>deadline:raise RuntimeError('Minecraft did not become foreground/ready')
   time.sleep(.2)
  s=snapshot()
  if s['mode']!='CREATIVE' or s['flying'] or not s['on_ground']:raise RuntimeError('Start standing on solid ground in Creative mode, not flying.')
  command('origin');origin=json.loads((ROOT/'bridge/runtime/origin.json').read_text())
  run(sys.executable,ROOT/'bridge/survey_water.py','--world',world)
  survey=json.loads((ROOT/'bridge/water-survey.json').read_text())
  if not survey['nearest_candidates']:raise RuntimeError('No exposed source water found in saved chunks within 96 blocks. Move to a suitable start and save the world before retrying.')
  run(sys.executable,ROOT/'bridge/run_pure_task.py','--root',ROOT,'--backend',a.backend,'--max-seconds',a.seconds)
  report=Path(json.loads((ROOT/'reports/ninfer-five-minute-latest.json').read_text())['directory'])
  run(sys.executable,ROOT/'bridge/summarize_results.py',report)
  results=json.loads((report/'results.json').read_text())
  expected=2 if a.backend=='both' else 1
  if len(results)!=expected or any(x['reason']!='time_limit' for x in results):raise RuntimeError('Trial stopped early. Raw recordings and failure evidence were preserved: '+str(report))
  if a.backend=='both':run(sys.executable,ROOT/'bridge/make_comparison_video.py',report,'--llama-video',report/'llama.mp4','--output',report/'comparison.mp4','--ffmpeg',ROOT/'ffmpeg/ffmpeg.exe')
  print('Recorded results: '+str(report),flush=True)
 finally:
  try:
   if attached:
    from bridge_client import reset,command
    try:
     command('stop')
     if origin:
      restored=reset(origin);(ROOT/'reports/restored-state.json').write_text(json.dumps(restored,indent=2))
    finally:
     cleanup=run(sys.executable,ROOT/'bridge/shutdown_bridge.py',capture_output=True,text=True,encoding='utf8')
     (ROOT/'reports/cleanup.json').write_text(cleanup.stdout,encoding='utf8')
  finally:
   # Stop only launcher trees created by this invocation; never kill a process by port/name.
   for proc in reversed(owned):
    if proc.poll() is None:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
   for log in logs:log.close()
if __name__=='__main__':main()
