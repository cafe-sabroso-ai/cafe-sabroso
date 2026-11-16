"""Private, per-person case campaign for the local rehearsal only."""
import asyncio,json,random,re,time,unicodedata
from pathlib import Path
BANK=json.loads(Path(__file__).with_name('misterio_original.json').read_text())
BY_ID={c['id']:c for c in BANK}
CATEGORIES=list(dict.fromkeys(c['category'] for c in BANK))
W=None

def norm(text):
 text=''.join(c for c in unicodedata.normalize('NFD',str(text).lower()) if unicodedata.category(c)!='Mn')
 return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]',' ',text)).strip()

def judge(case,text):
 """Conservative explicit aliases, never substring or model answers."""
 t=norm(text)
 for prefix in ['mi respuesta es ','la respuesta es ','creo que es ','pienso que es ','es ']:
  if t.startswith(prefix):t=t[len(prefix):];break
 accepted={norm(x)for x in case['accepted']}
 if t in accepted:return 'acierto'
 if not t:return 'vacia'
 if t in {norm(x)for x in case.get('rejected',[])}:return 'lejos'
 # Negations and multiple possibilities are not stripped or accepted.
 if any(norm(k) in t.split() for k in case['near']):return 'cerca'
 return 'sin_confirmar'

def order(rng=None):
 rng=rng or random.SystemRandom();pools={cat:[c['id']for c in BANK if c['category']==cat]for cat in CATEGORIES}
 for pool in pools.values():rng.shuffle(pool)
 result=[]
 for _ in range(10):
  cats=CATEGORIES.copy();rng.shuffle(cats)
  result.extend(pools[cat].pop()for cat in cats)
 return result

def active_players(room):return [p for p in room['players']if not p.get('gone')and not p.get('spectator')]
def getrun(room,pid):return room.get('misterio',{}).get('runs',{}).get(pid)
def case_for(room,run):return BY_ID[room['misterio']['order'][run['index']]] if run['index']<len(BANK) else None

def cancel(run):
 task=run.pop('task',None)
 if task and task is not asyncio.current_task():task.cancel()
 run['started']=None

def public(room):
 st=room.get('misterio',{})
 return {'campaign':True,'total':len(BANK),'categories':CATEGORIES,'progress':[{'id':p['id'],'name':p['name'],'solved':len(st.get('runs',{}).get(p['id'],{}).get('solved',[]))}for p in active_players(room)],'winner':st.get('winner')}

def view(room,pid):
 data=public(room);run=getrun(room,pid)
 if run is None:return dict(data,watching=True)
 c=case_for(room,run)
 return dict(data,title=c['title']if c else 'Recorrido completo',case=c['story']if c else '',category=c['category']if c else '',position=run['index']+1 if c else len(BANK),completed=len(run['solved']),lives=run['lives'],ready=run['started']is not None,remaining=round(run['remaining']),token=run['token'],feedback=run.get('feedback',''),hint=run.get('hint',''),finished=c is None,ambience='suspenso')

async def state(room,p=None):
 if p:await W.tell(p,W.room_state(room))
 else:await W.broadcast(room,W.room_state(room))

async def speak(room,p,text):
 # Private voice does not hold the shared room narration lock.
 await W.say(room,text,to=p)

async def read_case(room,p,extra=''):
 run=getrun(room,p['id'])
 if not run or room['phase']!='misterio':return
 cancel(run);run['token']+=1;run['awaiting_ack']=True
 if run['remaining']<=0:run['remaining']=150.
 c=case_for(room,run)
 if not c:return
 token=run['token'];await state(room,p)
 text=(extra+' '+f"Ruleta de apartados: {c['category']}. Tu caso {run['index']+1} de {len(BANK)}: {c['title']}. {c['story']} "
       'Tu respuesta y tus pistas son privadas. El reloj empieza al terminar la lectura o al tocar Empezar a responder.').strip()
 await W.say(room,text,to=p,grid_ack={'game':'misterio','token':token,'turn':p['id']})

