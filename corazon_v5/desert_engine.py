"""Deterministic simulation driven only by one server clock, not player commands."""
from copy import deepcopy
import math
import coop_engine as common
from house_engine import HEADINGS,door_between
from collections import deque
ROOMS={'entrada':{'name':'Campamento','exits':{'norte':'salon','este':'patio'}},'salon':{'name':'Ruinas','exits':{'sur':'entrada','este':'cocina'}},'cocina':{'name':'Taller de arena','exits':{'oeste':'salon','sur':'patio'}},'patio':{'name':'Dunas','exits':{'norte':'cocina','oeste':'entrada'}}}
WEAPONS={'cuchillo':{'name':'Cuchillo arcade','price':0,'damage':1,'cooldown':1},'disparo':{'name':'Disparo arcade','price':0,'damage':1,'cooldown':1},'hielo':{'name':'Pulso congelante','price':30,'damage':0,'cooldown':4},'llamas':{'name':'Lanzallamas ficticio','price':40,'damage':1,'cooldown':2.5},'bazuca':{'name':'Bazuca de caricatura','price':60,'damage':3,'cooldown':4},'iman':{'name':'Pulso de atracción','price':35,'damage':1,'cooldown':3}}

WEAPONS.update({'sable':{'name':'Sable de arena','price':25,'damage':2,'cooldown':1.6},'mazo':{'name':'Mazo sísmico ficticio','price':70,'damage':4,'cooldown':4},'rayo':{'name':'Rayo de tormenta ficticio','price':50,'damage':1,'cooldown':4}})

SPEEDS={'lenta':{'walk':3.0,'run':1.8,'contact':6.0,'spawn':5.0},'normal':{'walk':2.0,'run':1.2,'contact':4.0,'spawn':4.0},'rapida':{'walk':1.3,'run':.8,'contact':3.0,'spawn':3.0}}
CUES={'hurt2':'Golpe. Dos vidas.','hurt1':'Golpe. Una vida.','dead':'Sin vidas. Seguís como espectador.','teammate_down':'Un compañero cayó.','runner_near':'Corredor cerca.','walker_near':'Caminante cerca.','boss_near':'Jefe cerca.','spawn_cocina':'Aparece un zombi en cocina.','spawn_patio':'Aparece un zombi en patio.','spawn_boss':'Sale el jefe de la pileta.','door_break':'Puerta rota.','door_hit':'Golpes en la puerta.','kill':'Enemigo vencido.','boss_kill':'Jefe vencido. Sigue la supervivencia.','pause':'Pausa del equipo.','resume':'Seguimos. Los zombis se mueven.','win_none':'Todo el equipo cayó. Fin de la partida.','salon':'Salón.','cocina':'Cocina.','patio':'Patio.','entrada':'Entrada.','closed':'Puerta cerrada.','opened':'Puerta abierta.','barred':'Puerta trabada.','no_target':'No hay enemigo a tu alcance.','blocked':'No hay paso.','wait':'Todavía no.','left':'Girás a la izquierda.','right':'Girás a la derecha.'}

CUES.update({'level_end':'Nivel terminado. El equipo puede descansar y revisar la tienda.','next_level':'Nueva ronda. Continúa el combate.','victory':'Arena completada. Victoria del equipo.','taunt':'Ja, ja, ja. La arena ganó esta vez. Dale, intentá de nuevo.','enemy_open':'Un enemigo abrió la puerta.','spawn_mummy':'Una momia sale de la arena. Hay veloces y guardianas resistentes.','mummy_near':'Momia cerca. Revisá su resistencia en el objetivo.','spawn_cocina':'Aparece un zombi en el taller.','spawn_patio':'Un zombi sale de la arena.','spawn_boss':'Llega el Guardián de las dunas.','salon':'Ruinas.','cocina':'Taller de arena.','patio':'Dunas.','entrada':'Campamento.','frozen':'Enemigo congelado un segundo.','flame':'Fuego de fantasía en el enemigo.','blast':'Impacto de bazuca de caricatura.','pull':'El pulso atrae y retrasa al enemigo.','purchase':'Arma comprada con puntos virtuales.','equip':'Arma equipada.','burn_kill':'El fuego venció al enemigo.'})

