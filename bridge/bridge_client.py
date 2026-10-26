import json,os,time,uuid,ctypes,zlib
from ctypes import wintypes as W
from pathlib import Path
RUNTIME=Path(__file__).resolve().parent/'runtime'
# Windows readers must share DELETE so the game can atomically replace snapshots.
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
k.ReadFile.argtypes=[W.HANDLE,ctypes.c_void_p,W.DWORD,ctypes.POINTER(W.DWORD),ctypes.c_void_p]
k.CloseHandle.argtypes=[W.HANDLE]
def shared_read(path):
 h=k.CreateFileW(str(path),0x80000000,7,None,3,0,None)
 if h==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error(),'Cannot open snapshot')
 try:
  data=ctypes.create_string_buffer(65536);n=W.DWORD()
  if not k.ReadFile(h,data,len(data),ctypes.byref(n),None):raise OSError(ctypes.get_last_error(),'Cannot read snapshot')
  return data.raw[:n.value].decode('utf8')
 finally:k.CloseHandle(h)
def snapshot(max_age=2):
 for _ in range(10):
  try:
   raw=json.loads(shared_read(RUNTIME/'snapshot.json'))
   if 'payload' in raw:
    if zlib.crc32(raw['payload'].encode('utf8'))!=raw['crc32']:raise json.JSONDecodeError('CRC mismatch','',0)
    d=json.loads(raw['payload'])
   else:d=raw
   if abs(time.time()*1000-d['wall_ms'])>max_age*1000:raise RuntimeError('Stale game telemetry')
   return d
  except (PermissionError,FileNotFoundError,json.JSONDecodeError):time.sleep(.02)
 raise RuntimeError('Snapshot unavailable')
def command(op,timeout=3,**kwargs):
 ident=uuid.uuid4().hex; values={'id':ident,'op':op,'submitted_ms':int(time.time()*1000),**kwargs}
 tmp=RUNTIME/'command.properties.tmp'
 deadline_write=time.monotonic()+2
 while True:
  values['submitted_ms']=int(time.time()*1000)
  try:
   tmp.write_text(''.join(f'{k}={v}\n' for k,v in values.items()),encoding='utf8')
   os.replace(tmp,RUNTIME/'command.properties');break
  except PermissionError:
   if time.monotonic()>deadline_write:raise
   time.sleep(.02)
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  try:d=snapshot()
  except RuntimeError as e:
   if 'Stale game telemetry' not in str(e):raise
   time.sleep(.02);continue
  if d.get('action_id')==ident:
   if d.get('error'):raise RuntimeError(d.get('error'))
   if op!='action' or d.get('action_status')!='running':return d
  time.sleep(.02)
 raise RuntimeError('No command acknowledgement')
def reset(origin):
 command('reset');deadline=time.monotonic()+4
 while time.monotonic()<deadline:
  d=snapshot();delta=sum((x-y)**2 for x,y in zip(d['position'],origin['position']))**.5
  yaw=abs((d['yaw']-origin['yaw']+180)%360-180)
  if delta<.05 and yaw<.2 and abs(d['pitch']-origin['pitch'])<.2 and d['on_ground'] and d['flying']==origin.get('flying',False) and all(d[k]==origin[k] for k in ('inventory','carried','crafting_grid','selected_slot','mode')):
   time.sleep(.15);return snapshot()
  time.sleep(.05)
 raise RuntimeError('Reset pose/inventory/carried/grid/mode not verified; do not start trial')
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['snapshot','origin','stop','shutdown']);a=p.parse_args()
 print(json.dumps(snapshot() if a.operation=='snapshot' else command(a.operation),ensure_ascii=False,indent=2))
