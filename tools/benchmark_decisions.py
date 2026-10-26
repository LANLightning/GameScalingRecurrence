import sys,json,time,statistics,argparse
from pathlib import Path
from PIL import Image
from streaming_policy import StreamingPolicy,PolicyConfig,ROOT
p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:8095/v1');p.add_argument('--backend',choices=['ninfer','llama','vllm'],default='ninfer');p.add_argument('--name',default='ninfer');p.add_argument('--trials',type=int,default=10);a=p.parse_args()
prompt=(ROOT/'client/prompts/example_doom_battle1.txt').read_text(encoding='utf8');frame=Image.open(ROOT/'client/examples/doom_battle1.jpg')
rows=[]
for scenario in ['identical_reset','history_append','jpeg_variants_reset']:
 cfg=PolicyConfig(base_url=a.base_url,reasoning=False,image_size=(854,480),temperature=0,max_tokens=128,history_len=2)
 policy=StreamingPolicy(prompt,cfg);policy.request_backend=a.backend
 for i in range(a.trials):
  if scenario!='history_append':policy.reset()
  if scenario=='jpeg_variants_reset':cfg.jpeg_quality=70+i%20
  start=time.perf_counter();d=policy.act(frame)
  row=dict(scenario=scenario,trial=i+1,wall_ms=(time.perf_counter()-start)*1000,valid=d.action.parsed and not d.action.truncated and not d.action.dropped,text=d.text,**policy.last_metrics)
  rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
summary={}
for scenario in ['identical_reset','history_append','jpeg_variants_reset']:
 group=[r for r in rows if r['scenario']==scenario];warm=group[1:]
 summary[scenario]={'valid':sum(r['valid'] for r in group),'total':len(group),'first_ms':group[0]['wall_ms']}
 for key in ['ttft_ms','first_action_ms','total_ms','wall_ms']:
  values=sorted(r[key] for r in warm if r[key] is not None)
  summary[scenario][key]={'p50':statistics.median(values),'max':max(values),'n':len(values)}
result={'backend':a.name,'settings':vars(cfg),'note':'Offline single Doom sample. JPEG variants are synthetic changes, not game frames. First action time is observed only; no keys are executed. History contains generated actions, not observed gameplay. Warm statistics exclude first request in each scenario.','summary':summary,'records':rows}
(ROOT/'reports'/f'{a.name}-decision-benchmark.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,indent=2));sys.exit(0 if all(r['valid'] for r in rows) else 1)
