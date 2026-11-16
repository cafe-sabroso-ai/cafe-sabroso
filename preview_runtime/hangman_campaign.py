"""One hundred unique word challenges per person; no bank reset on misses."""
import asyncio,random
W=None

def bank():
 import rehearsal_words as r
 return list(r.AHORCADO_BANK)

def run(room,pid):return room['ahorcado'].setdefault('campaign_runs',{}).setdefault(pid,{'queue':None,'dealt':0,'done':0,'correct':0,'saved':None,'finished':False})

def make_queue():
 words=sorted(bank(),key=lambda x:(len(x[0]),x[0]));result=[]
 for i in range(0,len(words),20):
  chunk=words[i:i+20];random.shuffle(chunk);result.extend(chunk)
 return result

async def finish_person(room,p):
 st=run(room,p['id']);st['finished']=True;p['out']=True
 await W.narrate(room,f"{p['name']} terminó sus cien desafíos con {st['correct']} aciertos. No se repitieron palabras ni se contó un error como acierto.")
 alive=[q for q in room['players']if not q.get('gone')and not q.get('out')and not q.get('spectator')]
 if not alive:
  room['phase']='gameover';room['ahorcado']['word']=None
  await W.broadcast(room,W.room_state(room));await W.narrate(room,'Terminó el recorrido de cien desafíos. El marcador muestra aciertos, no palabras simplemente vistas. No se reinicia solo.');return
 await start_turn(room)

async def start_turn(room):
 W.cancel_timer(room);p=W.current_player(room)
 if not p:return
 ah=room['ahorcado'];st=run(room,p['id']);room['voice_hold_until']=0
 if st['queue']is None:st['queue']=make_queue()
 if st['saved']:
  ah.update({k:set(v)if isinstance(v,set)else v for k,v in st['saved'].items()})
 else:
  if st['dealt']>=len(st['queue']):return await finish_person(room,p)
  word,hint=st['queue'][st['dealt']];st['dealt']+=1
  _,_,attempts,*_=W.ah_helpers()
  ah.update(word=word,hint=hint,guessed=set(),wrong=set(),attempts=attempts(word))
 room['phase']='ahorcado';ah['reading_token']=ah.get('reading_token',0)+1;ah['clock_started']=False;ah['levels'][p['id']]=st['done']+1
 await W.broadcast(room,W.room_state(room))
 await W.narrate(room,f"Turno de {p['name']}. Desafío {st['done']+1} de cien; {st['correct']} aciertos. Tramo {(st['dealt']-1)//20+1} de cinco, por longitud, no dificultad medida. La palabra tiene {len(ah['word'])} letras. Pista: {ah['hint']} Tenés {ah['attempts']} intentos. Conservás tu palabra si pasa el turno. El reloj empieza después de esta lectura o al tocar Empezar mi turno.",grid_ack={'game':'ahorcado','token':ah['reading_token'],'turn':p['id']})
 await W.tell(p,{'event':'your_turn','kind':'ahorcado'})
 # Clock starts only after the playback acknowledgement or explicit button.

async def passed(room,reason):
 W.cancel_timer(room);p=W.current_player(room)
 if not p:return
 ah=room['ahorcado'];st=run(room,p['id'])
 if ah['attempts']>0:st['saved']={k:set(ah[k])if isinstance(ah[k],set)else ah[k]for k in ('word','hint','guessed','wrong','attempts')}
 else:st['saved']=None;st['done']+=1
 await W.narrate(room,reason)
 if st['done']>=len(bank()):return await finish_person(room,p)
 room['turn']+=1;await start_turn(room)

async def solved(room,p):
 W.cancel_timer(room);st=run(room,p['id']);st['correct']+=1;st['done']+=1;st['saved']=None
 room['scores'][p['id']]=st['correct']
 await W.narrate(room,f"¡{p['name']} adivinó! Lleva {st['correct']} aciertos en {st['done']} desafíos terminados de cien.")
 if st['done']>=len(bank()):return await finish_person(room,p)
 room['turn']+=1;await start_turn(room)

def install(w):
 global W
 if getattr(w,'_hangman_campaign_installed',False):return
 W=w;w._hangman_campaign_installed=True;w.ah_campaign_ready=ready
 for name,new in [('ah_start_turn',start_turn),('ah_pass',passed),('ah_solved',solved)]:
  old=getattr(w,name)
  def wrapper(old=old,new=new):
   async def call(room,*args,**kwargs):
    if room.get('ahorcado',{}).get('long_campaign'):return await new(room,*args,**kwargs)
    return await old(room,*args,**kwargs)
   return call
  setattr(w,name,wrapper())
 oldguess=w.ah_guess
 async def guarded_guess(room,p,guess):
  if room.get('ahorcado',{}).get('long_campaign')and not room['ahorcado'].get('clock_started'):return
  return await oldguess(room,p,guess)
 w.ah_guess=guarded_guess
 oldstate=w.room_state
 def roomstate(room):
  state=oldstate(room)
  if room.get('game')=='ahorcado'and room.get('ahorcado',{}).get('long_campaign'):
   ah=state.get('ahorcado')
   if ah:
    ah['clock_started']=room['ahorcado'].get('clock_started',False);ah['reading_token']=room['ahorcado'].get('reading_token');ah['campaign']=True;ah['total']=len(bank());ah['progress']={str(pid):{k:st[k]for k in ('dealt','done','correct','finished')}for pid,st in room['ahorcado'].get('campaign_runs',{}).items()}
  return state
 w.room_state=roomstate

async def ready(room,pid,token):
 if room['phase']!='ahorcado'or not room.get('ahorcado',{}).get('long_campaign'):return
 p=W.current_player(room);ah=room['ahorcado']
 if not p or p['id']!=pid or token!=ah.get('reading_token')or ah.get('clock_started'):return
 ah['clock_started']=True
 await W.broadcast(room,W.room_state(room))
 room['timer_task']=W.narrated_timer(room,W.turn_clock(room,pid))
