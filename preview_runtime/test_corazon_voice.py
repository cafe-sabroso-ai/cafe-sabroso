import asyncio,sys,unittest,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import rehearsal_words as rw
sys.modules['app']=rw
import webapp as w
class Extra(unittest.IsolatedAsyncioTestCase):
 def test_gato_parser(self):
  for text in ['gato','Gato.','el gato','es gato','¡gato!']:
   self.assertEqual(rw.ahorcado_parse_guess(text),('word','GATO'))
 def test_farewell(self):
  for form,word in [('femenino','amiga'),('masculino','amigo'),('neutral','Teresa')]:
   lines=[w.farewell_text({'name':'Teresa','address_form':form},i) for i in range(6)]
   self.assertEqual(len(set(lines)),6)
   self.assertTrue(all(word in line for line in lines))
   if form=='neutral':self.assertFalse(any('amiga' in x or 'amigo' in x for x in lines))
  self.assertNotIn('amigo',w.farewell_text({},0))
 async def test_pause_budget_bounded(self):
  loop=asyncio.get_running_loop();room={'game':'ahorcado','voice_clock':{'budget':.16},'voice_hold_until':loop.time()+10}
  start=loop.time();await w.voice_safe_sleep(room,.15);elapsed=loop.time()-start
  self.assertGreaterEqual(elapsed,.29);self.assertLess(elapsed,.6)
  self.assertAlmostEqual(room['voice_clock']['budget'],0)
 async def test_no_pause_when_mic_off(self):
  loop=asyncio.get_running_loop();room={'game':'ahorcado'};start=loop.time();await w.voice_safe_sleep(room,.1)
  self.assertLess(loop.time()-start,.25);self.assertEqual(room['voice_clock']['budget'],15)
if __name__=='__main__':unittest.main()
