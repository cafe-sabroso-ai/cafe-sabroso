"""Shared short sonic-aim game, rings rather than official sports scoring."""
import math,random
MODES=('dardos','arco','sapo')
SPEEDS=(.45,.6,.8,1.05,1.35,1.75)
DURATIONS=(24,18,12,9,6,4)

def aim_position(elapsed,level_index=2,phase=math.pi/2):
    level_index=max(0,min(5,int(level_index)))
    return 1.25*math.sin(max(0,float(elapsed))*SPEEDS[level_index]*math.pi+phase)

def points(offset):
    distance=abs(float(offset))
    if not math.isfinite(distance):raise ValueError('Distancia inválida')
    if distance>1:return 0
    if distance<=.08:return 10
    if distance<=.25:return 8
    if distance<=.45:return 6
    if distance<=.7:return 4
    return 2

def sapo_points(offset):
    x=float(offset)
    if not math.isfinite(x):raise ValueError('Distancia inválida')
    if abs(x)<=.09:return 100,'boca del sapo'
    if abs(abs(x)-.38)<=.1:return 50,'agujero cercano'
    if abs(abs(x)-.78)<=.12:return 20,'agujero lateral'
    return 0,'mesa, sin agujero'


def new_game(seats,mode='dardos'):
    if mode not in MODES or len(seats)<2 or len(set(seats))!=len(seats):raise ValueError('Modo o asientos inválidos')
    return {'seats':list(seats),'mode':mode,'turn':seats[0],'scores':{p:0 for p in seats},'throws':[],'round':1,'stage':'ready','token':0,'winner':None,'phase':math.pi/2,'result':''}

def prepare(st,phase=None,rng=None):
    if st['winner'] is not None:raise ValueError('Partida terminada')
    rng=rng or random;st['phase']=phase if phase is not None else rng.choice((math.pi/2,3*math.pi/2))
    st['stage']='ready';st['token']+=1

def start(st,pid,token):
    if st['turn']!=pid or st['stage']!='ready' or token!=st['token']:return False
    st['stage']='aiming';return True

def release(st,pid,token,elapsed,level_index=2,timed_out=False):
    if st['turn']!=pid or st['stage']!='aiming' or token!=st['token']:raise ValueError('Tiro fuera de turno')
    seconds=float(elapsed)
    if not math.isfinite(seconds) or seconds<0:raise ValueError('Tiempo inválido')
    index=max(0,min(5,int(level_index)));offset=aim_position(seconds,index,st['phase']);value=0 if timed_out or seconds>DURATIONS[index] else points(offset)
    destination=None
    if st['mode']=='sapo':
        value,destination=sapo_points(offset)
        if timed_out or seconds>DURATIONS[index]:value=0;destination='fuera de tiempo'
    throw={'pid':pid,'round':st['round'],'offset':offset,'points':value,'destination':destination,'timeout':timed_out or seconds>DURATIONS[index]};st['throws'].append(throw);st['scores'][pid]+=value;st['stage']='result'
    total=len(st['throws'])
    shots=3 if st['mode']=='sapo' else 1
    if total>=3*shots*len(st['seats']):
        best=max(st['scores'].values());st['winner']=[p for p in st['seats'] if st['scores'][p]==best];st['stage']='done'
    else:st['turn']=st['seats'][(total//shots)%len(st['seats'])];st['round']=total//(shots*len(st['seats']))+1
    return throw
