"""Install pinned release assets with SHA-256 and safe ZIP extraction."""
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def extract(archive,root):
 root=root.resolve()
 with zipfile.ZipFile(archive) as z:
  for i in z.infolist():
   target=(root/i.filename).resolve()
   if not target.is_relative_to(root) or (i.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe archive member: '+i.filename)
  z.extractall(root)
def install(asset,cache,local=None):
 path=(Path(local)/asset['name']) if local else cache/asset['name']
 if not path.exists() or sha(path)!=asset['sha256']:
  if local:raise RuntimeError('Missing or mismatched local asset: '+str(path))
  temp=path.with_suffix('.part')
  for attempt in range(3):
   try:
    print('Downloading '+asset['name'],flush=True)
    with requests.get(asset['url'],stream=True,timeout=(30,120)) as response:
     response.raise_for_status()
     with temp.open('wb') as f:
      for data in response.iter_content(4*1024*1024):f.write(data)
    if sha(temp)!=asset['sha256']:raise RuntimeError('SHA-256 mismatch: '+asset['name'])
    temp.replace(path);break
   except (requests.RequestException,RuntimeError):
    if attempt==2:raise
 print('Verified '+asset['name'],flush=True);extract(path,ROOT)
def main():
 p=argparse.ArgumentParser();p.add_argument('--asset-directory');p.add_argument('--verify-only',action='store_true');a=p.parse_args()
 for n in ['logs','data','reports','cache']: (ROOT/n).mkdir(exist_ok=True)
 assets=json.loads((ROOT/'release-assets.json').read_text(encoding='utf-8-sig'))['assets']
 if not a.verify_only:
  for asset in assets:
   if asset['install']:install(asset,ROOT/'cache',a.asset_directory)
 subprocess.run([sys.executable,str(ROOT/'tools/verify_runtime.py'),'--hash'],check=True)
 # File hashes cover all redistributed executables/libraries, not just the two model files.
 for item in json.loads((ROOT/'runtime-files.json').read_text(encoding='utf-8-sig')):
  path=ROOT/item['path']
  if not path.is_file() or sha(path)!=item['sha256']:raise RuntimeError('Installed file mismatch: '+str(path))
 print('Installation verified. No game input has been sent.')
if __name__=='__main__':main()
