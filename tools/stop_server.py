import json
from pathlib import Path
from process_control import terminate
root=Path(__file__).resolve().parents[1]
found=False
for name in ('ninfer-session.json','service-session.json'):
 path=root/'data'/name
 if not path.exists():continue
 found=True
 for record in reversed(json.loads(path.read_text(encoding='utf8'))):
  print(record['pid'],'stopped' if terminate(record) else 'already exited or identity differs; untouched')
if not found:print('No recorded GameScaling service session.')
