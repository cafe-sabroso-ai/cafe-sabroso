import unittest
from fastapi.testclient import TestClient
import app as m
class Tests(unittest.TestCase):
 def setUp(self):self.client=TestClient(m.app)
 def test_socket_turn_and_timer_no_secrets(self):
  code=self.client.post('/rooms').json()['code']
  with self.client.websocket_connect('/ws/'+code)as a:
   a.send_json({'name':'A'});key=a.receive_json()['key'];a.receive_json()
   with self.client.websocket_connect('/ws/'+code)as b:
    b.send_json({'name':'B'});b.receive_json();b.receive_json();a.receive_json()
    a.send_json({'action':'start'});sa=a.receive_json();b.receive_json();self.assertEqual(sa['phase'],'reading');self.assertNotIn('fuse',sa)
    b.send_json({'action':'ready','token':sa['token']});self.assertEqual(b.receive_json()['event'],'error')
    a.send_json({'action':'ready','token':sa['token']});sa=a.receive_json();b.receive_json();self.assertEqual(sa['phase'],'answering')
    with self.client.websocket_connect('/ws/'+code)as c:
     c.send_json({'name':'A','key':key});self.assertEqual(c.receive_json()['key'],key);self.assertEqual(c.receive_json()['phase'],'answering')
 def test_voice_access_control(self):
  self.assertEqual(self.client.post('/voice',json={}).status_code,403);self.assertEqual(self.client.post('/voice',json=[]).status_code,400)
