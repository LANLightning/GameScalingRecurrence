"""Pure GameScaling episodes: goal once, screenshots/history only, no planner or item shortcuts."""
import argparse,json,math,sys,time,uuid,subprocess,statistics,traceback,hashlib
from collections import deque
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--max-decisions',type=int,default=100000);p.add_argument('--max-seconds',type=float,default=300);p.add_argument('--history',type=int,default=5);p.add_argument('--seed-base',type=int,default=20261026);p.add_argument('--backend',choices=['both','ninfer','llama'],default='both');p.add_argument('--resume-directory');p.add_argument('--llama-url',default='http://127.0.0.1:8094/v1');a=p.parse_args()
base=Path(__file__).resolve().parent;root=Path(a.root);sys.dont_write_bytecode=True;sys.path[:0]=[str(base),str(root/'tools'),str(root/'client')]
from bridge_client import snapshot,command,reset,RUNTIME
from streaming_policy import StreamingPolicy,PolicyConfig
import minecraft_runner as game
import requests
ffmpeg=root/'ffmpeg/ffmpeg.exe';ffprobe=ffmpeg.with_name('ffprobe.exe')
report=Path(a.resume_directory).resolve() if a.resume_directory else root/'reports'/('ninfer-five-minute-'+time.strftime('%Y%m%d-%H%M%S'));report.mkdir(exist_ok=bool(a.resume_directory));(root/'reports/ninfer-five-minute-latest.json').write_text(json.dumps({'directory':str(report)}))
origin=json.loads((RUNTIME/'origin.json').read_text());cols=json.loads((base/'surface-columns.json').read_text());survey=json.loads((base/'water-survey.json').read_text())
water={(c['x'],c['y'],c['z']) for c in cols if c['name']=='minecraft:water' and c['properties'].get('level','0')=='0'};near=survey['nearest_candidates'][0];seed=(near['x'],near['y'],near['z']);target={seed};stack=[seed]
while stack:
 x,y,z=stack.pop()
 for q in ((x-1,y,z),(x+1,y,z),(x,y,z-1),(x,y,z+1)):
  if q in water and q not in target:target.add(q);stack.append(q)
goal='Walk from your current location to the bank of the nearest water source. Then obtain one full stack (64) of cobblestone and one full stack (64) of oak logs from the Creative inventory. Then craft one crafting table using the logs; taking a ready-made crafting table from Creative inventory does not count. Complete the tasks in this order. Walk rather than fly. Stop when finished.'
prompt=(root/'minecraft-prompt.txt').read_text(encoding='utf8').replace('Goal: explore nearby terrain and stay alive.','Goal: '+goal)
# Static controls describe the interface; no route, recipe, slot coordinates or stage hints.
prompt=prompt.replace('- E -> Open or close inventory','- E -> Open or close inventory\n- LB / RB / MB -> Left / right / middle mouse click in menus; primary / secondary / pick-block in the world\n- Mouse X Y -> Relative cursor movement in menus; relative camera movement in the world\n- Z -> Mouse wheel scrolling\n- A..Z, zero..nine, Space, Back, Enter -> Keyboard keys; type in focused text fields\n- Shift / Ctrl / Alt -> Hold modifier keys\n- Esc -> Close a screen\n- One..Twelve -> F1..F12 keys')
(report/'prompt.txt').write_text(prompt,encoding='utf8');(report/'initial-state.json').write_text(json.dumps(origin,indent=2))
urls={'ninfer':'http://127.0.0.1:8095/v1','llama':a.llama_url}
meta={'goal':goal,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'config':{'temperature':1,'top_k':20,'top_p':1.0,'min_p':0.0,'presence_penalty':0.0,'frequency_penalty':0.0,'seed_base':a.seed_base,'reasoning':False,'history_len':a.history,'max_tokens':512,'image_size':[854,480],'max_decisions':a.max_decisions,'max_seconds':a.max_seconds},'models':{k:requests.get(v+'/models',timeout=5).json() for k,v in urls.items()},'recording':{'fps':10,'audio':False,'speed':1,'capture':'Minecraft window via FFmpeg gdigrab'},'menu_policy':'Model-opened pause menus remain controllable; external pause/focus stops input','observer_data_given_to_model':False,'subgoal_feedback':False,'target_water_seed':seed,'target_water_component_size':len(target),'origin':origin,'note':'Live game input callbacks, temporary virtual-key support. No give/craft/slot-selection API during episodes. Only experiment reset restores saved state between episodes.'}
if a.resume_directory:
 previous=json.loads((report/'metadata.json').read_text());assert previous['prompt_sha256']==meta['prompt_sha256'] and previous['config']==meta['config'],'Resume configuration mismatch'
