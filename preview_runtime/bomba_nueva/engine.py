"""Local prototype. Proposed fuse/lives rules await owner review. No production import."""
import json,random,secrets,time
from pathlib import Path
class GameError(ValueError):pass
class Room:
 def __init__(self,clock=time.monotonic,rng=None):
  self.clock=clock;self.rng=rng or random.Random();self.players={};self.host=None;self.phase='lobby';self.round=0;self.token=0;self.turn=None;self.question=None;self.feedback='';self.winner=None;self.version=0;self.fuse=None;self.started=None;self.mode='tranquila';self.heat=1;self.heat_text='Temperatura tranquila.';self.message='Borrador: reglas de mecha y vidas propuestas, por confirmar.'
  self.deck=[]
  for level in [1,2,3]:
   group=[q for q in json.loads(Path(__file__).with_name('questions.json').read_text())if q['level']==level];self.rng.shuffle(group);self.deck+=group
  self.used=set()
 def join(self,name,key=None):
  if isinstance(key,str)and key in self.players:return key
  name=' '.join(str(name).split())[:32]
  if not name:raise GameError('Escribí un nombre.')
  if self.phase!='lobby':raise GameError('La partida ya empezó.')
  if len(self.players)>=12:raise GameError('Máximo doce personas.')
  key=secrets.token_urlsafe(24);self.players[key]={'name':name,'lives':3,'score':0}
  if self.host is None:self.host=key
  self.version+=1;return key
 def active(self):return[k for k,p in self.players.items()if p['lives']>0]
 def ishost(self,key):
  if key!=self.host:raise GameError('Solo quien creó la sala puede hacerlo.')
 def start(self,key,mode='tranquila'):
  self.ishost(key)
  if self.phase!='lobby':raise GameError('La partida ya empezó.')
  if len(self.players)<2:raise GameError('Se necesitan dos personas como mínimo.')
  if mode!='tranquila':raise GameError('Elegí una mecha válida.')
  self.mode=mode;self.turn=self.active()[0];self.next_round(key,initial=True)
 def next_round(self,key,initial=False):
  self.ishost(key)
  if not initial and self.phase!='round_end':raise GameError('La ronda todavía no terminó.')
  alive=self.active()
  if len(alive)<=1:self.finish();return
  self.round+=1;self.heat=min(3,(self.round+1)//2)
  ranges={1:(45,75),2:(35,60),3:(25,45)}
  self.fuse=self.rng.uniform(*ranges[self.heat]);self.started=None;self.feedback=''
  self.heat_text={1:'Temperatura tranquila. La mecha empieza suave.',2:'Sube la temperatura. La mecha es más corta que al principio.',3:'Temperatura alta. La mecha está en su tramo más corto; no seguirá acortándose.'}[self.heat]
  self.message=self.heat_text+' La lectura no consume la mecha. Quien tiene la bomba toca Empezar a responder.'
  if self.turn not in alive:self.turn=alive[0]
  self.next_question()
 def next_question(self):
  self.started=None;self.token+=1
  if not self.deck:self.phase='finished';self.question=None;self.winner=None;self.message='Se agotaron las preguntas. Cierre sin ganador; no se repiten preguntas.';self.version+=1;return
  self.question=dict(self.deck.pop(0));order=[0,1,2];self.rng.shuffle(order);self.question['options']=[self.question['options'][i]for i in order];self.question['correct']=order.index(self.question['correct']);self.used.add(self.question['id']);self.phase='reading';self.version+=1
 def require_turn(self,key,token):
  if key!=self.turn:raise GameError('La bomba la tiene otra persona.')
  if type(token)is not int or token!=self.token:raise GameError('Esa pregunta ya cambió.')
 def ready(self,key,token):
  self.require_turn(key,token)
  if self.phase!='reading':raise GameError('Ya empezó tu tiempo de respuesta.')
  self.phase='answering';self.started=self.clock();self.message='La mecha corre solo mientras respondés.';self.version+=1
 def tick(self):
  if self.phase!='answering':return False
  now=self.clock();elapsed=max(0,now-self.started);self.fuse=max(0,self.fuse-elapsed);self.started=now
  if self.fuse<=0:self.explode();return True
  return False
 def answer(self,key,token,choice):
  self.require_turn(key,token)
  if self.phase!='answering':raise GameError('Primero escuchá o leé y tocá Empezar a responder.')
  if type(choice)is not int or choice not in [0,1,2]:raise GameError('Opción no válida.')
  if self.tick():raise GameError('La mecha ya terminó. La respuesta llegó tarde.')
  correct=choice==self.question['correct'];self.started=None
  if correct:
   self.players[key]['score']+=1;self.feedback=self.players[key]['name']+' acertó y pasó la bomba. '+self.question['explanation'];alive=self.active();self.turn=alive[(alive.index(key)+1)%len(alive)]
  else:self.feedback='No era esa. Seguís con la bomba. '+self.question['explanation']
  self.next_question()
 def explode(self):
  key=self.turn;self.players[key]['lives']-=1;self.phase='round_end';self.started=None;self.token+=1;self.question=None;self.feedback=self.players[key]['name']+' se quedó con la bomba y pierde una vida. Explosión solo virtual.';self.message='Ronda terminada. El anfitrión abre la siguiente.';self.version+=1
  alive=self.active()
  if len(alive)<=1:self.finish()
  else:
   order=list(self.players);idx=order.index(key)
   for offset in range(1,len(order)+1):
    candidate=order[(idx+offset)%len(order)]
    if candidate in alive:self.turn=candidate;break
 def finish(self):
  self.phase='finished';self.started=None;alive=self.active();self.winner=alive[0]if len(alive)==1 else None;self.turn=None;self.message=(self.players[self.winner]['name']+' es la última persona con vidas y ganó.')if self.winner else 'Partida terminada sin ganador.';self.version+=1
 def view(self,key):
  # No remaining fuse, random interval, correct answer or deck sent to clients.
  p=self.players[key];q=None
  if self.question:q={k:self.question[k]for k in ['id','category','level','question','options']}
  return dict(phase=self.phase,round=self.round,token=self.token,host=key==self.host,my_turn=key==self.turn,holder=self.players[self.turn]['name']if self.turn else None,me=dict(p),players=[dict(p)for p in self.players.values()],question=q,feedback=self.feedback,message=self.message,winner=self.players[self.winner]['name']if self.winner else None,version=self.version,mode=self.mode,heat=self.heat,heat_text=self.heat_text)