CUES.update({'cheer_tomas':'¡Bien ahí! Soy Tomás. Pasamos juntos a la siguiente ronda.','cheer_mateo':'¡Vamos todavía! Mateo listo para la siguiente ronda.','cheer_elena':'¡Eso es! Soy Elena. Seguimos juntos.','cheer_valentina':'¡Lo logramos! Valentina lista para seguir.'})

CUES.update({'timeout':'Se terminó el tiempo. El equipo pierde esta partida. Dale, intentá de nuevo.','time30':'Atención. Quedan treinta segundos de ronda.','time10':'Últimos diez segundos de ronda.'})

CUES.update({'sable':'Golpe de sable de arena. Dos de daño.','mazo':'Impacto de mazo sísmico. Cuatro de daño.','rayo':'Rayo de tormenta. Un daño y dos segundos de aturdimiento.'})

ROUTE_HINT='Bifurcación en Campamento. Norte: Ruinas, después puerta al Taller, sin tormenta adicional. Este: atajo directo a Dunas, quince puntos una vez por ronda. Si seguís en Dunas doce segundos de juego después del atajo, la tormenta te quita una vida. Salí al norte al Taller o volvé al oeste. Los enemigos siguen en ambos caminos.'
CUES.update({'route_info':ROUTE_HINT,'route_calm':'Camino de las Ruinas. Sin tormenta adicional. Seguí al este y abrí la puerta para llegar al Taller. Los enemigos siguen.','route_risk':'Atajo. Tormenta en doce segundos de juego. Salí de Dunas al norte o al oeste para no perder una vida.','storm_hit':'La tormenta te alcanzó. Perdiste una vida.','storm_safe':'Saliste de Dunas. Tormenta evitada.','storm_clear':'La tormenta terminó.','view_first':'Vista de primera persona simulada. Arma abajo, amenaza de tu zona al frente. No hay puntería ni movimiento libre.'})

def pace(st):
 factor=(1,.85,.7)[st['level']-1]
 return {k:v*factor for k,v in SPEEDS[st['speed']].items()}
def new_game(speed='lenta',timed=False):
 if speed not in SPEEDS:raise ValueError('Velocidad inválida.')
 return {'timed':bool(timed),'level_started':0.0,'limit':180,'time_warned':[],'players':[],'enemies':[],'door':{'state':'cerrada','hp':4,'max':4},'phase':'lobby','paused':False,'pause_reason':'','ready':[],'speed':speed,'time':0.0,'ticks':0,'kills':0,'bosses':0,'boss_due':6,'level':1,'level_kills':0,'goal':6,'max_levels':3,'boss_pending':False,'serial':0,'spawn_at':0.0,'events':[],'seq':0,'pool_effect':None}

def add_player(st,pid,name,cid):
 p=common.player(pid,name,cid);p.update(points=0,owned=['cuchillo','disparo'],weapon_ready={},next_action=0.0,next_hurt=0.0,kills=0,visible=True,audio_mode='cached',route_reward_level=0,storm_at=None);st['players'].append(p);return p

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
 st['phase']='play';st['spawn_at']=0.0;st['level_started']=st['time']
 emit(st,'Supervivencia en tiempo real. Todos pueden actuar. Los zombis siguen mientras habla la voz.','resume',4)
 spawn_enemy(st,'cocina');st['spawn_at']=st['time']+pace(st)['spawn']

def spawn_enemy(st,room='patio',boss=False):
 st['serial']+=1;number=st['serial'];mummy=(not boss and number%3==0) or (boss and st['bosses']%2==1);runner=not boss and (number%2==1 or mummy and number%6==0)
 e={'id':'rt'+str(number),'type':'momia' if mummy else 'zombi','can_open':number%2==0,'name':(('Custodia de los Vientos ' if mummy else 'Guardián de las dunas ')+str(st['bosses']+1)) if boss else (('Momia veloz ' if runner else 'Momia guardiana ') if mummy else 'Zombi ')+str(number)+(' corredor' if runner else ' caminante'),'boss':boss,'runner':runner,'room':room,'hp':4+st['level']-1 if boss else (2 if runner else 4) if mummy else 1 if runner else 2,'next_move':st['time']+(pace(st)['run' if runner else 'walk']*2),'attack_at':None,'target':None,'warned':None,'frozen_until':0.0,'burn_at':None,'burn_owner':None}
 st['enemies'].append(e)
 emit(st,e['name']+' aparece en '+ROOMS[room]['name']+'. No ataca al aparecer.','spawn_boss' if boss else 'spawn_mummy' if mummy else 'spawn_'+room,2)

 return e