async def start(room):
 for run in room.get('misterio',{}).get('runs',{}).values():cancel(run)
 W.cancel_timer(room);room['phase']='misterio';room['team_count']=0
 room['misterio']={'campaign':True,'order':order(),'runs':{},'winner':None}
 for p in active_players(room):
  p['out']=False;room['scores'][p['id']]=0
  room['misterio']['runs'][p['id']]={'index':0,'solved':[],'lives':3,'remaining':150.,'started':None,'token':0,'feedback':'','hint':'','hint_count':0,'lock':asyncio.Lock()}
 await state(room)
 await asyncio.gather(*(read_case(room,p,'Carrera individual. Todos reciben el mismo orden sorteado, cada uno avanza a su ritmo. Gana quien resuelva los cincuenta casos primero. No compartas soluciones en el chat general.')for p in active_players(room)))

async def ready(room,pid,token):
 run=getrun(room,pid)
 if not run or token!=run['token']or room['phase']!='misterio'or not run.get('awaiting_ack')or run['started']is not None:return False
 run['awaiting_ack']=False;run['started']=time.monotonic();run['voice_budget']=15.
 p=next((p for p in room['players']if p['id']==pid),None)
 if not p:return False
 await state(room,p)
 run['task']=asyncio.create_task(deadline(room,p,run,token));return True

async def deadline(room,p,run,token):
 try:
  before=time.monotonic();last_second=None
  while run['remaining']>0 and room['phase']=='misterio'and token==run['token']:
   await asyncio.sleep(.1);now=time.monotonic();delta=now-before;before=now
   paused=min(delta,run['voice_budget'])if run.get('voice_until',0)>now-delta else 0
   run['voice_budget']-=paused;run['remaining']-=delta-paused
   second=max(0,int(run['remaining']))
   if second!=last_second:
    last_second=second;await W.tell(p,{'event':'mst-clock','token':token,'seconds':second})
   if p.get('gone')or p.get('ws')is None:
    suspend(room,p);return
  if token!=run['token']or room['phase']!='misterio':return
  run['started']=None;run['awaiting_ack']=False;run['feedback']='Terminó tu tiempo de este intento. El caso no cambia ni se revela. Tocá Repetir o Pedir pista y volvé a intentar.'
  await state(room,p);await speak(room,p,run['feedback'])
 except asyncio.CancelledError:pass

def suspend(room,p):
 run=getrun(room,p['id'])
 if run:
  cancel(run);run['token']+=1;run['awaiting_ack']=True
  run['feedback']='Conexión interrumpida. Conservás tu caso y progreso; volvé a escuchar antes de responder.'

async def resume(room,p):
 run=getrun(room,p['id'])
 if run and room['phase']=='misterio':
  run['feedback']='Conexión recuperada. Conservás tu caso y progreso.'
  await read_case(room,p,'Volviste al mismo caso y conservás tu progreso.')

def mic(room,pid,active):
 run=getrun(room,pid)
 if run:run['voice_until']=time.monotonic()+(12 if active else 1.5)

async def action(room,p,kind,token=None):
 run=getrun(room,p['id'])
 if not run or p.get('spectator')or room['phase']!='misterio':return
 if token is not None and token!=run['token']:return
 if kind=='ready':return await ready(room,p['id'],run['token'])
 if run['lock'].locked():return
 async with run['lock']:
  if kind=='progress':
   text=progress_text(room)
   # This player's clock pauses for the private scoreboard reading.
   cancel(run);run['token']+=1;run['awaiting_ack']=True
   await state(room,p)
   await W.say(room,text,to=p,grid_ack={'game':'misterio','token':run['token'],'turn':p['id']});return
  if kind=='hint':
   c=case_for(room,run);i=min(run['hint_count'],len(c['hints'])-1);run['hint']=c['hints'][i];run['hint_count']+=1
   await read_case(room,p,'Pista privada: '+run['hint']);return
  if kind in ('read','retry'):
   if run['remaining']<=0:run['remaining']=150.
   await read_case(room,p)


def progress_text(room):
 rows=public(room)['progress']
 if not rows:return 'No hay personas jugando.'
 high=max(r['solved']for r in rows);leaders=[r['name']for r in rows if r['solved']==high]
 line='Marcador: '+'. '.join(f"{r['name']}: {r['solved']} de {len(BANK)} casos"for r in rows)+'. '
 if high==0:return line+'Todavía nadie resolvió el primer caso.'
 return line+('Van empatados adelante: 'if len(leaders)>1 else 'Va adelante: ')+', '.join(leaders)+'. No se comparten respuestas ni pistas.'

