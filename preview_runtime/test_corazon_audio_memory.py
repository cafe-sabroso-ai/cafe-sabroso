import asyncio,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
import rehearsal_app,webapp as w,rehearsal_words as rw

class AudioMemory(unittest.IsolatedAsyncioTestCase):
 async def test_six_identical_readings_build_once(self):
  async def encode(data):await asyncio.sleep(.01);return b'converted'
  with patch.object(rw,'synthesize',AsyncMock(return_value=b'audio'))as synth,patch.object(w,'ogg_to_mp3',AsyncMock(side_effect=encode))as conv:
   result=await asyncio.gather(*(w.bounded_voice_mp3('Mismo caso privado','voice')for _ in range(6)))
  self.assertEqual(result,[b'converted']*6);self.assertEqual(synth.await_count,1);self.assertEqual(conv.await_count,1)
 async def test_different_encodes_are_serial(self):
  active=peak=0
  class Proc:
   returncode=None
   def __init__(self,path):self.path=path
   async def communicate(self):
    nonlocal active,peak
    active+=1;peak=max(peak,active);await asyncio.sleep(.01);Path(self.path).write_bytes(b'mp3');active-=1;self.returncode=0;return b'',b''
  async def spawn(*args,**kwargs):return Proc(args[-1])
  with patch.object(asyncio,'create_subprocess_exec',side_effect=spawn):
   result=await asyncio.gather(*(w.ogg_to_mp3(bytes([i]))for i in range(6)))
  self.assertEqual(peak,1);self.assertEqual(result,[b'mp3']*6)
 async def test_cancel_kills_and_reaps_encoder(self):
  started=asyncio.Event()
  class Proc:
   returncode=None;killed=False;calls=0
   async def communicate(self):
    self.calls+=1
    if self.killed:self.returncode=-9;return b'',b''
    started.set();await asyncio.sleep(60)
   def kill(self):self.killed=True
  proc=Proc()
  with patch.object(asyncio,'create_subprocess_exec',AsyncMock(return_value=proc)):
   task=asyncio.create_task(w.ogg_to_mp3(b'audio'));await started.wait();task.cancel()
   with self.assertRaises(asyncio.CancelledError):await task
  self.assertTrue(proc.killed);self.assertEqual(proc.calls,2)
 def test_cache_is_bounded(self):
  old=w.audio_cache.copy();w.audio_cache.clear()
  try:
   for i in range(40):w.cache_audio(bytes([i])*1024*1024)
   self.assertLessEqual(sum(len(v[0])for v in w.audio_cache.values()),32*1024*1024)
  finally:w.audio_cache.clear();w.audio_cache.update(old)
if __name__=='__main__':unittest.main()
