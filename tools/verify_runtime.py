"""Read-only deployment preflight; works after relocating the runtime folder."""
import sys,importlib,importlib.metadata,json,subprocess,struct,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def add(name,ok,detail=''):checks.append({'check':name,'ok':bool(ok),'detail':detail})
add('Python x64',struct.calcsize('P')==8,sys.version.split()[0])
for name in ['requests','Pillow','Jinja2']:
 try:add(name,True,importlib.metadata.version(name))
 except importlib.metadata.PackageNotFoundError:add(name,False,'Run SETUP_RUNTIME.bat')
for rel in ['ninfer-small/ninfer-serve-small.exe','models/ninfer/gamescaling-0.8b-s3-bf16.ninfer','models/gguf/GameScaling-0.8B-S3-Q8_0.gguf','models/gguf/mmproj-GameScaling-0.8B-S3-F16.gguf','models/GameScaling-0.8B-S3/chat_template.jinja','llama-runtime/llama-server.exe','engine/cudart64_13.dll','client/gamescaling/policy.py','client/examples/doom_battle1.jpg','minecraft-prompt.txt']:
 p=ROOT/rel;add(rel,p.is_file(),str(p.stat().st_size) if p.is_file() else 'missing')
try:
 info=subprocess.check_output(['nvidia-smi','--query-gpu=name,compute_cap,memory.total','--format=csv,noheader'],text=True,stderr=subprocess.STDOUT).strip()
 add('CUDA target sm89','8.9' in info,info)
except (OSError,subprocess.SubprocessError) as e:add('NVIDIA GPU',False,str(e))
try:
 sys.path.insert(0,str(ROOT/'tools'));import native_protocol,streaming_policy
 add('client + template imports',True)
except Exception as e:add('client + template imports',False,str(e))
if '--hash' in sys.argv:
 for record in json.loads((ROOT/'runtime-artifacts.json').read_text(encoding='utf8')):
  path=ROOT/record['path']
  if path.is_file():
   with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
   add('sha256 '+record['path'],actual==record['sha256'],actual)
  else:add('sha256 '+record['path'],False,'missing')
print(json.dumps({'root':str(ROOT),'checks':checks},ensure_ascii=False,indent=2))
sys.exit(0 if all(x['ok'] for x in checks) else 1)
