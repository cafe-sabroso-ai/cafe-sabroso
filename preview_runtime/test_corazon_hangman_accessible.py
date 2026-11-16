import unittest,json,asyncio
from unittest.mock import AsyncMock,patch
import rehearsal_app,webapp as w,hangman_campaign as h,rehearsal_words as rw
class Request:
 async def json(self):return {'mode':'ahorcado','capacity':1}
class AccessibleHangman(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  code=(await w.crear_sala(Request()))['code'];self.room=w.rooms[code];self.p={'id':1,'name':'Rocky','ws':None};self.room.update(players=[self.p],scores={1:0},turn=0,phase='ahorcado',ahorcado={'long_campaign':True,'levels':{},'used':set(),'word':'GATO','hint':'Animal que maúlla','guessed':set(),'wrong':set(),'attempts':3,'clock_started':True});h.run(self.room,1)['queue']=[('GATO','Animal que maúlla')];h.run(self.room,1)['dealt']=1
  self.say=patch.object(w,'narrate',AsyncMock());self.narr=self.say.start()
 async def asyncTearDown(self):w.cancel_timer(self.room);self.say.stop()
 async def test_no_definition_sent_or_spoken(self):
  h.run(self.room,1)['dealt']=0;await h.start_turn(self.room)
  state=w.room_state(self.room)['ahorcado'];self.assertEqual(state['hint'],'');self.assertTrue(state['no_definition']);self.assertNotIn('maúlla',json.dumps(state,ensure_ascii=False));self.assertNotIn('maúlla',self.narr.call_args.args[1])
 async def test_g_a_announces_slots_and_formed_ga(self):
  await w.ah_guess(self.room,self.p,('letter','G'));self.assertIn('casillero 1',self.narr.call_args.args[1]);self.assertNotIn('GATO',self.narr.call_args.args[1])
  await w.ah_guess(self.room,self.p,('letter','A'));text=self.narr.call_args.args[1];self.assertIn('casillero 2',text);self.assertIn('Formaste GA',text);self.assertIn('2 casilleros vacíos',text);self.assertNotIn('GATO',text)
 async def test_repeated_letters_and_long_positions(self):
  self.assertIn('2, 4, 6',w.ah_positions_text('BANANA','A',rw.AHORCADO_SPEAK))
  self.assertIn('14',w.ah_positions_text('DESTORNILLADOR','R',rw.AHORCADO_SPEAK))
 async def test_figure_progress_and_soft_loss(self):
  ah=self.room['ahorcado'];ah['initial_attempts']=3
  ah['attempts']=2;self.assertIn('cabeza',h.miss_figure(self.room));self.assertEqual(ah['figure_parts'],['cabeza'])
  ah['attempts']=1;self.assertIn('último intento',h.miss_figure(self.room));self.assertEqual(len(ah['figure_parts']),4)
  ah['attempts']=0;h.miss_figure(self.room);self.assertEqual(len(ah['figure_parts']),6)
  text=h.loss_line(self.room,'GATO');self.assertIn('La palabra era GATO',text);self.assertNotIn('ahorcamos',text);self.assertIsNotNone(ah['last_figure'])
 async def test_read_board_does_not_reveal_hidden_letters(self):
  self.room['ahorcado']['guessed']={'G','A'}
  with patch.object(w,'say',AsyncMock())as say:
   await h.read_board(self.room,self.p)
  text=say.call_args.args[1];self.assertIn('Casillero 3: vacío',text);self.assertIn('Formaste GA',text);self.assertNotIn('GATO',text);self.assertFalse(self.room['ahorcado']['clock_started'])
 async def test_solved_word_is_named(self):
  await w.ah_guess(self.room,self.p,('word','GATO'));self.assertTrue(any('adivinó GATO' in c.args[1]for c in self.narr.call_args_list))
if __name__=='__main__':unittest.main()