else:(report/'metadata.json').write_text(json.dumps(meta,indent=2))
class Observer:
 def __init__(self):self.events={};self.peak_cobble=0;self.peak_logs=0;self.peak_table=0;self.inventory_open=False;self.ever_flying=False;self.craft_grid_seen=False;self.water_distance=float('inf');self.creative_seen=False
 def update(self,d):
  x,y,z=d['position'];items=d['inventory'];counts={}
  for it in items:counts[it['id']]=counts.get(it['id'],0)+it['count']
  cobble=counts.get('minecraft:cobblestone',0);logs=counts.get('minecraft:oak_log',0);table=counts.get('minecraft:crafting_table',0)+(d['carried']['count'] if d['carried']['id']=='minecraft:crafting_table' else 0)
  self.peak_cobble=max(self.peak_cobble,cobble);self.peak_logs=max(self.peak_logs,logs);self.peak_table=max(self.peak_table,table);self.ever_flying|=d['flying'];self.inventory_open|=d['screen'] is not None and 'Inventory' in d['screen'];self.creative_seen|=d['screen'] is not None and 'CreativeModeInventoryScreen' in d['screen']
  dist=min(math.sqrt(max(tx-x,0,x-tx-1)**2+(ty+1-y)**2+max(tz-z,0,z-tz-1)**2) for tx,ty,tz in target);self.water_distance=min(self.water_distance,dist)
  nearwater=d['on_ground'] and not d['in_water'] and not d['flying'] and any(abs(ty+1-y)<=2 and math.hypot(max(tx-x,0,x-tx-1),max(tz-z,0,z-tz-1))<=2.5 for tx,ty,tz in target)
  if nearwater:self.events.setdefault('water_bank',d['wall_ms'])
  if cobble>=64 and self.creative_seen:self.events.setdefault('cobblestone_stack',d['wall_ms'])
  if logs>=64 and self.creative_seen:self.events.setdefault('oak_log_stack',d['wall_ms'])
  grid=d.get('crafting_grid',[]);result=d.get('crafting_result',[])
  if len(grid)==4 and all(i['id'].endswith('_planks') and i['count']>=1 for i in grid) and any(i['id']=='minecraft:crafting_table' and i['count'] for i in result):self.craft_grid_seen=True
  if table and self.craft_grid_seen:self.events.setdefault('crafted_table_observed',d['wall_ms'])
 def done(self):
  e=self.events;return all(k in e for k in ('water_bank','cobblestone_stack','oak_log_stack','crafted_table_observed')) and e['water_bank']<=min(e['cobblestone_stack'],e['oak_log_stack']) and max(e['cobblestone_stack'],e['oak_log_stack'])<=e['crafted_table_observed'] and not self.ever_flying
 def result(self):return dict(events=self.events,peak_cobblestone=self.peak_cobble,peak_oak_logs=self.peak_logs,peak_crafting_tables=self.peak_table,inventory_opened=self.inventory_open,creative_screen_seen=self.creative_seen,craft_grid_seen=self.craft_grid_seen,ever_flying=self.ever_flying,min_distance_to_reference_water=self.water_distance,success=self.done())