def path(a,b,door,passable=True):
 if a==b:return []
 q=deque([(a,[])]);seen={a}
 while q:
  node,steps=q.popleft()
  for nxt in ROOMS[node]['exits'].values():
   if {node,nxt}=={'entrada','patio'}:continue # player-only shortcut, enemies keep the old road
   if nxt in seen:continue
   if passable and door_between(node,nxt) and door['state'] in ('cerrada','trabada'):continue
   if nxt==b:return steps+[nxt]
   seen.add(nxt);q.append((nxt,steps+[nxt]))
 return None

def target(st,e):
 for passable in (True,False):
  choices=[]
  for i,p in enumerate(living(st)):
   steps=path(e['room'],p['room'],st['door'],passable)
   if steps is not None:choices.append((len(steps),i,p,steps))
  if choices:
   _,_,p,steps=min(choices,key=lambda v:(v[0],v[1]));return p,steps,not passable
 return None,[],False

def complete_level(st):
 if st['level']>=st['max_levels']:
  st['phase']='won';emit(st,'Nivel '+str(st['level'])+' terminado. Arena del Desierto completada. Victoria del equipo.','victory',5)
 else:
  st['phase']='level_done';emit(st,'Nivel '+str(st['level'])+' terminado. Revisen el equipo. La persona anfitriona puede iniciar la ronda siguiente.','level_end',5)
 for p in living(st):emit(st,p['name']+': '+CUES['cheer_'+p['character']],'cheer_'+p['character'],4,[p['id']],'cheer')

def next_level(st):
 if st['phase']!='level_done':raise ValueError('Todavía falta terminar el nivel.')
 
 for p in st['players']:p['storm_at']=None
 st['level']+=1;st['limit']=(180,150,120)[st['level']-1];st['level_started']=st['time'];st['time_warned']=[];st['level_kills']=0;st['boss_pending']=False;st['enemies']=[];st['door']={'state':'cerrada','hp':4,'max':4};st['paused']=True;st['ready']=[];st['pause_reason']='Nueva zona preparada. Todas las personas vivas deben marcar Listo.';st['phase']='play';st['spawn_at']=st['time']+2
 for p in living(st):p['room']='entrada';p['known']=['entrada'];p['facing']='norte'
 emit(st,'Ronda '+str(st['level'])+'. Llegaron a otra parte de las ruinas. Marquen Listo para comenzar.','next_level',4)

def award(st,p,e):
 p['kills']+=1;reward=50 if e['boss'] else 20;p['points']+=reward
 st['spawn_at']=max(st['spawn_at'],st['time']+pace(st)['spawn'])
 if e['boss']:st['bosses']+=1;complete_level(st)
 else:
  st['kills']+=1;st['level_kills']+=1
  if st['level_kills']>=st['goal']:st['boss_pending']=True
 emit(st,e['name']+' cayó. Sonido de derrota ficticia.',None,0,None,'enemy_down',e['id'])
 return reward


