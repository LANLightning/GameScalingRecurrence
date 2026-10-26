"""Release controls, restore bytecode, stop observation, then stop the loader watcher."""
import json,time,uuid
from pathlib import Path
from bridge_client import command,RUNTIME
base=Path(__file__).resolve().parent
status_path=RUNTIME/'status.json'
status=json.loads(status_path.read_text(encoding='utf8')) if status_path.exists() else {}
if status.get('status')!='shutdown':
 command('shutdown',timeout=5)
 status=json.loads(status_path.read_text(encoding='utf8'))
required=['class_restored','keys_released','observer_stopped','transformer_removed']
if status.get('status')!='shutdown' or not all(status.get(k) for k in required):raise SystemExit('Cleanup not verified: '+json.dumps(status))
stamp=(RUNTIME/'snapshot.json').stat().st_mtime_ns;time.sleep(.3)
if stamp!=(RUNTIME/'snapshot.json').stat().st_mtime_ns:raise SystemExit('Observer still updating snapshots')
(base/'reload.properties').write_text('id='+uuid.uuid4().hex+'\nop=shutdown\n',encoding='utf8')
for _ in range(30):
 if 'Bootstrap shutdown' in (base/'bootstrap-status.txt').read_text(encoding='utf8'):break
 time.sleep(.1)
else:raise SystemExit('Bytecode restored; loader watcher shutdown not yet confirmed')
print(json.dumps({'implementation':status,'telemetry_stopped':True,'bootstrap_shutdown':True},indent=2))