results=json.loads((report/'results.json').read_text()) if a.resume_directory else [];video=None;log=None;active=False;recorder_start=None
try:
 for name,url in urls.items():
  if a.backend!='both' and name!=a.backend:continue
  if any(r['backend']==name for r in results):raise RuntimeError('This backend already has a recorded trial; no overwrite')
  deadline=time.monotonic()+60
  while not snapshot()['ready']:
   if time.monotonic()>deadline:raise RuntimeError('Game not foreground/ready')
   time.sleep(.1)
  start=reset(origin);time.sleep(.3);start=snapshot()
  assert math.dist(start['position'],origin['position'])<.05 and abs((start['yaw']-origin['yaw']+180)%360-180)<.2 and abs(start['pitch']-origin['pitch'])<.2,'Initial pose mismatch'
  assert start['inventory']==origin['inventory'] and start['mode']==origin['mode'] and start['crafting_grid']==origin['crafting_grid'] and start['carried']==origin['carried'],'Initial inventory/mode mismatch'
  policy=StreamingPolicy(prompt,PolicyConfig(base_url=url,reasoning=False,history_len=a.history,image_size=(854,480),max_tokens=512,temperature=1,timeout=60));policy.request_backend=name;policy.request_seed_base=a.seed_base
  h=game.u.GetForegroundWindow();title=game.title(h)
  if 'Minecraft' not in title:raise RuntimeError('Wrong foreground window')
  log=(report/(name+'-recorder.log')).open('wb');recorder_start=time.time()
  video=subprocess.Popen([str(ffmpeg),'-hide_banner','-loglevel','warning','-f','gdigrab','-framerate','10','-draw_mouse','1','-i','title='+title,'-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart','-y',str(report/(name+'.mp4'))],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
  time.sleep(.5)
  if video.poll() is not None:raise RuntimeError('Video recorder failed')
  episode=name+'-'+uuid.uuid4().hex[:8];command('episode',name=episode);begin=snapshot();observer=Observer();observer.update(begin);started=time.perf_counter();paused_seconds=0.;interruptions=[];decisions=[];reason='decision_limit';active=True
  print('START '+name+' RECORDING '+str(report/(name+'.mp4')),flush=True)
  for step in range(a.max_decisions):
   state=snapshot()
   if not state['ready']:
    wait_start=time.perf_counter();deadline=wait_start+60
    while not snapshot()['ready']:
     if time.perf_counter()>deadline:raise RuntimeError('Game inactive for 60 seconds')
     time.sleep(.1)
    waited=time.perf_counter()-wait_start;paused_seconds+=waited;interruptions.append({'kind':'inactive_wait','seconds':waited});state=snapshot()
   if state['error']:raise RuntimeError(state['error'])
   if time.perf_counter()-started-paused_seconds>=a.max_seconds:reason='time_limit';break
   if video.poll() is not None:raise RuntimeError('Video recorder stopped unexpectedly')
   if game.u.GetForegroundWindow()!=h:time.sleep(.1);continue
   captured=time.perf_counter();frame=game.capture(h)
   if step%25==0:frame.save(report/f'{name}-{step:03d}.png')
   history_before=list(policy._history);seed_step_before=getattr(policy,'_sampling_step',0);d=policy.act(frame);inferwall=(time.perf_counter()-captured)*1000
   valid=d.action.parsed and not d.action.truncated and not d.action.dropped
   row={'backend':name,'episode':episode,'step':step+1,'frame_state':state,'model_text':d.text,'model_metrics':policy.last_metrics,'capture_to_response_ms':inferwall,'valid':bool(valid),'request_prompt_sha256':meta['prompt_sha256']}
   (report/(name+'-pending-action.json')).write_text(json.dumps(row),encoding='utf8')
   if valid:
    action=d.action
    try:
     ack=command('action',timeout=5,mouse_x=action.mouse[0],mouse_y=action.mouse[1],scroll=int(action.mouse[2]),width=frame.width,height=frame.height,steps=';'.join(' '.join(x) for x in action.steps))
    except RuntimeError as exc:
     if 'World must be active' not in str(exc):raise
     current=snapshot()
     deadline=time.monotonic()+60
     while not snapshot()['ready']:
      if time.monotonic()>deadline:raise
      time.sleep(.1)
     discarded=time.perf_counter()-captured;paused_seconds+=discarded;interruptions.append({'kind':'focus_lost_during_inference','seconds':discarded,'model_text_not_executed':d.text,'wall_ms':current['wall_ms']});policy._history=deque(history_before);policy._sampling_step=seed_step_before;command('episode',name=episode);continue
    row.update(action={'mouse':action.mouse,'steps':action.steps},ack=ack['action_status'],after=ack);observer.update(ack)
   else:row['ack']='not_executed_invalid'
   decisions.append(row)
   (report/(name+'-pending-action.json')).write_text(json.dumps({'pending':False}),encoding='utf8')
   with (report/'decisions.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')
   if not valid:reason='invalid_model_action';break
   if row['ack']!='completed':reason='action_aborted';break
   # Keep observing until the requested five-minute deadline; the fixed goal already says stop when finished.
   if step%10==0:print(name+' '+str(step+1)+' elapsed='+str(round(time.perf_counter()-started))+' pos='+str([round(x,2) for x in ack['position']])+' screen='+str(ack['screen'])+' items='+str([observer.peak_cobble,observer.peak_logs,observer.peak_table]),flush=True)
  command('stop');time.sleep(.3);end=snapshot();elapsed=time.perf_counter()-started
  video.communicate(input=b'q\n',timeout=20);returncode=video.returncode;video=None;log.close();log=None
  result={'backend':name,'episode':episode,'reason':reason,'elapsed_seconds':elapsed,'active_seconds':elapsed-paused_seconds,'interruptions':interruptions,'decision_count':len(decisions),'start':begin,'end':end,'observer_live':observer.result(),'recorder_started_wall_ms':int(recorder_start*1000),'video_exit_code':returncode};results.append(result);active=False
  (report/'episodes.json').write_text(json.dumps(results,indent=2));print('END '+name+' '+reason+' '+str(round(elapsed,2))+'s',flush=True)
  if reason in ('pause_chat_or_focus','focus_loss','action_aborted'):break
except Exception as e:
 (report/'error.txt').write_text(traceback.format_exc(),encoding='utf8');print('ERROR '+repr(e),flush=True)
 if active:
  try:last_state=snapshot();end_fresh=True
  except Exception:last_state=decisions[-1].get('after',state) if decisions else begin;end_fresh=False
  results.append({'backend':name,'episode':episode,'reason':'infrastructure_error','error':repr(e),'elapsed_seconds':time.perf_counter()-started,'decision_count':len(decisions),'start':begin,'end':last_state,'end_state_fresh':end_fresh,'observer_live':observer.result(),'recorder_started_wall_ms':int(recorder_start*1000)})
finally:
 try:command('stop')
 except Exception:pass
 if video is not None:
  try:video.communicate(input=b'q\n',timeout=20)
  except Exception:video.terminate();video.wait(timeout=10)
 if log:log.close()
 allstates=[]
 for line in (RUNTIME/'telemetry.jsonl').read_text(encoding='utf8').splitlines():
  if line.strip():
   try:allstates.append(json.loads(line))
   except json.JSONDecodeError:pass
 for r in results:
  states=[s for s in allstates if s.get('episode')==r['episode']];states=[r['start'],*states,r['end']];states=sorted({s['sequence']:s for s in states}.values(),key=lambda s:s['sequence']);obs=Observer()
  for s in states:obs.update(s)
  gaps=[b['wall_ms']-a['wall_ms'] for a,b in zip(states,states[1:])]
  r.update(observer=obs.result(),samples=len(states),path_xyz=sum(math.dist(a['position'],b['position']) for a,b in zip(states,states[1:])),path_xz=sum(math.hypot(a['position'][0]-b['position'][0],a['position'][2]-b['position'][2]) for a,b in zip(states,states[1:])),max_sample_gap_ms=max(gaps,default=0),telemetry_errors=sum(bool(s['error']) for s in states))
  with (report/(r['backend']+'-telemetry.jsonl')).open('w',encoding='utf8') as f:
   for s in states:f.write(json.dumps(s)+'\n')
  movie=report/(r['backend']+'.mp4')
  if movie.exists():r['video_probe']=json.loads(subprocess.check_output([str(ffprobe),'-v','error','-show_entries','stream=width,height,nb_frames,avg_frame_rate','-show_entries','format=duration,size','-of','json',str(movie)]))
 (report/'results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
 print('RESULT '+str(report),flush=True);print(json.dumps([{k:r.get(k) for k in ('backend','reason','elapsed_seconds','decision_count','samples','path_xyz','path_xz','observer','max_sample_gap_ms','telemetry_errors')} for r in results]),flush=True)
