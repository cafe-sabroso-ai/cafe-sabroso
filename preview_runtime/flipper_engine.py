"""Original assisted pinball. One public cue at a time, no twitch physics claim or money."""
import random
from copy import deepcopy
LANES=('izquierda','centro','derecha')
TABLES=('Jardín de Luces','Faro de Colores','Órbita de Cristal')
BONUSES=(('Estrella',100),('Cometa',150),('Faro',250),('Arcoíris',300))
BALLS=3
CONTACTS=8

def new_game(seats,seed=None,level=2):
 if not 1<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
 if type(level) is not int or not 0<=level<=5:raise ValueError('Nivel inválido')
 seed=random.randrange(1<<30) if seed is None else seed;rng=random.Random(seed)
 return dict(seats=list(seats),turn=seats[0],seed=seed,level=level,table=rng.choice(TABLES),phase='ready',players={p:dict(score=0,balls=BALLS,completed=0) for p in seats},step=0,seq=0,cue=None,bonus=None,history=[],winner=None,result='Tres bolas por participante. Tocá Lanzar para empezar.')

def cue_for(st):
 rng=random.Random(f"flipper:{st['seed']}:{st['turn']}:{st['players'][st['turn']]['completed']}:{st['step']}")
 lane=rng.choice(LANES);target=rng.choice(('bumper azul','campana dorada','estrella violeta','rampa verde'))
 return dict(lane=lane,target=target,value=50+25*st['level'],contact=st['step']+1,total=CONTACTS,window_seconds=(45,40,35,30,25,20)[st['level']],advice='izquierda' if lane=='izquierda' else 'derecha' if lane=='derecha' else 'ambas')

def legal_actions(st,pid):
 if st['winner'] is not None or st['turn']!=pid:return []
 return ['lanzar'] if st['phase']=='ready' else ['izquierda','derecha','ambas'] if st['phase']=='ball' else ['ruleta'] if st['phase']=='bonus' else []

def launch(st,pid):
 if 'lanzar' not in legal_actions(st,pid):raise ValueError('No se puede lanzar')
 st.update(phase='ball',step=0,bonus=None,cue=None);st['cue']=cue_for(st);st['seq']+=1;st['result']='Bola lanzada. Escuchá el carril y elegí pala.'

def paddle(st,pid,side=None,timeout=False):
 if st['phase']!='ball' or st['turn']!=pid or st['winner'] is not None:raise ValueError('Fuera de turno')
 if not timeout and side not in ('izquierda','derecha','ambas'):raise ValueError('Pala inválida')
 cue=st['cue'];correct=not timeout and side==cue['advice'];p=st['players'][pid];points=cue['value'] if correct else 0
 if correct:
  p['score']+=points;st['step']+=1;st['result']='¡Clac! '+cue['target']+'. Ganaste '+str(points)+' puntos virtuales.'
 else:st['result']='La bola se perdió.'+(' Se agotó la ventana asistida.' if timeout else ' La pala elegida no coincidía con el carril anunciado.')
 event=dict(seq=st['seq']+1,pid=pid,side=side,correct=correct,target=cue['target'],lane=cue['lane'],points=points,ball=p['completed']+1,contact=cue['contact'])
 st['seq']+=1;st['history'].append(event);st['history']=st['history'][-30:]
 if not correct or st['step']>=CONTACTS:
  p['balls']-=1;p['completed']+=1;st['phase']='bonus';st['cue']=None
  st['result']+=(' Bola completa, ocho contactos.' if correct else '')+' Quedan '+str(p['balls'])+' bolas. Girá la ruleta de bonus, sin dinero.'
 else:st['cue']=cue_for(st)
 return event

def spin_bonus(st,pid):
 if 'ruleta' not in legal_actions(st,pid):raise ValueError('No se puede girar')
 p=st['players'][pid];rng=random.Random(f"bonus:{st['seed']}:{pid}:{p['completed']}");name,points=rng.choice(BONUSES);p['score']+=points;st['bonus']=dict(name=name,points=points,pid=pid);st['seq']+=1
 st['result']='Ruleta: '+name+'. '+str(points)+' puntos virtuales de bonus.'
 eligible=[q for q in st['seats'] if st['players'][q]['balls']>0]
 if not eligible:
  high=max(p['score'] for p in st['players'].values());st['winner']=[q for q in st['seats'] if st['players'][q]['score']==high];st['phase']='done'
 else:
  i=st['seats'].index(pid);st['turn']=next(st['seats'][(i+j)%len(st['seats'])] for j in range(1,len(st['seats'])+1) if st['seats'][(i+j)%len(st['seats'])] in eligible);st['phase']='ready'
 return deepcopy(st['bonus'])

def choose_move(st,pid,level=2):
 actions=legal_actions(st,pid)
 if not actions:return None
 if st['phase']=='ready':return 'lanzar'
 if st['phase']=='bonus':return 'ruleta'
 rng=random.Random(f"bot:{st['seed']}:{pid}:{st['seq']}")
 return st['cue']['advice'] if rng.random()<(.45,.6,.72,.82,.9,.96)[max(0,min(5,level))] else rng.choice(actions)

def public_state(st):
 return deepcopy({k:st[k] for k in ('turn','level','table','phase','players','step','seq','cue','bonus','winner','result')})|{'actions':legal_actions(st,st['turn']),'max_balls':BALLS,'contacts_per_ball':CONTACTS,'assisted':True}
