import unittest,json,random
from engine import Room,GameError
class Test(unittest.TestCase):
 def setUp(self):
  self.t=0.;self.r=Room(clock=lambda:self.t,rng=random.Random(7));self.a=self.r.join('A');self.b=self.r.join('B');self.r.start(self.a)
 def test_reading_does_not_burn(self):
  f=self.r.fuse;self.t+=500;self.r.tick();self.assertEqual(self.r.fuse,f);self.assertEqual(self.r.phase,'reading')
 def test_ready_and_correct_pass(self):
  self.r.ready(self.a,self.r.token);self.t+=3;old=self.r.fuse;self.r.answer(self.a,self.r.token,self.r.question['correct']);self.assertEqual(self.r.turn,self.b);self.assertEqual(self.r.phase,'reading');self.assertAlmostEqual(self.r.fuse,old-3)
 def test_wrong_keeps_holder_new_question(self):
  self.r.ready(self.a,self.r.token);old=self.r.question['id'];self.r.answer(self.a,self.r.token,(self.r.question['correct']+1)%3);self.assertEqual(self.r.turn,self.a);self.assertNotEqual(self.r.question['id'],old)
 def test_deadline_late_answer_cannot_pass(self):
  self.r.ready(self.a,self.r.token);self.t+=100
  with self.assertRaises(GameError):self.r.answer(self.a,self.r.token,self.r.question['correct'])
  self.assertEqual(self.r.players[self.a]['lives'],2);self.assertEqual(self.r.phase,'round_end')
 def test_repeated_tick_only_one_life(self):
  self.r.ready(self.a,self.r.token);self.t+=100
  for _ in range(5):self.r.tick()
  self.assertEqual(self.r.players[self.a]['lives'],2)
 def test_stale_and_wrong_holder(self):
  for key,tok in [(self.b,self.r.token),(self.a,self.r.token-1),(self.a,True)]:
   with self.assertRaises(GameError):self.r.ready(key,tok)
 def test_private_fuse_and_solution(self):
  text=json.dumps(self.r.view(self.a));self.assertNotIn('fuse',text);self.assertNotIn('correct',text);self.assertNotIn('deck',text)
 def test_reconnect_not_extra_place(self):
  key=self.r.join('Otra',self.a);self.assertEqual(key,self.a);self.assertEqual(len(self.r.players),2)
 def test_duplicate_answer_no_double_pass(self):
  self.r.ready(self.a,self.r.token);t=self.r.token;c=self.r.question['correct'];self.r.answer(self.a,t,c)
  with self.assertRaises(GameError):self.r.answer(self.a,t,c)
  self.assertEqual(self.r.players[self.a]['score'],1)
 def test_last_alive_wins(self):
  self.r.players[self.a]['lives']=1;self.r.ready(self.a,self.r.token);self.t+=100;self.r.tick();self.assertEqual(self.r.winner,self.b)
 def test_six_complete_until_winner(self):
  r=Room(clock=lambda:self.t,rng=random.Random(9));keys=[r.join(str(i))for i in range(6)];r.start(keys[0]);count=0
  while r.phase!='finished':
   if r.phase=='round_end':r.next_round(keys[0])
   r.ready(r.turn,r.token);self.t+=100;r.tick();count+=1
  self.assertEqual(count,17);self.assertEqual(len(r.active()),1)
 def test_no_repeat_and_tier_progression(self):
  r=self.r;levels=[];ids=[]
  for _ in range(90):
   ids.append(r.question['id']);levels.append(r.question['level']);r.ready(r.turn,r.token);r.answer(r.turn,r.token,r.question['correct'])
  self.assertEqual(r.phase,'finished');self.assertEqual(len(set(ids)),90);self.assertEqual(levels,sorted(levels));self.assertIsNone(r.winner)
 def test_heat_shortens_only_between_rounds(self):
  r=self.r;r.players[self.a]['lives']=30;r.players[self.b]['lives']=30
  for n in range(1,8):
   self.assertEqual(r.round,n);lo,hi={1:(45,75),2:(35,60),3:(25,45)}[min(3,(n+1)//2)]
   self.assertTrue(lo<=r.fuse<=hi);self.assertEqual(r.view(self.a)['heat'],min(3,(n+1)//2))
   r.ready(r.turn,r.token);self.t+=100;r.tick()
   if n<7:r.next_round(self.a)
 def test_disconnect_does_not_pause_started_fuse(self):
  self.r.ready(self.a,self.r.token);self.t+=100;self.r.tick();self.assertEqual(self.r.players[self.a]['lives'],2)
 def test_invalid_choices_and_early_answer(self):
  with self.assertRaises(GameError):self.r.answer(self.a,self.r.token,0)
  self.r.ready(self.a,self.r.token)
  for choice in [True,1.0,'1',None,-1,3]:
   with self.assertRaises(GameError):self.r.answer(self.a,self.r.token,choice)
 def test_host_lobby_capacity_and_late_join(self):
  r=Room();a=r.join('A')
  with self.assertRaises(GameError):r.start(a)
  with self.assertRaises(GameError):r.join('  ')
  keys=[a]+[r.join(str(i))for i in range(11)]
  with self.assertRaises(GameError):r.join('13')
  with self.assertRaises(GameError):r.start(keys[1])
  r.start(a)
  with self.assertRaises(GameError):r.join('new')
 def test_200_six_player_games(self):
  for seed in range(200):
   t=[0.];rng=random.Random(seed);r=Room(clock=lambda:t[0],rng=rng);keys=[r.join(str(i))for i in range(6)];r.start(keys[0]);seen=set()
   while r.phase!='finished':
    if r.phase=='round_end':r.next_round(keys[0])
    if r.phase=='finished':break
    self.assertNotIn(r.question['id'],seen);seen.add(r.question['id']);r.ready(r.turn,r.token)
    t[0]+=rng.uniform(2,50)
    if rng.random()<.5:r.tick()
    else:
     try:r.answer(r.turn,r.token,r.question['correct']if rng.random()<.7 else(r.question['correct']+1)%3)
     except GameError:pass
    if r.phase=='answering':t[0]+=100;r.tick()
    self.assertTrue(all(0<=p['lives']<=3 for p in r.players.values()))
   if r.winner:self.assertEqual(r.active(),[r.winner])
if __name__=='__main__':unittest.main()
