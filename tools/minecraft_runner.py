"""Screen-based Minecraft runner. F8 toggles; F9 exits. Defaults to observation only."""
import argparse,ctypes,json,threading,time,sys
from ctypes import wintypes as W
from pathlib import Path
from PIL import ImageGrab
from streaming_policy import StreamingPolicy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'client'))
from gamescaling import PolicyConfig
u=ctypes.WinDLL('user32',use_last_error=True)
u.SetProcessDPIAware();u.GetForegroundWindow.restype=W.HWND
u.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
u.GetClientRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
u.ClientToScreen.argtypes=[W.HWND,ctypes.POINTER(W.POINT)]
UP=ctypes.c_size_t
class M(ctypes.Structure):_fields_=[('dx',W.LONG),('dy',W.LONG),('mouseData',W.DWORD),('dwFlags',W.DWORD),('time',W.DWORD),('dwExtraInfo',UP)]
class K(ctypes.Structure):_fields_=[('wVk',W.WORD),('wScan',W.WORD),('dwFlags',W.DWORD),('time',W.DWORD),('dwExtraInfo',UP)]
class H(ctypes.Structure):_fields_=[('uMsg',W.DWORD),('wParamL',W.WORD),('wParamH',W.WORD)]
class U(ctypes.Union):_fields_=[('mi',M),('ki',K),('hi',H)]
class I(ctypes.Structure):_anonymous_=('value',);_fields_=[('type',W.DWORD),('value',U)]
u.SendInput.argtypes=[W.UINT,ctypes.POINTER(I),ctypes.c_int]
KEYS={**{x:ord(x) for x in 'WASDEQF'},'Space':32,'Shift':16,'Ctrl':17,**{s:ord(str(i)) for i,s in enumerate(['one','two','three','four','five','six','seven','eight','nine'],1)}}
BUTTONS={'LB':(2,4),'RB':(8,16),'MB':(32,64)}
held=set();state={'active':False,'stop':False,'epoch':0}
def title(hwnd):
    b=ctypes.create_unicode_buffer(512);u.GetWindowTextW(hwnd,b,512);return b.value

def send(event):
    if u.SendInput(1,ctypes.byref(event),ctypes.sizeof(I))!=1:raise OSError(ctypes.get_last_error(),'SendInput failed')

def button(name,down):
    if name in BUTTONS:
        send(I(type=0,mi=M(dwFlags=BUTTONS[name][0 if down else 1])))
    elif name in KEYS:
        scan=u.MapVirtualKeyW(KEYS[name],0);send(I(type=1,ki=K(wScan=scan,dwFlags=8|(0 if down else 2))))

def set_keys(keys):
    keys=set(keys)&(set(KEYS)|set(BUTTONS))
    for key in held-keys:button(key,False)
    for key in keys-held:button(key,True)
    held.clear();held.update(keys)

def hotkeys():
    old8=old9=False
    while not state['stop']:
        a=bool(u.GetAsyncKeyState(0x77)&0x8000);b=bool(u.GetAsyncKeyState(0x78)&0x8000)
        if b and not old9:state['stop']=True
        if a and not old8:
            state['active']=not state['active'];state['epoch']+=1;print('ACTIVE' if state['active'] else 'PAUSED',flush=True)
        old8,old9=a,b;time.sleep(.01)

def capture(hwnd):
    rect=W.RECT();origin=W.POINT()
    if not u.GetClientRect(hwnd,ctypes.byref(rect)) or not u.ClientToScreen(hwnd,ctypes.byref(origin)):raise OSError('Window rectangle unavailable')
    if rect.right<=0 or rect.bottom<=0:raise ValueError('Window is minimized')
    return ImageGrab.grab(bbox=(origin.x,origin.y,origin.x+rect.right,origin.y+rect.bottom),all_screens=True)

def execute(action,hwnd,epoch,width,height):
    started=time.perf_counter();px=py=0
    for i,keys in enumerate(action.steps):
        if state['stop'] or not state['active'] or epoch!=state['epoch'] or u.GetForegroundWindow()!=hwnd:break
        set_keys(keys)
        nx=round(action.mouse[0]*width/1000*(i+1)/6);ny=round(action.mouse[1]*height/1000*(i+1)/6)
        if nx!=px or ny!=py:send(I(type=0,mi=M(dx=nx-px,dy=ny-py,dwFlags=1)))
        px,py=nx,ny
        if i==0 and action.mouse[2]:send(I(type=0,mi=M(mouseData=(int(action.mouse[2])*120)&0xffffffff,dwFlags=0x800)))
        while time.perf_counter()<started+(i+1)*.2/6:
            if state['stop'] or not state['active'] or u.GetForegroundWindow()!=hwnd:break
            time.sleep(.002)
    set_keys(set())

def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:8095/v1');p.add_argument('--execute',action='store_true');p.add_argument('--title',default='Minecraft');p.add_argument('--goal',default='Explore nearby terrain and stay alive.');p.add_argument('--steps',type=int,default=30);p.add_argument('--max-age',type=float,default=2.0);args=p.parse_args()
    system=(ROOT/'minecraft-prompt.txt').read_text(encoding='utf8').replace('Goal: explore nearby terrain and stay alive.','Goal: '+args.goal)
    policy=StreamingPolicy(system,PolicyConfig(base_url=args.base_url,reasoning=False,image_size=(854,480),max_tokens=256,history_len=2,timeout=120))
    print('EXECUTION ENABLED' if args.execute else 'OBSERVE ONLY: actions will only be printed',flush=True)
    print('Enter a world, focus Minecraft, then F8 to start/pause; F9 to exit.',flush=True)
    threading.Thread(target=hotkeys,daemon=True).start();count=0
    try:
        with (ROOT/'logs/minecraft-decisions.jsonl').open('a',encoding='utf8') as log:
            while not state['stop'] and count<args.steps:
                hwnd=u.GetForegroundWindow()
                if not state['active'] or args.title.casefold() not in title(hwnd).casefold():
                    set_keys(set());time.sleep(.05);continue
                epoch=state['epoch'];t=time.perf_counter();frame=capture(hwnd)
                try:d=policy.act(frame)
                except Exception as error:
                    print(str(error),flush=True);policy.reset();state['active']=False;continue
                valid=d.action.parsed and not d.action.truncated and not d.action.dropped
                fresh=time.perf_counter()-t<=args.max_age
                acted=args.execute and valid and fresh and not state['stop'] and state['active'] and state['epoch']==epoch and u.GetForegroundWindow()==hwnd
                record={'time':time.time(),'text':d.text,'latency_ms':d.latency_ms,'parsed':valid,'executed':acted,'fresh':fresh}
                print(json.dumps(record,ensure_ascii=False),flush=True);log.write(json.dumps(record,ensure_ascii=False)+'\n');log.flush()
                if acted:execute(d.action,hwnd,epoch,*frame.size)
                else:policy.reset()  # never teach history that an unexecuted action happened
                count+=1
    finally:set_keys(set());state['stop']=True
if __name__=='__main__':main()
