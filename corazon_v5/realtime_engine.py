"""Deterministic simulation driven only by one server clock, not player commands."""
from copy import deepcopy
import math
import coop_engine as common
from house_engine import ROOMS,HEADINGS,door_between
SPEEDS={'lenta':{'walk':3.0,'run':1.8,'contact':6.0,'spawn':5.0},'normal':{'walk':2.0,'run':1.2,'contact':4.0,'spawn':4.0},'rapida':{'walk':1.3,'run':.8,'contact':3.0,'spawn':3.0}}
CUES={'hurt2':'Golpe. Dos vidas.','hurt1':'Golpe. Una vida.','dead':'Sin vidas. Seguís como espectador.','teammate_down':'Un compañero cayó.','runner_near':'Corredor cerca.','walker_near':'Caminante cerca.','boss_near':'Jefe cerca.','spawn_cocina':'Aparece un zombi en cocina.','spawn_patio':'Aparece un zombi en patio.','spawn_boss':'Sale el jefe de la pileta.','door_break':'Puerta rota.','door_hit':'Golpes en la puerta.','kill':'Enemigo vencido.','boss_kill':'Jefe vencido. Sigue la supervivencia.','pause':'Pausa del equipo.','resume':'Seguimos. Los zombis se mueven.','win_none':'Todo el equipo cayó. Fin de la partida.','salon':'Salón.','cocina':'Cocina.','patio':'Patio.','entrada':'Entrada.','closed':'Puerta cerrada.','opened':'Puerta abierta.','barred':'Puerta trabada.','no_target':'No hay enemigo a tu alcance.','blocked':'No hay paso.','wait':'Todavía no.','left':'Girás a la izquierda.','right':'Girás a la derecha.'}

def new_game(speed='lenta'):
 if speed not in SPEEDS:raise ValueError('Velocidad inválida.')
 return {'players':[],'enemies':[],'door':{'state':'cerrada','hp':4,'max':4},'phase':'lobby','paused':False,'pause_reason':'','ready':[],'speed':speed,'time':0.0,'ticks':0,'kills':0,'bosses':0,'boss_due':10,'boss_pending':False,'serial':0,'spawn_at':0.0,'events':[],'seq':0,'pool_effect':None}

def add_player(st,pid,name,cid):
 p=common.player(pid,name,cid);p.update(next_action=0.0,next_hurt=0.0,kills=0,visible=True,audio_mode='cached');st['players'].append(p);return p

def living(st):return common.active(st)
def find(st,pid):return common.find(st,pid)
def emit(st,text,cue=None,priority=1,recipients=None,kind='info',entity=None):
 st['seq']+=1;st['events'].append({'id':st['seq'],'time':round(st['time'],3),'text':text,'cue':cue,'priority':priority,'recipients':recipients,'kind':kind,'entity':entity});st['events']=st['events'][-160:]

def pause(st,reason):
 if st['phase']!='play':return
 if not st['paused']:emit(st,'Pausa del equipo. '+reason,'pause',4)
 st['paused']=True;st['pause_reason']=reason;st['ready']=[]

def start(st):
 if st['phase']!='lobby':raise ValueError('La partida ya empezó.')
 if not 2<=len(st['players'])<=4:raise ValueError('Se necesitan de dos a cuatro personas.')
 if not all(p['connected'] and p['visible'] for p in st['players']):raise ValueError('Falta una persona activa.')
 st['phase']='play';st['spawn_at']=0.0
 emit(st,'Supervivencia en tiempo real. Todos pueden actuar. Los zombis siguen mientras habla la voz.','resume',4)
 spawn_enemy(st,'cocina');st['spawn_at']=st['time']+SPEEDS[st['speed']]['spawn']

def spawn_enemy(st,room='patio',boss=False):
 st['serial']+=1;number=st['serial'];runner=not boss and number%2==1
 e={'id':'rt'+str(number),'name':('Guardián de la pileta '+str(st['bosses']+1)) if boss else 'Zombi '+str(number)+(' corredor' if runner else ' caminante'),'boss':boss,'runner':runner,'room':room,'hp':4 if boss else 1 if runner else 2,'next_move':st['time']+(SPEEDS[st['speed']]['run' if runner else 'walk']*2),'attack_at':None,'target':None,'warned':None}
 st['enemies'].append(e)
 emit(st,e['name']+' aparece en '+ROOMS[room]['name']+'. No ataca al aparecer.','spawn_boss' if boss else 'spawn_'+room,2)
 if room=='patio':st['pool_effect']={'id':st['seq'],'time':st['time'],'kind':'emerge','enemies':[e['id']]}
 return e

def target(st,e):return common.target(st,e)

