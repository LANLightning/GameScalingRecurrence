import unittest,json
from unittest.mock import patch,MagicMock
from streaming_policy import StreamingPolicy,PolicyConfig
from native_protocol import native_request
class SamplingContract(unittest.TestCase):
 @patch('streaming_policy.encode_image',return_value='data:image/jpeg;base64,dGVzdA==')
 def test_explicit_sampling_and_replayable_seed_sequence(self,_):
  p=StreamingPolicy('goal',PolicyConfig(reasoning=False,temperature=1));p.request_seed_base=20261026
  response=MagicMock();response.__enter__.return_value=response
  response.iter_lines.return_value=[b'data: '+json.dumps({'choices':[{'delta':{'content':'<|action_start|>0 0 0 ; W ; W ; W ; W ; W ; W'},'finish_reason':'stop'}]}).encode()]
  p._session.post=MagicMock(return_value=response)
  for seed in [20261026,20261027]:
   p.act(None);body=p._session.post.call_args.kwargs['json'];self.assertEqual(body['seed'],seed)
   self.assertEqual({k:body[k] for k in ['top_k','top_p','min_p','presence_penalty','frequency_penalty']},dict(top_k=20,top_p=1,min_p=0,presence_penalty=0,frequency_penalty=0));self.assertEqual(p.last_metrics['sampling']['seed'],seed)
 def test_native_adapter_preserves_seed_zero_and_sampling(self):
  body=dict(messages=[dict(role='system',content='goal'),dict(role='user',content='frame'),dict(role='assistant',content='<think>\n\n</think>')],seed=0,top_k=20,top_p=.9,min_p=.1,presence_penalty=.3,frequency_penalty=.2)
  result=native_request(body,'IMAGE');self.assertEqual(result['seed'],0)
  for key in ['top_k','top_p','min_p','presence_penalty','frequency_penalty']:self.assertEqual(result[key],body[key])
  self.assertTrue(result['prompt']['prompt_string'].endswith('<think>\n\n</think>'));self.assertEqual(len(body['messages']),3)
if __name__=='__main__':unittest.main()