def tick(st,dt):
 if st['phase']!='play' or st['paused']:return
 # No damage bursts after a stalled process. The driver pauses on a large wall-clock gap.
 dt=min(max(float(dt),0),.25);st['time']+=dt;st['ticks']+=1;t=st['time'];cfg=pace(st)
 for p in st['players']:
  deadline=p.get('storm_at')
  if deadline is not None and t>=deadline:
   p['storm_at']=None
   if p['room']=='patio' and p['lives']>0 and not p['removed']:
    p['lives']-=1;emit(st,p['name']+' perdió una vida por la tormenta del atajo. Quedan '+str(p['lives'])+'.','storm_hit',5,[p['id']],'hurt')
    if not p['lives']:emit(st,p['name']+' cayó por la tormenta. El equipo sigue.','teammate_down',4,None,'death')
   else:emit(st,'La tormenta terminó.','storm_clear',1,[p['id']])
 if not living(st):
  st['phase']='lost';emit(st,'Todo el equipo quedó sin vidas. Fin de esta partida.','taunt',5);return
 if st['timed']:
  remaining=max(0,st['limit']-(t-st['level_started']))
  if remaining<=0:
   st['phase']='lost';emit(st,'Se terminó el tiempo de la ronda. El equipo pierde esta partida. Podés volver a intentarlo.','timeout',5,None,'timeout');return
  for threshold in (30,10):
   if remaining<=threshold and threshold not in st['time_warned']:
    st['time_warned'].append(threshold);emit(st,'Quedan '+str(threshold)+' segundos de juego en esta ronda.','time'+str(threshold),4,None,'clock')
 for e in st['enemies']:
  if st['phase']!='play':break
  if e['hp']<=0:continue
  if e.get('burn_at') is not None and t+1e-7>=e['burn_at']:
   e['burn_at']=None;e['hp']=max(0,e['hp']-1)
   if e['hp']==0:
    owner=find(st,e['burn_owner']);reward=award(st,owner,e)
    emit(st,'El fuego ficticio venció a '+e['name']+'. '+owner['name']+' recibe '+str(reward)+' puntos virtuales.','boss_kill' if e['boss'] else 'burn_kill',2,None,'flame');continue
  if t+1e-7<e.get('frozen_until',0):continue
  p,steps,blocked=target(st,e)
  if not p:break
  changed=e['target']!=p['id'];e['target']=p['id']
  if not steps:
   if changed or e['attack_at'] is None:
    e['attack_at']=t+cfg['contact'];e['warned']=p['id']
    emit(st,e['name']+' cerca de vos en '+ROOMS[e['room']]['name']+'. Aviso antes del contacto.','boss_near' if e['boss'] else 'mummy_near' if e['type']=='momia' else 'runner_near' if e['runner'] else 'walker_near',3,[p['id']],'threat',e['id'])
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
    if e['can_open'] and st['door']['state']=='cerrada':
     st['door']['state']='abierta';emit(st,e['name']+' abrió la puerta.','enemy_open',3,None,'door');continue
    st['door']['hp']=max(0,st['door']['hp']-(2 if e['runner'] else 1))
    if not st['door']['hp']:st['door']['state']='rota';emit(st,'La puerta se rompió.','door_break',4)
    else:emit(st,'Golpes en la puerta. Resistencia '+str(st['door']['hp'])+'.','door_hit',2)
   else:
    e['room']=nxt
    # Arrival grants full contact warning before damage, even if next tick is due.
    if nxt==p['room']:
     e['attack_at']=t+cfg['contact'];e['warned']=p['id']
     emit(st,e['name']+' entra en tu habitación.','boss_near' if e['boss'] else 'mummy_near' if e['type']=='momia' else 'runner_near' if e['runner'] else 'walker_near',3,[p['id']],'threat',e['id'])
 if not living(st):st['phase']='lost';emit(st,'Todo el equipo quedó sin vidas. Fin de esta partida.','taunt',5);return
 st['enemies']=[e for e in st['enemies'] if e['hp']>0]
 if st['phase']!='play':return
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
 text+=(ROUTE_HINT+' ' if p['room']=='entrada' else '')
 if p.get('storm_at') is not None:text+='Tormenta del atajo en '+str(max(0,round(p['storm_at']-st['time'])))+' segundos de juego. Salí de Dunas. '
 text+=' '.join(q['name']+' en '+ROOMS[q['room']]['name']+', '+str(q['lives'])+' vidas.' for q in st['players'] if not q['removed'] and q['id']!=pid)
 text+=' Arma '+WEAPONS[p['weapon']]['name']+'. Saldo '+str(p['points'])+' puntos virtuales, nunca dinero real. Tienda en Taller de arena: desde Ruinas por la puerta, o desde Dunas al norte tras el atajo. ' 
 text+=(' Contrarreloj: '+str(max(0,round(st['limit']-(st['time']-st['level_started']))))+' segundos restantes de juego.' if st['timed'] else ' Sin límite de tiempo de ronda.')
 text+=' Nivel '+str(st['level'])+' de tres. Bajas comunes de este nivel '+str(st['level_kills'])+' de '+str(st['goal'])+'. ' 
 text+=' Enemigos vencidos '+str(st['kills'])+'. Jefes vencidos '+str(st['bosses'])+'. Puerta '+st['door']['state']+'. '
 for e in st['enemies']:
  if e['hp']<=0:continue
  text+=e['name']+' en '+ROOMS[e['room']]['name']+', resistencia '+str(e['hp'])+'. '
 return text

