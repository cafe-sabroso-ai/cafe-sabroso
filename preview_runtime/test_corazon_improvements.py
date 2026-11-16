import asyncio,sys,types,ast,pathlib,unittest
from unittest.mock import AsyncMock,patch
import webapp as w
import rehearsal_words
sys.modules['app']=rehearsal_words
class Tests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.p=[{'id':1,'name':'Pepe','ws':None},{'id':2,'name':'Teresa','ws':None}]
  self.r={'players':self.p,'turn':0,'phase':'ahorcado','timer_task':None,'game':'ahorcado','scores':{1:0,2:0},'ahorcado':{'levels':{},'used':set(),'word':'CASA','hint':'Donde vivís','guessed':{'A'},'wrong':{'Z'},'attempts':2}}
  self.mocks=[]
  for n in ['narrate','broadcast','tell','wrong_answer_feedback']:
   p=patch.object(w,n,AsyncMock(return_value='Incorrecta. '));p.start();self.mocks.append(p)
  p=patch.object(w,'room_state',lambda r:{});p.start();self.mocks.append(p)
 async def asyncTearDown(self):
  w.cancel_timer(self.r)
  for p in self.mocks:p.stop()
 async def test_personal_word_survives_pass(self):
  with patch.object(w,'ah_start_turn',AsyncMock()):await w.ah_pass(self.r,'Fallaste')
  self.assertEqual(self.r['ahorcado']['saved_words'][1]['word'],'CASA')
  self.assertEqual(self.r['turn'],1)
  self.r['ahorcado'].update(word='MATE',hint='Bebida',guessed={'M'},wrong=set(),attempts=3)
  with patch.object(w,'ah_start_turn',AsyncMock()):await w.ah_pass(self.r,'Fallaste')
  await w.ah_start_turn(self.r)
  self.assertEqual(self.r['ahorcado']['word'],'CASA')
  self.assertEqual(self.r['ahorcado']['attempts'],2)
  self.assertEqual(self.r['ahorcado']['guessed'],{'A'})
 async def test_exhausted_word_removed(self):
  self.r['ahorcado']['attempts']=0
  self.r['ahorcado']['saved_words']={1:{'word':'CASA'}}
  with patch.object(w,'ah_start_turn',AsyncMock()):await w.ah_pass(self.r,'Fin')
  self.assertNotIn(1,self.r['ahorcado']['saved_words'])
 async def test_correct_letter_keeps_turn(self):
  await w.ah_guess(self.r,self.p[0],('letter','C'))
  self.assertEqual(self.r['turn'],0)
  self.assertEqual(self.r['ahorcado']['guessed'],{'A','C'})
 async def test_missed_letter_preserves_remaining(self):
  with patch.object(w,'ah_start_turn',AsyncMock()):await w.ah_guess(self.r,self.p[0],('letter','X'))
  self.assertEqual(self.r['ahorcado']['saved_words'][1]['attempts'],1)
  self.assertIn('X',self.r['ahorcado']['saved_words'][1]['wrong'])
 async def test_bomb_stale_judgment_ignored(self):
  self.r.update(phase='bomba',bomba={'prompt':'Animales','keywords':['gato'],'said':set(),'generation':1})
  async def judge(*args):self.r['bomba']['generation']=2;return False
  with patch.object(w,'judge_bomba',judge),patch.object(w,'bb_explode',AsyncMock()) as explode:
   await w.bb_answer(self.r,self.p[0],'silla');explode.assert_not_called()
 async def test_mystery_simultaneous_correct_only_one(self):
  self.r.update(phase='misterio',misterio={'case':('Caso','Historia','Solucion',['solucion'],[]),'generation':1,'solved':{},'lives':{1:3,2:3}})
  entered=asyncio.Event()
  async def judge(*args):entered.set();await asyncio.sleep(.01);return 'acierto'
  with patch.object(w,'judge_misterio',judge),patch.object(w,'mst_next_case',AsyncMock()) as nxt:
   await asyncio.gather(w.mst_guess(self.r,self.p[0],'solucion'),w.mst_guess(self.r,self.p[1],'solucion'))
   self.assertEqual(sum(self.r['misterio']['solved'].values()),1);nxt.assert_awaited_once()
 async def test_mystery_stale_response_no_penalty(self):
  self.r.update(phase='misterio',misterio={'case':('Caso','Historia','Solucion',[],[]),'generation':1,'lives':{1:3}})
  async def judge(*args):self.r['misterio']['generation']=2;return 'lejos'
  with patch.object(w,'judge_misterio',judge):await w.mst_guess(self.r,self.p[0],'no')
  self.assertEqual(self.r['misterio']['lives'][1],3)
 async def test_chat_bad_target_no_synthesis(self):
  rehearsal_words.synthesize=AsyncMock()
  await w.handle_chat(self.r,self.p[0],{'text':'hola','to':'bad'})
  rehearsal_words.synthesize.assert_not_called()
 async def test_solo_bomb_miss_is_not_a_win(self):
  self.r.update(capacity=1,players=[self.p[0]],phase='bomba',bomba={'lives':{1:3}})
  with patch.object(w,'game_over',AsyncMock()) as win,patch.object(w,'bb_next_prompt',AsyncMock()) as nxt:
   await w.bb_explode(self.r,self.p[0],'Error')
   win.assert_not_called();nxt.assert_awaited_once();self.assertEqual(self.r['bomba']['lives'][1],2)
 async def test_solo_mystery_miss_is_not_a_win(self):
  self.r.update(capacity=1,players=[self.p[0]],phase='misterio',misterio={'case':('Caso','Historia','Solucion',[],[]),'generation':1,'lives':{1:3}})
  with patch.object(w,'judge_misterio',AsyncMock(return_value='lejos')),patch.object(w,'game_over',AsyncMock()) as win:
   await w.mst_guess(self.r,self.p[0],'incorrecta')
   win.assert_not_called();self.assertEqual(self.r['misterio']['lives'][1],2)
 def test_bomb_timing_unchanged(self):self.assertEqual((w.BOMBA_FUSE_MIN,w.BOMBA_FUSE_MAX),(8,20))
 def test_accessible_chat_replay(self):
  self.assertIn('audio.controls = true',w.PAGE);self.assertIn('role="log"',w.PAGE)
  self.assertNotIn('if (!msg.echo) queueAudio(msg.url',w.PAGE)
if __name__=='__main__':unittest.main(verbosity=2)