def tick(st,dt):
 if st['phase']!='play' or st['paused']:return
 # No damage bursts after a stalled process. The driver pauses on a large wall-clock gap.
 dt=min(max(float(dt),0),.25);st['time']+=dt;st['ticks']+=1;t=st['time'];cfg=SPEEDS[st['speed']]
 for e in st['enemies']:
  if e['hp']<=0:continue
  p,steps,blocked=target(st,e)
  if not p:break
  changed=e['target']!=p['id'];e['target']=p['id']
  if not steps:
   if changed or e['attack_at'] is None:
    e['attack_at']=t+cfg['contact'];e['warned']=p['id']
    emit(st,e['name']+' cerca de vos en '+ROOMS[e['room']]['name']+'. Aviso antes del contacto.','boss_near' if e['boss'] else 'runner_near' if e['runner'] else 'walker_near',3,[p['id']],'threat',e['id'])
   if t>=e['attack_at']:
    e['attack_at']=t+cfg['contact']
    if t>=p['next_hurt']:
     p['lives']=max(0,p['lives']-1);p['next_hurt']=t+3.0
     emit(st,p['name']+' recibió un golpe. '+str(p['lives'])+' vidas.','hurt'+str(p['lives']) if p['lives'] else 'dead',5,[p['id']],'hurt')
     if not p['lives']:
      emit(st,p['name']+' quedó sin vidas. El resto sigue.','teammate_down',4,[q['id'] for q in st['players'] if q['id']!=p['id']],'death')
  else:
   e['attack_at']=None;e['warned']=None
   if t+1e-7<e['next_move']:continue
   e['next_move']=t+cfg['run' if e['runner'] else 'walk'];nxt=steps[0]
   if door_between(e['room'],nxt) and st['door']['state'] in ('cerrada','trabada'):
    st['door']['hp']=max(0,st['door']['hp']-(2 if e['runner'] else 1))
    if not st['door']['hp']:st['door']['state']='rota';emit(st,'La puerta se rompió.','door_break',4)
    else:emit(st,'Golpes en la puerta. Resistencia '+str(st['door']['hp'])+'.','door_hit',2)
   else:
    e['room']=nxt
    # Arrival grants full contact warning before damage, even if next tick is due.
    if nxt==p['room']:
     e['attack_at']=t+cfg['contact'];e['warned']=p['id']
     emit(st,e['name']+' entra en tu habitación.','boss_near' if e['boss'] else 'runner_near' if e['runner'] else 'walker_near',3,[p['id']],'threat',e['id'])
 if not living(st):st['phase']='lost';emit(st,'Todo el equipo quedó sin vidas. Fin de supervivencia.','win_none',5);return
 st['enemies']=[e for e in st['enemies'] if e['hp']>0]
 if t+1e-7>=st['spawn_at']:
  has_boss=any(e['boss'] for e in st['enemies'])
  if st['boss_pending']:
   if not st['enemies']:spawn_enemy(st,boss=True);st['boss_pending']=False;st['spawn_at']=t+cfg['spawn']
  elif not has_boss and len(st['enemies'])<2:
   spawn_enemy(st);st['spawn_at']=t+cfg['spawn']
 # Full live cap postpones arrivals rather than stacking hidden threats.

def orientation(st,pid):
 p=find(st,pid)
 text=('PAUSA. '+st['pause_reason']+'. ' if st['paused'] else 'Tiempo real. Sigue mientras escuchás. ' if st['phase']=='play' else 'Sala en preparación. ' if st['phase']=='lobby' else 'Terminó la partida. ')
 text+=p['name']+', '+ROOMS[p['room']]['name']+', mirás al '+p['facing']+', '+str(p['lives'])+' vidas. Salidas: '+'. '.join(d+' a '+ROOMS[r]['name'] for d,r in ROOMS[p['room']]['exits'].items())+'. '
 text+=' '.join(q['name']+' en '+ROOMS[q['room']]['name']+', '+str(q['lives'])+' vidas.' for q in st['players'] if not q['removed'] and q['id']!=pid)
 text+=' Enemigos vencidos '+str(st['kills'])+'. Jefes vencidos '+str(st['bosses'])+'. Puerta '+st['door']['state']+'. '
 for e in st['enemies']:
  if e['hp']<=0:continue
  text+=e['name']+' en '+ROOMS[e['room']]['name']+', resistencia '+str(e['hp'])+'. '
 return text