def action(st,pid,act,target_id=''):
 p=find(st,pid);t=st['time']
 if act=='route_info':
  emit(st,ROUTE_HINT,'route_info',2,[pid]);return {'accepted':True,'notice':ROUTE_HINT}
 if act.startswith('buy_') or act.startswith('weapon_'):
  if st['phase'] not in ('play','level_done','won') or p['removed'] or p['lives']<=0:raise ValueError('No podés comprar ni equipar como espectador o fuera de partida.')
  weapon=act.split('_',1)[1]
  if weapon not in WEAPONS:raise ValueError('Arma inválida.')
  if act.startswith('buy_'):
   if p['room']!='cocina':raise ValueError('La tienda está en Taller de arena. Abrí la puerta de Ruinas y entrá.')
   if weapon in p['owned']:raise ValueError('Ya tenés esa arma. No se cobraron puntos.')
   price=WEAPONS[weapon]['price']
   if p['points']<price:raise ValueError('Necesitás '+str(price)+' puntos virtuales. Tenés '+str(p['points'])+'. No se cobró nada.')
   p['points']-=price;p['owned'].append(weapon);p['weapon']=weapon
   emit(st,'Compraste '+WEAPONS[weapon]['name']+' por '+str(price)+' puntos virtuales. Saldo '+str(p['points'])+'. Arma equipada.','purchase',2,[pid],'purchase')
  else:
   if weapon not in p['owned']:raise ValueError('Primero comprá esa arma con puntos virtuales en el Taller.')
   p['weapon']=weapon;emit(st,'Equipaste '+WEAPONS[weapon]['name']+'.','equip',1,[pid])
  return {'accepted':True}
 if st['phase']!='play' or st['paused']:raise ValueError('La partida está en pausa o terminó.')
 if p['removed'] or p['lives']<=0:raise ValueError('Estás de espectador. El resto puede seguir.')
 if act not in ('left','right','walk','back','run','open','close','bar','weapon_cuchillo','weapon_disparo','attack_nearest','attack_target','route_calm','route_risk'):raise ValueError('Acción inválida.')
 if t+1e-7<p['next_action']:return {'accepted':False,'notice':'Todavía se recupera tu acción anterior.','cue':'wait'}
 p['next_action']=t+.18 # Every command is bounded, including orientation/weapon changes.
 p['last_action']=act;p['path']=[p['room']]
 if act in ('left','right'):
  p['facing']=HEADINGS[(HEADINGS.index(p['facing'])+(-1 if act=='left' else 1))%4]
  emit(st,p['name']+' mira al '+p['facing']+'.',act,1,[pid]);return {'accepted':True}
 accepted=False;cue=None;text='';kind='action'
 if act in ('walk','back','run','route_calm','route_risk'):
  heading=('norte' if act=='route_calm' else 'este') if act.startswith('route_') else HEADINGS[(HEADINGS.index(p['facing'])+2)%4] if act=='back' else p['facing'];nxt=ROOMS[p['room']]['exits'].get(heading)
  if act.startswith('route_') and p['room']!='entrada':raise ValueError('La bifurcación está en Campamento.')
  if not nxt:text='No hay salida en esa dirección.';cue='blocked'
  elif door_between(p['room'],nxt) and st['door']['state'] in ('cerrada','trabada'):text='Puerta cerrada. Primero abrila.';cue='closed'
  elif act=='run' and (nxt not in p['known'] or any(e['hp']>0 and e['room']==nxt for e in st['enemies'])):text='Para correr necesitás una habitación conocida y libre.';cue='blocked'
  else:
   old_room=p['room'];p['path'].append(nxt);p['room']=nxt
   if nxt not in p['known']:p['known'].append(nxt)
   accepted=True;text=p['name']+' llega a '+ROOMS[nxt]['name']+'.';cue=nxt;kind='move'
   if p.get('storm_at') is not None and nxt!='patio':
    p['storm_at']=None;emit(st,'Saliste de Dunas. Tormenta evitada.','storm_safe',3,[pid])
   if old_room=='entrada' and nxt=='patio':
    p['storm_at']=t+12;p['facing']='norte';cue='route_risk'
    reward=15 if p.get('route_reward_level')!=st['level'] else 0;p['points']+=reward;p['route_reward_level']=st['level']
    text+=' '+CUES['route_risk']+' Ganaste '+str(reward)+' puntos de atajo. Saldo '+str(p['points'])+'.'
   elif old_room=='entrada' and nxt=='salon':cue='route_calm';text+=' '+CUES['route_calm'];p['facing']='este'
 elif act in ('open','close','bar'):
  d=st['door']
  if p['room'] not in ('salon','cocina') or d['state']=='rota':text='No podés usar esa puerta desde acá.';cue='blocked'
  elif act=='open' and d['state']!='abierta':d['state']='abierta';accepted=True;text='Abriste la puerta.';cue='opened';kind='door'
  elif act=='close' and d['state']=='abierta':d.update(state='cerrada',hp=min(4,d['hp']),max=4);accepted=True;text='Cerraste la puerta.';cue='closed';kind='door'
  elif act=='bar' and d['state']=='cerrada':d.update(state='trabada',hp=6,max=6);accepted=True;text='Trabaste la puerta. Resistencia seis.';cue='barred';kind='door'
  else:text='La puerta no permite esa acción.';cue='blocked'
 else:
  weapon=p['weapon'];spec=WEAPONS[weapon]
  if t+1e-7<p['weapon_ready'].get(weapon,0):return {'accepted':False,'notice':'Ese poder todavía se recupera. Podés cambiar a cuchillo o disparo.','cue':'wait'}
  candidates=[e for e in st['enemies'] if e['hp']>0 and (e['room']==p['room'] or (weapon=='iman' and (steps:=path(e['room'],p['room'],st['door'])) is not None and len(steps)==1))]
  e=next((e for e in candidates if e['id']==target_id),None) if act=='attack_target' else min(candidates,key=lambda e:(e['attack_at'] if e['attack_at'] is not None else float('inf'),e['hp'],e['id']),default=None)
  if e is None:text='No hay enemigo a tu alcance.';cue='no_target'
  else:
   p['weapon_ready'][weapon]=t+spec['cooldown'];e['hp']=max(0,e['hp']-spec['damage']);accepted=True;cue=None
   kind='shot' if weapon in ('disparo','bazuca') else 'hit'
   text=p['name']+' usa '+spec['name']+' contra '+e['name']+'. Resistencia '+str(e['hp'])+'.'
   if weapon=='hielo':
    extra=max(0,t+1-max(t,e.get('frozen_until',0)));e['frozen_until']=t+1;e['next_move']+=extra
    if e['attack_at'] is not None:e['attack_at']+=extra
    text+=' Congelado un segundo de reloj de juego.';cue='frozen';kind='freeze'
   elif weapon=='llamas':
    e['burn_at']=t+1;e['burn_owner']=pid;text+=' Fuego ficticio: un daño ahora y uno dentro de un segundo.';cue='flame';kind='flame'
   elif weapon=='rayo':
    extra=max(0,t+2-max(t,e.get('frozen_until',0)));e['frozen_until']=t+2;e['next_move']+=extra
    if e['attack_at'] is not None:e['attack_at']+=extra
    cue='rayo';kind='shock';text+=' Aturdido dos segundos de juego.'
   elif weapon=='sable':cue='sable';kind='slash'
   elif weapon=='mazo':cue='mazo';kind='quake'
   elif weapon=='bazuca':cue='blast';kind='blast'
   elif weapon=='iman':
    e['room']=p['room'];e['attack_at']=max(e['attack_at'] or 0,t+2);e['next_move']=max(e['next_move'],t+2);text+=' Lo atraés a tu zona y retrasás su contacto al menos dos segundos.';cue='pull';kind='pull'
   st['combat_effect']={'id':st['seq']+1,'time':t,'kind':kind,'enemy':e['id'],'room':e['room']}
   if cue is not None:emit(st,text,cue,3,[pid],kind);cue=None;kind='action'
   if e['hp']==0:
    reward=award(st,p,e);cue='boss_kill' if e['boss'] else 'kill';text+=' Vencido. Ganaste '+str(reward)+' puntos virtuales. Saldo '+str(p['points'])+'.'
 if accepted:p['next_action']=t+(.45 if act=='run' else .8 if act in ('walk','back','route_calm','route_risk') else 1.0)
 emit(st,text,cue,4 if cue=='route_risk' else 3 if cue=='route_calm' else 2 if cue in ('kill','boss_kill') else 1,[pid],kind)
 # Teammates in the same room get a nonverbal event, not speech for every ally attack.
 if accepted and kind in ('hit','shot','freeze','flame','blast','pull','door'):
  emit(st,text,None,0,[q['id'] for q in st['players'] if q['id']!=pid and q['room']==p['room']],kind)
 return {'accepted':accepted,'notice':text}
