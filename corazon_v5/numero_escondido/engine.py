import json, random, secrets, time
from pathlib import Path

try:
 from .puzzles import make_puzzle
except ImportError:
 from puzzles import make_puzzle
CATEGORIES={'number':'El número escondido'}
BANK=[]
class GameError(ValueError): pass

class Room:
 def __init__(self, mode='friends', clock=time.monotonic, rng=None, bank=None):
  if mode not in ('solo','friends'): raise GameError('Modo inválido.')
  self.mode=mode; self.clock=clock; self.rng=rng or random.SystemRandom(); self.bank=bank if bank is not None else BANK
  self.players={}; self.host=None; self.phase='lobby'; self.actor=None; self.q=None; self.options=[]; self.correct=None
  self.used=set();self.used_text=set();self.variant=0;self.rejected=[];self.attempts=0;self.hint=''; self.token=0; self.remaining=30.; self.started=None; self.feedback=''; self.result=''; self.winner=None
  self.online=set(); self.version=0; self.turns=0
 def join(self,name,key=None):
  if isinstance(key,str) and key in self.players:
   self.online.add(key); self.version+=1; return key
  if self.phase!='lobby': raise GameError('La partida empezó. Solo pueden volver quienes ya estaban.')
  limit=1 if self.mode=='solo' else 12
  if len(self.players)>=limit: raise GameError('La sala está completa: '+str(limit)+' personas.')
  name=' '.join(str(name).split())[:24]
  if not name: raise GameError('Escribí un nombre o apodo.')
  if any(p['name'].casefold()==name.casefold() for p in self.players.values()): raise GameError('Ese nombre ya está en la sala. Usá otro apodo.')
  key=secrets.token_urlsafe(24); self.players[key]={'name':name,'lives':3,'badges':[],'correct':0,'level':1}; self.online.add(key)
  if self.host is None:self.host=key
  self.version+=1; return key
 def leave(self,key):
  self.online.discard(key)
  if key==self.actor and self.phase=='question':self.pause(key,self.token)
  self.version+=1
 def require(self,key,phase=None,actor=False):
  if key not in self.players:raise GameError('Asiento no válido.')
  if phase and self.phase!=phase:raise GameError('Esa acción ya no está disponible.')
  if actor and self.actor!=key:raise GameError('Esperá tu turno.')
 def start(self,key):
  self.require(key,'lobby')
  if key!=self.host:raise GameError('Solo quien creó la sala puede empezar.')
  if self.mode=='friends' and len(self.players)<2:raise GameError('Esperá al menos una amistad o creá una partida individual.')
  if self.online!=set(self.players):raise GameError('Falta alguien por conectarse. Esperá su regreso.')
  self.actor=next(iter(self.players)); self.phase='spin'; self.feedback='';self.version+=1
 def tick(self):
  if self.phase!='question' or self.started is None:return False
  elapsed=max(0,self.clock()-self.started);self.remaining=max(0,self.remaining-elapsed);self.started=self.clock()
  if self.remaining<=0:self.resolve(False,'Se terminó el tiempo activo.');return True
  return False
 def spin(self,key,token):
  self.require(key,'spin',True)
  if token!=self.token:raise GameError('El giro ya cambió. Actualizá la situación.')
  for _ in range(1000):
   self.variant+=1;self.q=make_puzzle(self.players[key]['level'],self.variant)
   if self.q['question'] not in self.used_text:break
  else:raise GameError('No se pudo preparar un desafío nuevo. Volvé a intentar.')
  self.used_text.add(self.q['question']);self.q['category']='number';self.used.add(self.q['id']);self.attempts=0;self.rejected=[];self.hint=''
  pairs=list(enumerate(self.q['options']));self.rng.shuffle(pairs);self.options=[x[1] for x in pairs];self.correct=next(i for i,x in enumerate(pairs) if x[0]==self.q['correct'])
  self.remaining=30.;self.started=None;self.phase='question';self.token+=1;self.turns+=1;self.feedback='';self.version+=1
 def ready(self,key,token):
  self.require(key,'question',True)
  if token!=self.token:raise GameError('La pregunta cambió.')
  self.tick()
  if self.phase!='question':return
  if self.started is None:self.started=self.clock();self.version+=1
 def pause(self,key,token):
  self.require(key)
  if token!=self.token:raise GameError('La pregunta cambió.')
  if self.actor!=key:raise GameError('Solo puede pausar quien responde.')
  if self.phase!='question':return
  self.tick()
  if self.phase=='question':self.started=None;self.version+=1
 def answer(self,key,token,choice):
  self.require(key,'question',True)
  if token!=self.token:raise GameError('Esa pregunta ya cambió.')
  if type(choice)!=int or not 0<=choice<4:raise GameError('Elegí una de las cuatro opciones.')
  # Read first, then explicitly run the active clock before committing an answer.
  if self.started is None:raise GameError('Leé tranquilo. Después tocá Listo y respondé.')
  self.tick()
  if self.phase!='question':return
  if choice in self.rejected:raise GameError('Esa opción ya se descartó. Elegí otra.')
  if choice!=self.correct and self.attempts==0:
   self.attempts=1;self.rejected.append(choice);self.started=None;self.hint='Primera opción incorrecta. Tenés una segunda oportunidad y conservás los segundos activos restantes. No perdiste vidas. Leé las pistas y tocá Listo para seguir.';self.version+=1;return
  self.resolve(choice==self.correct,'Respuesta correcta.' if choice==self.correct else 'La segunda opción tampoco era.')
 def resolve(self,ok,prefix):
  self.started=None; p=self.players[self.actor]
  if ok:
   p['correct']+=1
   p['level']+=1
  else:p['lives']=max(0,p['lives']-1)
  self.feedback=prefix+' La respuesta es: '+self.options[self.correct]+'. '+self.q['explanation']
  if ok:self.feedback+=' '+('Completaste los quinientos niveles.'if p['level']>500 else 'Pasaste al nivel '+str(p['level'])+'.')
  else:self.feedback+=' Te quedás en el nivel '+str(p['level'])+'. En tu próximo turno recibirás un desafío nuevo de ese nivel.'
  self.hint=''
  self.phase='feedback';self.version+=1
  if p['level']>500:self.finish(self.actor,'completó los quinientos niveles')
  elif self.mode=='solo' and p['lives']==0:self.finish(None,'Te quedaste sin vidas. La partida terminó; podés crear otra')
  elif self.mode=='friends':
   alive=[k for k,v in self.players.items() if v['lives']>0]
   if len(alive)==1:self.finish(alive[0],'es la última persona con vidas')
 def finish(self,winner,reason):
  self.winner=winner;self.phase='finished';self.started=None
  self.result=(self.players[winner]['name']+' '+reason+'.') if winner else reason+'.'
 def next(self,key,token):
  self.require(key,'feedback',True)
  if token!=self.token:raise GameError('El turno cambió.')
  seats=list(self.players);start=seats.index(self.actor)
  for i in range(1,len(seats)+1):
   candidate=seats[(start+i)%len(seats)]
   if self.players[candidate]['lives']>0:self.actor=candidate;break
  self.q=None;self.options=[];self.correct=None;self.phase='spin';self.token+=1;self.feedback='';self.version+=1
 def view(self,key):
  self.require(key);self.tick()
  question=None
  if self.q:
   question={'id':self.q['id'],'category':self.q['category'],'category_label':self.q['tier_label'],'text':self.q['question'],'options':self.options,'level':self.q['level'],'level_label':self.q['tier_label'],'tier':self.q['tier']}
   if self.phase in ('feedback','finished'):question.update(correct=self.correct,explanation=self.q['explanation'],verified_by=self.q['verified_by'])
  return {'mode':self.mode,'phase':self.phase,'token':self.token,'version':self.version,'turn':self.turns,'me':key,'host':key==self.host,'my_turn':key==self.actor,'actor':self.players[self.actor]['name'] if self.actor else None,
   'players':[{'name':p['name'],'lives':p['lives'],'badges':p['badges'],'correct':p['correct'],'level':p['level'],'online':k in self.online,'is_me':k==key}for k,p in self.players.items()],
   'question':question,'remaining':round(self.remaining,1),'running':self.started is not None,'feedback':self.feedback,'result':self.result,'winner':self.players[self.winner]['name'] if self.winner else None,'categories':CATEGORIES,'bank_size':500,'used':len(self.used),'hint':self.hint,'rejected':list(self.rejected),'attempts':self.attempts}
