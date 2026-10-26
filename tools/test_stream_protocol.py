import unittest,json
from unittest.mock import patch,MagicMock
from streaming_policy import StreamingPolicy,PolicyConfig
class StreamContract(unittest.TestCase):
 def policy(self,events):
  p=StreamingPolicy('test',PolicyConfig(reasoning=False))
  response=MagicMock();response.__enter__.return_value=response
  response.iter_lines.return_value=[b'data: '+json.dumps(e).encode() for e in events]
  p._session.post=MagicMock(return_value=response)
  return p
 @patch('streaming_policy.encode_image',return_value='data:image/jpeg;base64,test')
 def test_error_event_raises(self,_):
  p=self.policy([{'error':{'message':'worker failed'}}])
  with self.assertRaisesRegex(RuntimeError,'worker failed'):p.act(None)
  self.assertEqual(len(p._history),0)
 @patch('streaming_policy.encode_image',return_value='data:image/jpeg;base64,test')
 def test_incomplete_stream_raises(self,_):
  p=self.policy([{'choices':[{'delta':{'content':'<|action_start|>0 0'}}]}])
  with self.assertRaisesRegex(RuntimeError,'finish reason'):p.act(None)
  self.assertEqual(len(p._history),0)
 @patch('streaming_policy.encode_image',return_value='data:image/jpeg;base64,test')
 def test_complete_stream_parses(self,_):
  p=self.policy([{'choices':[{'delta':{'content':'<|action_start|>0 0 0 ; W ; W ; W ; W ; W ; W'},'finish_reason':'stop'}]}])
  d=p.act(None);self.assertTrue(d.action.parsed);self.assertFalse(d.action.truncated)
if __name__=='__main__':unittest.main()
