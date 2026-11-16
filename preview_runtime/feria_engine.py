"""Original assisted fairground toss, virtual balls and rewards only."""
import random
from copy import deepcopy
LANES=('izquierda','centro','derecha')
STRENGTHS=('suave','media','fuerte')
PRIZES=(('Molinillo de papel',80),('Estrella de feria',120),('Cinta de colores',150),('Sol de cartón',200))

def new_game(seats,seed=None):
 if not 1<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
 st=dict(seats=list(seats),seed=random.randrange(1<<30) if seed is None else seed,turn=seats[0],players={p:dict(score=0,hits=0,throws=0) for p in seats},level=1,phase='aim',aim='centro',strength='media',targets=[],balls=0,cue=None,wind='calma',seq=0,bonus=None,winner=None,result='Doce puestos de feria, solo puntos virtuales. Elegí dirección, fuerza y lanzar.')
 build_level(st);return st

def build_level(st):
 rng=random.Random(f"fair:{st['seed']}:{st['level']}");st['targets']=[dict(id=i,lane=LANES[i%3],kind='lata' if i%2==0 else 'muñeco de trapo',color=('azul','dorado','violeta','verde','coral')[i%5],height=1+i//3) for i in range(3+(st['level']-1)//2)];st['balls']=len(st['targets'])+3;st['wind']=rng.choice(('calma',)) if st['level']<=3 else rng.choice(('calma','hacia la izquierda','hacia la derecha'));st.update(aim='centro',strength='media',bonus=None);set_cue(st)

def set_cue(st):
 target=st['targets'][0] if st['targets'] else None
 if target is None:st['cue']=None;return
 lane=LANES.index(target['lane']);offset=-1 if st['wind']=='hacia la izquierda' else 1 if st['wind']=='hacia la derecha' else 0;aim=max(0,min(2,lane-offset));strength=STRENGTHS[(st['level']-1)//4];st['cue']=dict(target_id=target['id'],lane=target['lane'],kind=target['kind'],color=target['color'],height=target['height'],recommended_aim=LANES[aim],recommended_strength=strength)

def check(st,pid):
 if st['winner'] is not None or st['phase']!='aim' or st['turn']!=pid:raise ValueError('Fuera de turno')

def choose(st,pid,kind,value):
 check(st,pid)
 if kind=='aim' and value in LANES:st['aim']=value
 elif kind=='strength' and value in STRENGTHS:st['strength']=value
 else:raise ValueError('Opción inválida')
 st['seq']+=1;st['result']='Mira '+st['aim']+', fuerza '+st['strength']+'.'

def finish(st,reason):
 high=max(p['score'] for p in st['players'].values());st['winner']=[p for p in st['seats'] if st['players'][p]['score']==high];st['phase']='done';st['result']+=reason

def rotate_turn(st):
 i=st['seats'].index(st['turn']);st['turn']=st['seats'][(i+1)%len(st['seats'])]

def throw(st,pid,timeout=False):
 check(st,pid);cue=st['cue'];p=st['players'][pid];correct=not timeout and st['aim']==cue['recommended_aim'] and st['strength']==cue['recommended_strength'];st['balls']-=1;p['throws']+=1;st['seq']+=1
 if correct:
  st['targets']=[t for t in st['targets'] if t['id']!=cue['target_id']];p['score']+=40+st['level']*10;p['hits']+=1;st['result']='¡Clonc! Derribaste '+cue['kind']+' '+cue['color']+' en '+cue['lane']+'. '+str(40+st['level']*10)+' puntos virtuales.'
 else:st['result']='La pelota cayó en la red de seguridad. '+('Ventana agotada.' if timeout else 'Mira o fuerza no coincidían con la pista asistida.')+' Quedan '+str(st['balls'])+' pelotas del puesto.'
 if not st['targets']:st['phase']='bonus';st['cue']=None;st['result']+=' Puesto limpio. Girá la ruleta virtual de bonus.'
 elif st['balls']==0:finish(st,' Se acabaron las pelotas del puesto.')
 else:rotate_turn(st);set_cue(st);st['aim']='centro';st['strength']='media'
 return dict(correct=correct,level_clear=not st['targets'])

def spin(st,pid):
 if st['winner'] is not None or st['phase']!='bonus' or st['turn']!=pid:raise ValueError('No se puede girar')
 rng=random.Random(f"prize:{st['seed']}:{st['level']}");name,points=rng.choice(PRIZES);st['players'][pid]['score']+=points;st['bonus']=dict(name=name,points=points);st['result']='Ruleta virtual: '+name+', '+str(points)+' puntos. No es un objeto ni premio real.';st['seq']+=1;st['phase']='between'
 if st['level']==12:finish(st,' Completaron los doce puestos.')
 return deepcopy(st['bonus'])

def next_level(st):
 if st['phase']!='between' or st['winner'] is not None:raise ValueError('Puesto no completado')
 st['level']+=1;rotate_turn(st);build_level(st);st['phase']='aim';st['seq']+=1;st['result']='Puesto '+str(st['level'])+'. '+str(len(st['targets']))+' blancos. Viento '+st['wind']+'.'

def bot_move(st,pid,level=2):
 if st['turn']!=pid or st['winner'] is not None:raise ValueError('Fuera de turno')
 if st['phase']=='bonus':return spin(st,pid)
 check(st,pid);cue=st['cue'];rng=random.Random(f"bot:{st['seed']}:{pid}:{st['seq']}");st['aim']=cue['recommended_aim'];st['strength']=cue['recommended_strength']
 if rng.random()>(.65,.75,.85,.92,.97,1)[max(0,min(5,level))]:st['strength']=STRENGTHS[(STRENGTHS.index(st['strength'])+1)%3]
 return throw(st,pid)

def public_state(st):
 return deepcopy({k:st[k] for k in ('turn','players','level','phase','aim','strength','targets','balls','cue','wind','seq','bonus','winner','result')})|{'total_levels':12,'assisted':True}
