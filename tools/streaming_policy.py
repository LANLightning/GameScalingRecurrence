import json,sys,time,re,os,secrets
from pathlib import Path
import requests
from PIL import Image
ROOT=Path(os.environ.get('GAME_SCALING_ROOT',Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(ROOT/'client'))
from gamescaling import PolicyConfig,GameScalingPolicy
from gamescaling.policy import encode_image,build_request,finalize,Turn,Decision
from gamescaling.action import parse_action,split_reasoning
class StreamingPolicy(GameScalingPolicy):
    def act(self,image):
        url=encode_image(image,self.cfg)
        body=build_request(self.messages(url),self.cfg)
        body.update(enable_thinking=False,stream=True,stream_options={'include_usage':True},reasoning_format='none')
        # Match sampler semantics explicitly; NInfer inherits Qwen non-thinking
        # top_p=.8/presence=1.5 otherwise, unlike the original game client.
        step=getattr(self,'_sampling_step',0);base=getattr(self,'request_seed_base',None)
        seed=secrets.randbits(32) if base is None else (int(base)+step)%4294967295
        body.update(top_k=20,top_p=1.0,min_p=0.0,presence_penalty=0.0,frequency_penalty=0.0,seed=seed)
        self._sampling_step=step+1
        body.pop('continue_final_message',None)
        body.pop('add_generation_prompt',None)
        # llama-server continues a final assistant message with add_generation_prompt=false.
        body['add_generation_prompt']=False
        if getattr(self,'request_backend','ninfer')=='vllm':body['continue_final_message']=True
        t0=time.perf_counter(); text=''; finish=None; usage={}; first=None; first_action=None
        with self._session.post(self.base_url+'/chat/completions',json=body,stream=True,timeout=self.cfg.timeout) as response:
            response.raise_for_status()
            for line in response.iter_lines(chunk_size=1):
                if not line.startswith(b'data: '):continue
                data=line[6:]
                if data==b'[DONE]':break
                event=json.loads(data)
                if event.get('error'):raise RuntimeError('Inference stream failed: '+json.dumps(event['error'],ensure_ascii=False))
                if event.get('usage'):usage=event['usage']
                for choice in event.get('choices',[]):
                    chunk=(choice.get('delta') or {}).get('content') or ''
                    if chunk and first is None:first=(time.perf_counter()-t0)*1000
                    text+=chunk
                    if first_action is None and re.search(r'<\|action_start\|>\s*-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s*;[^;]*;',text):
                        first_action=(time.perf_counter()-t0)*1000
                    if choice.get('finish_reason'):finish=choice['finish_reason']
        if finish is None:raise RuntimeError('Inference stream ended without a finish reason')
        text=finalize(text,finish,self.cfg)
        action=parse_action(text)
        reasoning,_,closed=split_reasoning(text)
        self._history.append(Turn(url,reasoning if closed else '',action.history_text))
        while len(self._history)>self.cfg.history_len:self._history.popleft()
        self.last_metrics={'ttft_ms':first,'first_action_ms':first_action,'total_ms':(time.perf_counter()-t0)*1000,'usage':usage,'sampling':{k:body[k] for k in ('temperature','top_k','top_p','min_p','presence_penalty','frequency_penalty','seed')}}
        return Decision(action,text,reasoning,self.last_metrics['total_ms'],finish,usage.get('completion_tokens'))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--image',default=str(ROOT/'client/examples/doom_battle1.jpg'))
    p.add_argument('--prompt',default=str(ROOT/'client/prompts/example_doom_battle1.txt'))
    p.add_argument('--backend',choices=['ninfer','llama','vllm'],default='ninfer')
    p.add_argument('--report',default='streaming-test.json')
    p.add_argument('--trials',type=int,default=3)
    p.add_argument('--base-url',default='http://127.0.0.1:8095/v1')
    args=p.parse_args()
    cfg=PolicyConfig(base_url=args.base_url,reasoning=False,image_size=(854,480),max_tokens=256,history_len=2)
    policy=StreamingPolicy(Path(args.prompt).read_text(encoding='utf8').rstrip('\n'),cfg)
    policy.request_backend=args.backend
    records=[]
    for i in range(args.trials):
        policy.reset()
        d=policy.act(Image.open(args.image))
        record=dict(trial=i+1,text=d.text,parsed=d.action.parsed,truncated=d.action.truncated,mouse=d.action.mouse,steps=d.action.steps,**policy.last_metrics)
        records.append(record);print(json.dumps(record,ensure_ascii=False),flush=True)
    (ROOT/'reports'/args.report).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
    sys.exit(0 if all(r['parsed'] and not r['truncated'] for r in records) else 1)

