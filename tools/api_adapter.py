"""OpenAI-compatible adapter for the official GameScaling client; localhost only."""
import argparse,json,time,uuid,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import requests
from native_protocol import native_request
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8094);p.add_argument('--backend',default='http://127.0.0.1:8093');args=p.parse_args()
http=requests.Session();http.trust_env=False
marker=http.get(args.backend+'/props',timeout=10).json()['media_marker']
lock=threading.Lock()
class Handler(BaseHTTPRequestHandler):
    def send_json(self,status,data):
        encoded=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded)
    def do_GET(self):
        if self.path.rstrip('/')=='/v1/models':return self.send_json(200,{'object':'list','data':[{'id':'gamescaling','object':'model'}]})
        if self.path=='/health':
            try:r=http.get(args.backend+'/health',timeout=5);return self.send_json(r.status_code,r.json())
            except requests.RequestException as e:return self.send_json(503,{'error':str(e)})
        return self.send_json(404,{'error':'Not found'})
    def do_POST(self):
        if self.path!='/v1/chat/completions':return self.send_json(404,{'error':'Not found'})
        try:
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            req=native_request(body,marker)
        except (ValueError,KeyError,TypeError) as e:return self.send_json(400,{'error':str(e)})
        identity='chatcmpl-'+uuid.uuid4().hex;created=int(time.time())
        def base(obj):return {'id':identity,'object':obj,'created':created,'model':'gamescaling'}
        def usage(event):
            t=event.get('timings',{});pn=event.get('tokens_evaluated',t.get('cache_n',0)+t.get('prompt_n',0));cn=event.get('tokens_predicted',t.get('predicted_n',0))
            return {'prompt_tokens':pn,'completion_tokens':cn,'total_tokens':pn+cn,'prompt_tokens_details':{'cached_tokens':t.get('cache_n',0)}}
        def finish(event):return 'length' if event.get('stop_type')=='limit' else 'stop'
        with lock:
            try:
                with http.post(args.backend+'/completion',json=req,stream=req['stream'],timeout=120) as response:
                    if response.status_code!=200:return self.send_json(response.status_code,response.json())
                    if not req['stream']:
                        event=response.json();return self.send_json(200,{**base('chat.completion'),'choices':[{'index':0,'message':{'role':'assistant','content':event.get('content','')},'finish_reason':finish(event)}],'usage':usage(event),'timings':event.get('timings',{})})
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-cache');self.end_headers()
                    for line in response.iter_lines(chunk_size=1):
                        if not line.startswith(b'data: '):continue
                        event=json.loads(line[6:]);done=event.get('stop',False)
                        chunk={**base('chat.completion.chunk'),'choices':[{'index':0,'delta':{'content':event.get('content','')},'finish_reason':finish(event) if done else None}]}
                        if done:chunk.update(usage=usage(event),timings=event.get('timings',{}))
                        self.wfile.write(('data: '+json.dumps(chunk,ensure_ascii=False)+'\n\n').encode());self.wfile.flush()
                    self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError):pass
            except requests.RequestException as e:
                if not req['stream']:self.send_json(502,{'error':str(e)})
    def log_message(self,format,*values):print(format%values,flush=True)
print(f'GameScaling adapter listening on 127.0.0.1:{args.port}',flush=True)
ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
