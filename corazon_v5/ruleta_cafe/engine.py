import json, random, secrets, time
from pathlib import Path

CATEGORIES = {
 'records': 'Récords', 'curiosities': 'Misterios y curiosidades',
 'myths': 'Mitos y leyendas del mundo', 'jobs': 'Oficios y profesiones',
 'languages': 'Idiomas y saludos del mundo', 'festivals': 'Fiestas y tradiciones del mundo',
 'inventions': 'Inventos y descubrimientos'
}
BANK = json.loads(Path(__file__).with_name('questions.json').read_text()) if Path(__file__).with_name('questions.json').exists() else []
class GameError(ValueError): pass

class Room:
 def __init__(self, mode='friends', clock=time.monotonic, rng=None, bank=None):
  if mode not in ('solo','friends'): raise GameError('Modo inválido.')
  self.mode=mode; self.clock=clock; self.rng=rng or random.SystemRandom(); self.bank=bank if bank is not None else BANK
  self.players={}; self.host=None; self.phase='lobby'; self.actor=None; self.q=None; self.options=[]; self.correct=None
  self.used=set(); self.token=0; self.remaining=30.; self.started=None; self.feedback=''; self.result=''; self.winner=None
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
  key=secrets.token_urlsafe(24); self.players[key]={'name':name,'lives':3,'badges':[],'correct':0}; self.online.add(key)
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
  available=[c for c in CATEGORIES if c not in self.players[key]['badges'] and any(q['category']==c and q['id'] not in self.used for q in self.bank)]
  if not available:
   self.phase='finished';self.result='Se terminó el banco disponible para las insignias pendientes. No hay ganador por agotamiento: pueden crear una partida nueva.';self.started=None;self.version+=1;return
  cat=self.rng.choice(available);pool=[q for q in self.bank if q['category']==cat and q['id'] not in self.used];self.q=self.rng.choice(pool);self.used.add(self.q['id'])
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
  self.resolve(choice==self.correct,'Respuesta correcta.' if choice==self.correct else 'Esa no era la respuesta.')
 def resolve(self,ok,prefix):
  self.started=None; p=self.players[self.actor]
  if ok:
   p['correct']+=1
   if self.q['category'] not in p['badges']:p['badges'].append(self.q['category'])
  else:p['lives']=max(0,p['lives']-1)
  self.feedback=prefix+' La respuesta es: '+self.options[self.correct]+'. '+self.q['explanation']
  self.phase='feedback';self.version+=1
  if len(p['badges'])==7:self.finish(self.actor,'consiguió las siete insignias')
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
   question={'id':self.q['id'],'category':self.q['category'],'category_label':CATEGORIES[self.q['category']],'text':self.q['question'],'options':self.options}
   if self.phase in ('feedback','finished'):question.update(correct=self.correct,explanation=self.q['explanation'],source=self.q['source'],source_label=self.q['source_label'])
  return {'mode':self.mode,'phase':self.phase,'token':self.token,'version':self.version,'turn':self.turns,'me':key,'host':key==self.host,'my_turn':key==self.actor,'actor':self.players[self.actor]['name'] if self.actor else None,
   'players':[{'name':p['name'],'lives':p['lives'],'badges':p['badges'],'correct':p['correct'],'online':k in self.online,'is_me':k==key}for k,p in self.players.items()],
   'question':question,'remaining':round(self.remaining,1),'running':self.started is not None,'feedback':self.feedback,'result':self.result,'winner':self.players[self.winner]['name'] if self.winner else None,'categories':CATEGORIES,'bank_size':len(self.bank),'used':len(self.used)}
