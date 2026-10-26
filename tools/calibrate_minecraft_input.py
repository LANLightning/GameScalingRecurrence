"""Input-only calibration. Separate from model decisions; no blocks are modified."""
import json,time,sys
from pathlib import Path
from PIL import ImageChops,ImageStat
import minecraft_runner as game
from gamescaling.action import Action
ROOT=Path(__file__).resolve().parents[1]
def main():
 print('Waiting up to 30 seconds: focus the Minecraft world (close menus).',flush=True)
 deadline=time.monotonic()+30
 while True:
  h=game.u.GetForegroundWindow()
  if 'Minecraft' in game.title(h):break
  if time.monotonic()>deadline:raise SystemExit('No foreground Minecraft world; no input sent.')
  time.sleep(.1)
 out=ROOT/'reports'/time.strftime('minecraft-input-calibration-%Y%m%d-%H%M%S');out.mkdir()
 game.state.update(active=True,stop=False,epoch=0);events=[];original=game.send
 def send(e):original(e);events.append(e.type)
 game.send=send
 results=[]
 try:
  for name,action in [('turn_left',Action(mouse=(-80,0,0),steps=[[] for _ in range(6)],parsed=True)),('forward',Action(steps=[['W'] for _ in range(6)],parsed=True))]:
   if game.u.GetForegroundWindow()!=h:break
   before=game.capture(h);before.save(out/(name+'-before.png'));n=len(events)
   game.execute(action,h,0,*before.size);time.sleep(.15)
   after=game.capture(h);after.save(out/(name+'-after.png'))
   delta=sum(ImageStat.Stat(ImageChops.difference(before,after)).mean)/3
   results.append({'test':name,'successful_SendInput_calls':len(events)-n,'mean_pixel_delta':delta})
 finally:game.set_keys(set());game.send=original;game.state['stop']=True
 (out/'result.json').write_text(json.dumps({'kind':'fixed_input_calibration_not_model_output','results':results},indent=2),encoding='utf8');print(out);print(results)
if __name__=='__main__':main()
