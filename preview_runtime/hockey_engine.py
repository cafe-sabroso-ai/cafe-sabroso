"""Turn-based original arcade table hockey, two sides, first to five goals.

A shot is kept private until the defender commits to one of three zones. Bots
must choose defense from public state, never from pending_shot.
"""
import math
import aim_engine as aim
ZONES=('izquierda','centro','derecha')

def new_game(seats):
    if len(seats) not in (2,4) or len(set(seats))!=len(seats):raise ValueError('Se necesitan dos o cuatro participantes distintos')
    return {'seats':list(seats),'teams':[list(seats[::2]),list(seats[1::2])],'cursors':[0,0],'turn':seats[0],'scores':{p:0 for p in seats},'powers':{p:1 for p in seats},'shots':[],'pending_shot':None,'stage':'ready','token':0,'phase':math.pi/2,'winner':None,'round':1,'result':''}

def other(st,pid):
    if pid not in st['seats']:raise ValueError('Lado inválido')
    side=1-(st['seats'].index(pid)%2)
    return st['teams'][side][st['cursors'][side]%len(st['teams'][side])]

def zone(offset):
    return 'izquierda' if offset<-.25 else 'derecha' if offset>.25 else 'centro'

def shoot(st,pid,token,elapsed,level_index=2,direction=None,power=False,timed_out=False):
    if st['turn']!=pid or st['stage']!='aiming' or st['token']!=token:raise ValueError('Tiro fuera de turno')
    if direction is not None and direction not in ZONES:raise ValueError('Zona inválida')
    elapsed=float(elapsed)
    if not math.isfinite(elapsed) or elapsed<0:raise ValueError('Tiempo inválido')
    if power and not st['powers'][pid]:raise ValueError('Poder gastado')
    index=max(0,min(5,int(level_index)))
    x=aim.aim_position(elapsed,index,st['phase']) if direction is None else {'izquierda':-.5,'centro':0,'derecha':.5}[direction]
    timeout=timed_out or elapsed>aim.DURATIONS[index]
    if power:
        for mate in st['teams'][st['seats'].index(pid)%2]:st['powers'][mate]-=1
    shot={'pid':pid,'offset':x,'zone':zone(x),'power':bool(power),'timeout':timeout,'on_target':not timeout and abs(x)<=(.95 if power else .7)}
    st['pending_shot']=shot;st['turn']=other(st,pid);st['cursors'][st['seats'].index(pid)%2]+=1;st['stage']='defend'
    return {'pid':pid,'power':bool(power),'timeout':timeout}

def defend(st,pid,direction,timed_out=False):
    if st['stage']!='defend' or st['turn']!=pid or direction not in ZONES:raise ValueError('Defensa fuera de turno')
    shot=dict(st['pending_shot']);shot.update(defender=pid,defense=direction,saved=shot['on_target'] and not timed_out and direction==shot['zone'])
    shot['goal']=shot['on_target'] and not shot['saved'];shot['bounces']=1 if not shot['on_target'] else 2 if shot['saved'] else 0
    if shot['goal']:
        for mate in st['teams'][st['seats'].index(shot['pid'])%2]:st['scores'][mate]+=1
    st['shots'].append(shot);st['pending_shot']=None;st['round']+=1;st['stage']='result'
    if st['scores'][shot['pid']]>=5:st['winner']=list(st['teams'][st['seats'].index(shot['pid'])%2]);st['stage']='done'
    # Defender takes the next shot. No hidden random scoring or teleporting puck.
    return shot

def public_state(st,viewer=None):
    return {k:v for k,v in st.items() if k!='pending_shot'} | {'pending_shot': {'pid':st['pending_shot']['pid'],'power':st['pending_shot']['power']} if st['pending_shot'] else None}
