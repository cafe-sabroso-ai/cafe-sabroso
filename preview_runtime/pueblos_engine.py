"""Pueblos del Encuentro: cooperative fictional exploration, without enemies or money.
No real peoples, ethnic clothing, languages, ceremonies or history are represented.
"""
import random
from copy import deepcopy
COMMUNITIES=('Villa del Puente','Puerto de las Cometas','Jardín del Alba','Pueblo del Molino','Barrio de las Linternas','Villa del Arroyo')
PLACES=('sendero del bosque','puente del arroyo','plaza de las cometas','huerta comunitaria','taller de las linternas','muelle del lago')
WEATHERS=('despejado','brisa','llovizna')
RESOURCES=('madera','semillas','tela')
ROUTES=12

def visit_spec(visit,seed):
 if type(visit) is not int or not 1<=visit<=ROUTES:raise ValueError('Visita inválida')
 rng=random.Random(f'pueblos:{seed}:{visit}')
 # A request is always achievable by exploring, resting and exchanging.
 resource=rng.choice(RESOURCES);need=2+(visit-1)//4
 return dict(community=COMMUNITIES[(visit-1)%len(COMMUNITIES)],place=rng.choice(PLACES),weather=rng.choice(WEATHERS),resource=resource,need=need,visit=visit)

def new_game(seats,seed=None):
 if not 1<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Equipo inválido')
 seed=random.randrange(1<<30) if seed is None else seed
 st=dict(seats=list(seats),turn=seats[0],seed=seed,visit=1,phase='visit',winner=None,seq=0,team_points=0,helped=0,inventory={r:1 for r in RESOURCES},players={p:dict(energy=4,points=0) for p in seats},history=[],result='',revealed=[])
 start_visit(st);return st

def start_visit(st):
 st['spec']=visit_spec(st['visit'],st['seed']);st['phase']='visit';st['progress']=0
 for p in st['players'].values():p['energy']=max(2,p['energy'])
 st['result']='Nueva visita. '+st['spec']['community']+' pide '+str(st['spec']['need'])+' de '+st['spec']['resource']+' para un proyecto compartido.'

def legal_actions(st,pid):
 if st['phase']!='visit' or st['winner'] is not None or pid!=st['turn'] or pid not in st['players']:return []
 p=st['players'][pid];actions=['descansar','mapa']
 if p['energy']>=1:actions+=['explorar','ayudar']
 if any(v>0 for v in st['inventory'].values()):actions+=['intercambiar']
 return actions

def play(st,pid,action,resource=None):
 if action not in legal_actions(st,pid):raise ValueError('Acción fuera de turno')
 if action in ('explorar','intercambiar') and resource not in RESOURCES:raise ValueError('Recurso inválido')
 if action=='intercambiar' and st['inventory'][resource]<1:raise ValueError('No hay recurso para intercambiar')
 if action=='ayudar' and st['inventory'][st['spec']['resource']]<1:raise ValueError('Primero explorá o intercambiá por el recurso pedido')
 p=st['players'][pid];event=dict(seq=st['seq']+1,pid=pid,action=action,resource=resource,visit=st['visit'],points=0)
 if action=='descansar':p['energy']=min(4,p['energy']+2);text='Descansaste. Energía '+str(p['energy'])+'.'
 elif action=='mapa':
  if st['spec']['place'] not in st['revealed']:st['revealed'].append(st['spec']['place'])
  text='Mapa: '+st['spec']['place']+'. El proyecto pide '+st['spec']['resource']+'.'
 elif action=='explorar':
  p['energy']-=1;st['inventory'][resource]=min(12,st['inventory'][resource]+2)
  text='Exploraste el camino acordado con la comunidad. Reuniste hasta dos de '+resource+'.'
 elif action=='intercambiar':
  desired=st['spec']['resource']
  if resource==desired:raise ValueError('Elegí otro recurso para intercambiar')
  st['inventory'][resource]-=1;st['inventory'][desired]=min(12,st['inventory'][desired]+1)
  text='Intercambio acordado: uno de '+resource+' por uno de '+desired+'. Sin dinero.'
 else:
  desired=st['spec']['resource'];p['energy']-=1;st['inventory'][desired]-=1;st['progress']+=1;p['points']+=5;st['team_points']+=5;event['points']=5
  text='Aportaste uno de '+desired+' al proyecto. '+str(st['progress'])+' de '+str(st['spec']['need'])+'.'
  if st['progress']>=st['spec']['need']:
   st['helped']+=1;st['phase']='between';st['team_points']+=10;event['points']+=10;text+=' Proyecto completo. Diez puntos de equipo y agradecimiento de la comunidad.'
   if st['visit']==ROUTES:st['phase']='done';st['winner']=list(st['seats']);text+=' Completaron las doce visitas.'
 st['seq']+=1;st['history'].append(event);st['history']=st['history'][-30:];st['result']=text
 st['turn']=st['seats'][(st['seats'].index(pid)+1)%len(st['seats'])]
 return event

def continue_visit(st,pid):
 if st['phase']!='between' or pid!=st['seats'][0] or st['winner'] is not None:raise ValueError('Solo el anfitrión sigue la ruta')
 st['visit']+=1;start_visit(st)

def choose_move(st,pid,level=2):
 actions=legal_actions(st,pid)
 if not actions:return None,None
 wanted=st['spec']['resource']
 if st['players'][pid]['energy']==0:return 'descansar',None
 if st['inventory'][wanted]>0:return 'ayudar',None
 if level>0:
  extra=next((r for r in RESOURCES if r!=wanted and st['inventory'][r]>1),None)
  if extra:return 'intercambiar',extra
 return 'explorar',wanted

def public_state(st):
 # All resources and requests are shared; the random seed is not exposed.
 return deepcopy({k:st[k] for k in ('turn','visit','phase','winner','seq','team_points','helped','inventory','players','result','progress','spec','revealed')})|{'actions':legal_actions(st,st['turn']),'total_visits':ROUTES}