def leader_text(room):
 rows=public(room)['progress']
 if not rows:return ''
 high=max(r['solved']for r in rows);names=[r['name']for r in rows if r['solved']==high]
 names_text=', '.join(names[:3])+(' y otras personas'if len(names)>3 else '')
 return ('Van adelante empatados: 'if len(names)>1 else 'Va adelante: ')+names_text+f', con {high} de {len(BANK)} casos. Solo compartimos progreso.'

async def guess(room,p,text,token=None):
 run=getrun(room,p['id'])
 if not run or room['phase']!='misterio'or p.get('gone')or p.get('spectator')or(token is not None and token!=run['token']):return
 if run['lock'].locked():return
 async with run['lock']:
  if run['started']is None:
   await speak(room,p,'Primero escuchá tu caso y tocá Empezar a responder.');return
  c=case_for(room,run);verdict=judge(c,str(text)[:1000]);cancel(run)
  run['token']+=1;run['awaiting_ack']=True
  if verdict!='acierto':
   run['lives']=max(0,run['lives']-1) if verdict=='lejos' else run['lives']
   run['feedback']=('Reconocí parte del tema, pero no confirmé la solución.'if verdict=='cerca'else 'No confirmé esa respuesta con las formas revisadas del ensayo.')+' Tu teoría sigue siendo privada.'
   if run['lives']==0:
    run['lives']=3;run['remaining']=150.;run['feedback']+=' Tenés tres intentos nuevos para el mismo caso. No se suma como resuelto.'
   run['feedback']+=' Podés pedir una pista o revisar cómo la dijiste. Si la frase no está confirmada, no se descuenta un intento.'
   await state(room,p)
   await W.say(room,run['feedback'],to=p,grid_ack={'game':'misterio','token':run['token'],'turn':p['id']});return
  # No awaits until the win claim: simultaneous finish cannot crown twice.
  if room['misterio'].get('winner')is not None:return
  run['solved'].append(c['id']);run['index']+=1;run['hint_count']=0;run['hint']='';run['feedback']='Caso anterior resuelto. El caso que se muestra ahora sigue pendiente.';run['remaining']=150.
  room['scores'][p['id']]=len(run['solved'])
  if run['index']==len(BANK):
   room['misterio']['winner']=p['id'];room['phase']='gameover'
   for other in room['misterio']['runs'].values():cancel(other)
   await state(room)
   await W.narrate(room,f"¡{p['name']} resolvió los cincuenta casos y ganó la carrera! No se revelan las soluciones de los demás.")
   return
  # Only progress, not current title, category, guesses or solution is public.
  await state(room)
  await W.broadcast(room,{'event':'mst-progress','text':f"{p['name']} resolvió {len(run['solved'])} de {len(BANK)} casos. "+leader_text(room)})
  await read_case(room,p,'¡Acertaste! Pasás a tu siguiente caso.')


def install(w):
 global W
 if getattr(w,'_mystery_race_installed',False):return
 W=w;w._mystery_race_installed=True
 oldstate=w.room_state;oldprivate=w.private_player_state
 def roomstate(room):
  if room.get('game')!='misterio'or not room.get('misterio',{}).get('campaign'):return oldstate(room)
  # The base projection expects a legacy case only when present.
  state=oldstate(room);state['turn']=None;state['turn_name']='Cada persona a su ritmo';state['misterio']=public(room)
  state['_mystery_views']={str(p['id']):view(room,p['id'])for p in room['players']}
  return state
 def private(message,pid):
  state=oldprivate(message,pid);views=state.pop('_mystery_views',{})
  if views:state['misterio']=views.get(str(pid),{'campaign':True,'watching':True})
  return state
 w.room_state=roomstate;w.private_player_state=private
 w.mst_start_campaign=start;w.mst_campaign_action=action;w.mst_campaign_ready=ready;w.mst_campaign_mic=mic
 oldguess=w.mst_guess
 async def mst_guess(room,p,text,token=None):
  if room.get('misterio',{}).get('campaign'):return await guess(room,p,text,token)
  return await oldguess(room,p,text)
 w.mst_guess=mst_guess
