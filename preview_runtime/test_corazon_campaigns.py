import asyncio,json,unittest,random
from collections import Counter
from unittest.mock import AsyncMock,patch
import rehearsal_app,webapp as w,mystery_race as m,hangman_campaign as h,rehearsal_words as rw
class Request:
 async def json(self):return {'mode':'misterio','capacity':2}
class Sock:
 def __init__(self):self.messages=[]
 async def send_text(self,s):self.messages.append(json.loads(s))
 async def close(self,**kwargs):pass
class Content(unittest.TestCase):
 def test_counts_and_ids(self):
  self.assertEqual(len(m.BANK),50);self.assertEqual(len(m.BY_ID),50)
  self.assertEqual(set(Counter(c['category']for c in m.BANK).values()),{10})
  self.assertEqual(len(set(c['story']for c in m.BANK)),50)
  self.assertEqual(len(rw.AHORCADO_BANK),100);self.assertEqual(len(set(w for w,h in rw.AHORCADO_BANK)),100)
 def test_all_accepted_examples(self):
  for c in m.BANK:
   for a in c['accepted']:
    with self.subTest(case=c['id'],answer=a):self.assertEqual(m.judge(c,a),'acierto')
 def test_negation_extra_and_wrong_controls(self):
  for c in m.BANK:
   a=c['accepted'][-1]
   self.assertNotEqual(m.judge(c,'no es '+a),'acierto')
   self.assertNotEqual(m.judge(c,a+' o una silla espacial'),'acierto')
   for text in c['rejected']:self.assertEqual(m.judge(c,text),'lejos')
 def test_balanced_order(self):
  for seed in range(20):
   seq=m.order(random.Random(seed));self.assertEqual(len(seq),len(set(seq)))
   for i in range(0,50,5):self.assertEqual({m.BY_ID[x]['category']for x in seq[i:i+5]},set(m.CATEGORIES))
 def test_hangman_queue_no_repeats(self):
  for _ in range(10):self.assertEqual(len({x[0]for x in h.make_queue()}),100)
 def test_long_positions(self):
  text=w.ah_positions_text('DESTORNILLADOR','R',rw.AHORCADO_SPEAK);self.assertIn('14',text)