def action(st,pid,act,target_id=''):
 p=find(st,pid);t=st['time']
 if st['phase']!='play' or st['paused']:raise ValueError('La partida está en pausa o terminó.')
 if p['removed'] or p['lives']<=0:raise ValueError('Estás de espectador. El resto puede seguir.')
 if act not in ('left','right','walk','back','run','open','close','bar','weapon_cuchillo','weapon_disparo','attack_nearest','attack_target'):raise ValueError('Acción inválida.')
 if t+1e-7<p['next_action']:return {'accepted':False,'notice':'Todavía se recupera tu acción anterior.','cue':'wait'}
 p['next_action']=t+.18 # Every command is bounded, including orientation/weapon changes.
 p['last_action']=act;p['path']=[p['room']]
 if act in ('left','right'):
  p['facing']=HEADINGS[(HEADINGS.index(p['facing'])+(-1 if act=='left' else 1))%4]
  emit(st,p['name']+' mira al '+p['facing']+'.',act,1,[pid]);return {'accepted':True}
 if act.startswith('weapon_'):
  p['weapon']=act[7:];emit(st,'Elegiste '+p['weapon']+'. Daño uno, sin compras.',None,0,[pid]);return {'accepted':True}
 accepted=False;cue=None;text='';kind='action'
 if act in ('walk','back','run'):
  heading=HEADINGS[(HEADINGS.index(p['facing'])+2)%4] if act=='back' else p['facing'];nxt=ROOMS[p['room']]['exits'].get(heading)
  if not nxt:text='No hay salida en esa dirección.';cue='blocked'
  elif door_between(p['room'],nxt) and st['door']['state'] in ('cerrada','trabada'):text='Puerta cerrada. Primero abrila.';cue='closed'
  elif act=='run' and (nxt not in p['known'] or any(e['hp']>0 and e['room']==nxt for e in st['enemies'])):text='Para correr necesitás una habitación conocida y libre.';cue='blocked'
  else:
   p['path'].append(nxt);p['room']=nxt
   if nxt not in p['known']:p['known'].append(nxt)
   accepted=True;text=p['name']+' llega a '+ROOMS[nxt]['name']+'.';cue=nxt;kind='move'
 elif act in ('open','close','bar'):
  d=st['door']
  if p['room'] not in ('salon','cocina') or d['state']=='rota':text='No podés usar esa puerta desde acá.';cue='blocked'
  elif act=='open' and d['state']!='abierta':d['state']='abierta';accepted=True;text='Abriste la puerta.';cue='opened';kind='door'
  elif act=='close' and d['state']=='abierta':d.update(state='cerrada',hp=min(4,d['hp']),max=4);accepted=True;text='Cerraste la puerta.';cue='closed';kind='door'
  elif act=='bar' and d['state']=='cerrada':d.update(state='trabada',hp=6,max=6);accepted=True;text='Trabaste la puerta. Resistencia seis.';cue='barred';kind='door'
  else:text='La puerta no permite esa acción.';cue='blocked'
 else:
  candidates=[e for e in st['enemies'] if e['hp']>0 and e['room']==p['room']]
  e=next((e for e in candidates if e['id']==target_id),None) if act=='attack_target' else min(candidates,key=lambda e:(e['attack_at'] if e['attack_at'] is not None else float('inf'),e['hp'],e['id']),default=None)
  if e is None:text='No hay enemigo a tu alcance.';cue='no_target'
  else:
   e['hp']-=1;accepted=True;kind='shot' if p['weapon']=='disparo' else 'hit';text=p['name']+' golpea a '+e['name']+'. Resistencia '+str(e['hp'])+'.'
   if p['room']=='patio':st['pool_effect']={'id':st['seq']+1,'time':t,'kind':'fall','enemy':deepcopy(e),'defeated':not bool(e['hp'])};text+=' Cae a la pileta con chapoteo.'+(' Vuelve a salir.' if e['hp'] else '')
   if e['hp']<=0:
    p['kills']+=1;st['spawn_at']=max(st['spawn_at'],t+SPEEDS[st['speed']]['spawn'])
    if e['boss']:
     st['bosses']+=1;cue='boss_kill';text+=' Jefe vencido. La supervivencia sigue.';st['spawn_at']=t+SPEEDS[st['speed']]['spawn']
    else:
     st['kills']+=1;cue='kill'
     if st['kills']>=st['boss_due']:st['boss_pending']=True;st['boss_due']+=10
    kind='kill' if p['room']!='patio' else 'splash'
   elif p['room']=='patio':kind='splash'
 if accepted:p['next_action']=t+(.45 if act=='run' else .8 if act in ('walk','back') else 1.0)
 emit(st,text,cue,2 if cue in ('kill','boss_kill') else 1,[pid],kind)
 # Teammates in the same room get a nonverbal event, not speech for every ally attack.
 if accepted and kind in ('hit','shot','splash','kill','door'):
  emit(st,text,None,0,[q['id'] for q in st['players'] if q['id']!=pid and q['room']==p['room']],kind)
 return {'accepted':accepted,'notice':text}
