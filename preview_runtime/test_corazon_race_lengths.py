import asyncio,unittest,random,json
from unittest.mock import AsyncMock,patch
from fastapi import HTTPException
import rehearsal_app,webapp as w,mystery_race as m
from test_corazon_campaigns import Sock
class Request:
 def __init__(self,target,mode='misterio'):self.target=target;self.mode=mode
 async def json(self):return {'mode':self.mode,'capacity':2,'mystery_target':self.target}
class Lengths(unittest.IsolatedAsyncioTestCase):
 async def make(self,n):
  code=(await w.crear_sala(Request(n)))['code'];room=w.rooms[code];room['players']=[{'id':1,'name':'A','ws':Sock()},{'id':2,'name':'B','ws':Sock()}];return room
 async def test_valid_and_invalid_creation(self):
  for n in [10,25,50]:self.assertEqual((await self.make(n))['mystery_target'],n)
  for n in [0,1,9,11,24,26,49,51,True,10.0,'10',None,{},[]]:
   with self.subTest(n=n),self.assertRaises(HTTPException):await self.make(n)
 async def test_all_lengths_fair_and_immutable_after_start(self):
  with patch.object(w,'say',AsyncMock()),patch.object(w,'narrate',AsyncMock()):
   for n in [10,25,50]:
    room=await self.make(n);await m.start(room);room['mystery_target']=10 if n!=10 else 50
    self.assertEqual(m.target(room),n);self.assertEqual(len(room['misterio']['order']),n)
    self.assertEqual(len(set(room['misterio']['order'])),n)
    for cat in m.CATEGORIES:self.assertEqual(sum(m.BY_ID[x]['category']==cat for x in room['misterio']['order']),n//5)
    for p in room['players']:self.assertEqual(m.view(room,p['id'])['total'],n)
    for x in room['misterio']['runs'].values():m.cancel(x)
 async def test_finish_exactly_each_length_not_early_and_no_cross_distance_result(self):
  with patch.object(w,'say',AsyncMock()),patch.object(w,'narrate',AsyncMock())as narr:
   keys=[]
   for n in [10,25,50]:
    room=await self.make(n);await m.start(room);p=room['players'][0]
    for i in range(n):
     run=m.getrun(room,1)
     self.assertEqual(room['phase'],'misterio');await m.action(room,p,'spin',run['token']);c=m.case_for(room,run);await m.ready(room,1,run['token']);await m.guess(room,p,c['accepted'][-1],run['token'])
     self.assertEqual(len(run['solved']),i+1);self.assertEqual(m.getrun(room,2)['index'],0)
    self.assertEqual(room['phase'],'gameover');self.assertEqual(room['misterio']['winner'],1);self.assertIsNone(m.case_for(room,run));self.assertEqual(m.view(room,1)['position'],n)
    text=narr.call_args.args[1];self.assertIn(f'{n} casos',text);keys.append(m.public(room)['result_class'])
    # A later accepted answer cannot overwrite the winner or increment any score.
    await m.guess(room,p,'lo que sea',run['token']);self.assertEqual(room['scores'][1],n)
   self.assertEqual(len(set(keys)),3)
 async def test_simultaneous_last_answer_one_winner(self):
  with patch.object(w,'say',AsyncMock()),patch.object(w,'narrate',AsyncMock())as narr:
   room=await self.make(10);await m.start(room)
   for p in room['players']:
    r=m.getrun(room,p['id']);r['index']=9;r['solved']=room['misterio']['order'][:9];r['needs_spin']=False;r['awaiting_ack']=True;await m.ready(room,p['id'],r['token'])
   c=m.case_for(room,m.getrun(room,1));await asyncio.gather(*(m.guess(room,p,c['accepted'][-1],m.getrun(room,p['id'])['token'])for p in room['players']))
   self.assertIn(room['misterio']['winner'],[1,2]);self.assertEqual(narr.await_count,1)
if __name__=='__main__':unittest.main()
