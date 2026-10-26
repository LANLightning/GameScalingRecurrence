import json,statistics,sys,math
from pathlib import Path
from collections import Counter
p=Path(sys.argv[1]); rows=[json.loads(x) for x in (p/'decisions.jsonl').read_text().splitlines()]; results=json.loads((p/'results.json').read_text()); out={}
for r in results:
 b=r['backend']; rs=[x for x in rows if x['backend']==b]
 def describe(v):
  v=sorted(x for x in v if x is not None); return dict(mean=statistics.mean(v),median=statistics.median(v),p95=v[math.ceil(.95*len(v))-1])
 s=dict(decisions=len(rs),noop_count=sum(not any(x['action']['mouse']) and not any(x['action']['steps']) for x in rs),unique_model_texts=len(set(x['model_text'] for x in rs)),acks=dict(Counter(x['ack'] for x in rs)),keys=dict(Counter(k for x in rs for step in x['action']['steps'] for k in step)))
 for key in ['ttft_ms','first_action_ms','total_ms']:s[key]=describe(x['model_metrics'][key] for x in rs)
 s['capture_to_response_ms']=describe(x['capture_to_response_ms'] for x in rs)
 s['frame_state_to_ack_ms']=describe(x['after']['wall_ms']-x['frame_state']['wall_ms'] for x in rs)
 s['completion_tokens']=describe(x['model_metrics']['usage']['completion_tokens'] for x in rs)
 out[b]=s
(p/'statistics.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
print(json.dumps([{k:r.get(k) for k in ['backend','reason','decision_count','elapsed_seconds','path_xyz','path_xz','samples','max_sample_gap_ms','telemetry_errors','observer','interruptions','video_probe']} for r in results],indent=2))