class Campaign(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  code=(await w.crear_sala(Request()))['code'];self.room=w.rooms[code]
  self.players=[{'id':1,'name':'Pepe','ws':Sock()},{'id':2,'name':'Teresa','ws':Sock()},{'id':3,'name':'Mira','spectator':True,'ws':Sock()}]
  self.room['players']=self.players
  self.mock=patch.object(w,'say',AsyncMock());self.say=self.mock.start()
  self.narr=patch.object(w,'narrate',AsyncMock());self.narr.start()
  await m.start(self.room)
  for p in self.players[:2]:await m.action(self.room,p,"spin",m.getrun(self.room,p["id"])["token"])
 async def asyncTearDown(self):
  for r in self.room.get('misterio',{}).get('runs',{}).values():m.cancel(r)
  w.cancel_timer(self.room);self.mock.stop();self.narr.stop()
 async def answer(self,p):
  run=m.getrun(self.room,p['id']);
  if run.get('needs_spin'):await m.action(self.room,p,'spin',run['token'])
  await m.ready(self.room,p['id'],run['token']);case=m.case_for(self.room,run);await w.mst_guess(self.room,p,case['accepted'][-1],run['token']);return case
 async def test_independent_progress_and_private_views(self):
  old=m.case_for(self.room,m.getrun(self.room,2));await self.answer(self.players[0])
  self.assertEqual(m.getrun(self.room,1)['index'],1);self.assertEqual(m.getrun(self.room,2)['index'],0)
  await m.action(self.room,self.players[0],'spin',m.getrun(self.room,1)['token'])
  state=w.room_state(self.room);p=w.private_player_state(state,1);q=w.private_player_state(state,2);spect=w.private_player_state(state,3)
  self.assertNotIn('_mystery_views',p);self.assertNotEqual(p['misterio']['title'],q['misterio']['title']);self.assertNotIn('case',spect['misterio'])
  self.assertNotIn('solution',json.dumps(p));self.assertEqual(q['misterio']['title'],old['title'])
 async def test_private_hints(self):
  p=self.players[0];run=m.getrun(self.room,1);case=m.case_for(self.room,run)
  for q in self.players:q['ws'].messages.clear()
  await m.action(self.room,p,'hint',run['token'])
  other=json.dumps(self.players[1]['ws'].messages,ensure_ascii=False);self.assertNotIn(case['hints'][0],other)
  self.assertEqual(self.say.call_args.kwargs['to'],p)
 async def test_same_case_two_people_both_credit(self):
  await asyncio.gather(self.answer(self.players[0]),self.answer(self.players[1]))
  self.assertEqual([m.getrun(self.room,i)['index']for i in (1,2)],[1,1])
 async def test_duplicate_token_not_next_case(self):
  p=self.players[0];run=m.getrun(self.room,1);token=run['token'];c=await self.answer(p)
  await w.mst_guess(self.room,p,c['accepted'][0],token);self.assertEqual(run['index'],1)
 async def test_unknown_is_not_penalized(self):
  p=self.players[0];run=m.getrun(self.room,1);await m.ready(self.room,1,run['token']);await w.mst_guess(self.room,p,'Una reformulación todavía no revisada',run['token']);self.assertEqual(run['lives'],3);self.assertEqual(run['index'],0)
 async def test_50_cases_real_completion_no_repeat(self):
  p=self.players[0];run=m.getrun(self.room,1)
  for _ in range(50):await self.answer(p)
  self.assertEqual(len(run['solved']),50);self.assertEqual(len(set(run['solved'])),50);self.assertEqual(self.room['phase'],'gameover');self.assertEqual(self.room['misterio']['winner'],1)
 async def test_roulette_hides_next_case_until_own_spin(self):
  p=self.players[0];run=m.getrun(self.room,1);await self.answer(p)
  hidden=m.view(self.room,1);self.assertTrue(hidden['needs_spin']);self.assertEqual(hidden['case'],'');self.assertEqual(hidden['category'],'')
  self.assertFalse(await m.ready(self.room,1,run['token']))
  await m.action(self.room,p,'hint',run['token']);self.assertEqual(run['hint'],'')
  await m.action(self.room,p,'spin',run['token']);self.assertFalse(m.view(self.room,1)['needs_spin']);self.assertTrue(m.view(self.room,1)['case'])
  token=run['token'];await m.action(self.room,p,'spin',token);self.assertEqual(run['token'],token)
  self.assertEqual(m.getrun(self.room,2)['index'],0)
 async def test_reconnect_preserves_case_and_waits_for_read(self):
  p=self.players[0];run=m.getrun(self.room,1)
  await self.answer(p);await m.action(self.room,p,'spin',run['token']);case=m.case_for(self.room,run);run['remaining']=82
  await m.ready(self.room,1,run['token']);old=run['token'];m.suspend(self.room,p)
  self.assertIsNone(run['started']);self.assertGreater(run['token'],old)
  self.assertFalse(await m.ready(self.room,1,old))
  await m.resume(self.room,p)
  self.assertIs(m.case_for(self.room,run),case);self.assertEqual(run['index'],1);self.assertEqual(run['remaining'],82)
  self.assertIsNone(run['started']);self.assertTrue(await m.ready(self.room,1,run['token']))
 async def test_timeout_then_hint_is_retryable(self):
  p=self.players[0];run=m.getrun(self.room,1);run['remaining']=0
  await m.action(self.room,p,'hint',run['token'])
  self.assertEqual(run['remaining'],150);self.assertEqual(run['index'],0)
  self.assertTrue(await m.ready(self.room,1,run['token']))
 async def test_scoreboard_updates_private_token_before_audio(self):
  p=self.players[0];run=m.getrun(self.room,1);await m.ready(self.room,1,run['token']);p['ws'].messages.clear()
  await m.action(self.room,p,'progress',run['token'])
  self.assertEqual(p['ws'].messages[-1]['misterio']['token'],run['token'])
  self.assertTrue(await m.ready(self.room,1,run['token']))
 async def test_voice_failure_does_not_hold_other_players(self):
  self.mock.stop()
  try:
   with patch.object(w,'bounded_voice_mp3',AsyncMock(side_effect=RuntimeError('test voice outage'))):
    await w.say(self.room,'Caso privado para una sola persona',to=self.players[0],grid_ack={'game':'misterio','token':1,'turn':1})
   self.assertNotIn('natural_voice_gate',self.room)
   self.assertIn('voice_retry',self.players[0]);self.assertNotIn('voice_retry',self.players[1])
   self.assertTrue(await m.ready(self.room,2,m.getrun(self.room,2)['token']))
  finally:self.mock.start()
 async def test_double_finish_has_one_winner(self):
  for pid in (1,2):
   run=m.getrun(self.room,pid);run['index']=49;run['solved']=self.room['misterio']['order'][:49]
  await asyncio.gather(self.answer(self.players[0]),self.answer(self.players[1]))
  self.assertIn(self.room['misterio']['winner'],(1,2))
  self.assertEqual(sum(len(m.getrun(self.room,pid)['solved'])==50 for pid in (1,2)),1)
 async def test_hangman_full_100_and_fail_not_point(self):
  self.room.update(game='ahorcado',phase='ahorcado',turn=0,players=[self.players[0]],ahorcado={'long_campaign':True,'levels':{},'used':set(),'word':None,'hint':'','guessed':set(),'wrong':set(),'attempts':0})
  self.room['scores']={1:0};seen=[];await w.ah_start_turn(self.room)
  for i in range(100):
   seen.append(self.room['ahorcado']['word'])
   if i==10:
    self.room['ahorcado']['attempts']=0;await w.ah_pass(self.room,'agotó')
   else:await w.ah_solved(self.room,self.players[0])
  self.assertEqual(len(set(seen)),100);self.assertEqual(self.room['scores'][1],99);self.assertEqual(self.room['phase'],'gameover')
 async def test_hangman_saved_turn(self):
  self.room.update(game='ahorcado',phase='ahorcado',turn=0,players=self.players[:2],ahorcado={'long_campaign':True,'levels':{},'used':set(),'word':None,'hint':'','guessed':set(),'wrong':set(),'attempts':0})
  await w.ah_start_turn(self.room);first=self.room['ahorcado']['word'];self.room['ahorcado']['wrong']={'Z'};self.room['ahorcado']['attempts']=2
  await w.ah_pass(self.room,'error');await w.ah_pass(self.room,'tiempo')
  self.assertEqual(self.room['ahorcado']['word'],first);self.assertEqual(self.room['ahorcado']['attempts'],2);self.assertEqual(h.run(self.room,1)['dealt'],1)
if __name__=='__main__':unittest.main(verbosity=2)
