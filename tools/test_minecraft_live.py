"""Paired live Minecraft smoke test. No mining/placing; F9 or focus loss stops input."""
import argparse,copy,hashlib,json,statistics,threading,time
from pathlib import Path
from PIL import ImageChops,ImageStat
import minecraft_runner as game
from streaming_policy import StreamingPolicy,PolicyConfig,ROOT

def main():
 p=argparse.ArgumentParser();p.add_argument('--temperature',type=float,default=0);p.add_argument('--goal',default='Stay in place and turn the camera left slightly to inspect the mountain on your left. Output a negative mouse X movement. Do not press any key or click any mouse button.');p.add_argument('--pairs',type=int,default=6);p.add_argument('--execute',action='store_true');p.add_argument('--max-age',type=float,default=2.0);a=p.parse_args()
 print('Waiting up to 30 seconds: focus the Minecraft world (close menus).',flush=True)
 deadline=time.monotonic()+30
 while True:
  h=game.u.GetForegroundWindow()
  if 'Minecraft' in game.title(h):break
  if time.monotonic()>deadline:raise SystemExit('No foreground Minecraft world; no input sent.')
  time.sleep(.1)
 output=ROOT/'reports'/time.strftime('minecraft-live-%Y%m%d-%H%M%S');output.mkdir(parents=True)
 prompt=(ROOT/'minecraft-prompt.txt').read_text(encoding='utf8')
 prompt=prompt
 prompt=prompt.replace('Goal: explore nearby terrain and stay alive.','Goal: '+a.goal)
 policies={}
 for name,url in [('ninfer','http://127.0.0.1:8095/v1'),('llama','http://127.0.0.1:8094/v1')]:
  policies[name]=StreamingPolicy(prompt,PolicyConfig(base_url=url,reasoning=False,image_size=(854,480),temperature=a.temperature,max_tokens=128,history_len=0))
  policies[name].request_backend=name
 game.state.update(active=True,stop=False,epoch=0)
 threading.Thread(target=game.hotkeys,daemon=True).start()
 inputs=[];original_send=game.send
 def counted_send(event):
  original_send(event);inputs.append({'type':event.type,'time':time.perf_counter()})
 game.send=counted_send
 rows=[];reason='completed'
 try:
  for pair in range(a.pairs):
   if game.state['stop'] or not game.state['active'] or game.u.GetForegroundWindow()!=h:reason='paused_or_focus_lost';break
   epoch=game.state['epoch'];capture_start=time.perf_counter();frame=game.capture(h);capture_ms=(time.perf_counter()-capture_start)*1000
   frame.save(output/f'{pair+1:02d}-before.png');digest=hashlib.sha256(frame.tobytes()).hexdigest()
   order=['ninfer','llama'] if pair%2==0 else ['llama','ninfer'];decisions={};pair_rows=[]
   for name in order:
    if game.state['stop'] or game.u.GetForegroundWindow()!=h:reason='stopped_during_inference';break
    started=time.perf_counter();decision=policies[name].act(frame);decisions[name]=decision
    row={'pair':pair+1,'backend':name,'input_sha256':digest,'capture_ms':capture_ms,'wall_ms':(time.perf_counter()-started)*1000,'valid':decision.action.parsed and not decision.action.truncated and not decision.action.dropped,'text':decision.text,**policies[name].last_metrics}
    rows.append(row);pair_rows.append(row)
   if len(decisions)!=2:break
   chosen=order[0];action=copy.deepcopy(decisions[chosen].action)
   allowed={'W','A','S','D','Shift'};filtered=[[k for k in step if k in allowed] for step in action.steps]
   action.steps=filtered;action.mouse=(max(-30,min(30,action.mouse[0])),max(-30,min(30,action.mouse[1])),0)
   fresh=time.perf_counter()-capture_start<=a.max_age
   may_execute=a.execute and all(r['valid'] for r in pair_rows) and fresh and game.u.GetForegroundWindow()==h and game.state['active'] and not game.state['stop']
   count=len(inputs);execute_start=time.perf_counter()
   if may_execute:game.execute(action,h,epoch,*frame.size)
   after=game.capture(h) if game.u.GetForegroundWindow()==h else None
   delta=None
   if after is not None:
    after.save(output/f'{pair+1:02d}-after.png');delta=sum(ImageStat.Stat(ImageChops.difference(frame.convert('RGB'),after.convert('RGB'))).mean)/3
   for row in pair_rows:
    row.update(selected=row['backend']==chosen,execution_attempted=may_execute and row['backend']==chosen,successful_input_calls=(len(inputs)-count) if row['backend']==chosen else 0,fresh=fresh,filtered_action={'mouse':action.mouse,'steps':action.steps} if row['backend']==chosen else None,after_pixel_mean_delta=delta,execution_and_capture_ms=(time.perf_counter()-execute_start)*1000)
    print(json.dumps(row),flush=True)
   (output/'records.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
   time.sleep(.1)
 except Exception as e:reason=f'{type(e).__name__}: {e}';raise
 finally:
  game.set_keys(set());game.state['stop']=True;game.send=original_send
  result={'kind':'live_minecraft_paired_test','instance':'User-opened Minecraft 1.21.1 NeoForge','reason':reason,'execute_requested':a.execute,'goal':a.goal,'temperature':a.temperature,'input_calls':len(inputs),'note':'Same screenshot per pair; backend order alternates; history disabled; only selected output drives movement/aim after filtering. Pixel change alone is not proof of action causality or game-object correctness.','records':rows}
  (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
  (ROOT/'reports/latest-live-test.json').write_text(json.dumps({'directory':str(output),'result':result},indent=2),encoding='utf8')
  print('RESULT '+str(output/'result.json'),flush=True)
if __name__=='__main__':main()
