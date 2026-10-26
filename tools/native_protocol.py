"""Preserve the checkpoint's exact Jinja serialization on llama.cpp's native multimodal API."""
import copy,os
from pathlib import Path
from jinja2 import Environment,StrictUndefined
ROOT=Path(os.environ.get('GAME_SCALING_ROOT',Path(__file__).resolve().parents[1]))
ENV=Environment()
def fail(message):raise ValueError(message)
ENV.globals['raise_exception']=fail
TEMPLATE=ENV.from_string((ROOT/'models/GameScaling-0.8B-S3/chat_template.jinja').read_text(encoding='utf8'))
def native_request(body,marker):
    messages=copy.deepcopy(body['messages']);images=[]
    for message in messages:
        if isinstance(message.get('content'),list):
            for item in message['content']:
                if item.get('type')=='image_url':
                    url=item['image_url']['url']
                    if not url.startswith('data:image/') or ';base64,' not in url:raise ValueError('Pass images as base64 data URLs.')
                    images.append(url.split(',',1)[1])
    continuation=body.get('continue_final_message',messages[-1]['role']=='assistant')
    prompt=TEMPLATE.render(messages=messages,add_generation_prompt=not continuation)
    if continuation:
        if messages[-1]['role']!='assistant':raise ValueError('Continuation requires final assistant prefill.')
        prompt=prompt[:prompt.rfind('<|im_end|>')]
    placeholder='<|vision_start|><|image_pad|><|vision_end|>'
    if prompt.count(placeholder)!=len(images):raise ValueError('Image placeholder count differs from images.')
    prompt=prompt.replace(placeholder,marker)
    result=dict(prompt={'prompt_string':prompt,'multimodal_data':images},n_predict=body.get('max_tokens',256),temperature=body.get('temperature',1.0),top_p=body.get('top_p',1.0),top_k=body.get('top_k',0),min_p=body.get('min_p',0.0),presence_penalty=body.get('presence_penalty',0.0),frequency_penalty=body.get('frequency_penalty',0.0),repeat_penalty=1.0,stop=body.get('stop',['<|action_end|>']),special=True,cache_prompt=True,stream=body.get('stream',False))

    if 'seed' in body and body['seed'] is not None:result['seed']=body['seed']
    return result
