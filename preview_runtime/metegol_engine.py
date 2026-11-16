"""Original turn-based foosball arcade. No regulation or physical simulation claims."""
import math
import aim_engine as aim
ROWS=('arquero','defensa','medio','delantero')
ZONES=('izquierda','centro','derecha')

def new_game(seats,target=3):
    if len(seats) not in (2,4) or len(set(seats))!=len(seats) or target not in (3,5):raise ValueError('Dos o cuatro asientos, meta tres o cinco')
    return {'seats':list(seats),'teams':[list(seats[::2]),list(seats[1::2])],'turn':seats[0],'side':0,'scores':[0,0],'target':target,'row':2,'stage':'ready','token':0,'phase':math.pi/2,'winner':None,'round':1,'result':'','pending':None,'rotations':[0,0],'actions':0,'possession_steps':0,'throws':[]}

def actor(st,side):return st['teams'][side][st['rotations'][side]%len(st['teams'][side])]
def rotate(st,side):st['rotations'][side]+=1

def prepare(st,phase=None,rng=None):
    if st['winner'] is not None:raise ValueError('Partido terminado')
    import random
    st['phase']=phase if phase is not None else (rng or random).choice((math.pi/2,3*math.pi/2));st['token']+=1;st['stage']='ready'

def start(st,pid,token):
    if pid!=st['turn'] or st['token']!=token or st['stage']!='ready':return False
    st['stage']='aiming';return True

def change_possession(st,side,row=2):
    st.update(side=side,row=row,turn=actor(st,side),pending=None,possession_steps=0)

def action(st,pid,token,kind,elapsed=0,level_index=2,direction='centro',timed_out=False):
    if pid!=st['turn'] or st['stage']!='aiming' or token!=st['token'] or st['winner'] is not None:raise ValueError('Acción fuera de turno')
    seconds=float(elapsed)
    if not math.isfinite(seconds) or seconds<0 or direction not in ZONES or kind not in ('pasar','volver','tirar','defender','girar'):raise ValueError('Acción inválida')
    index=max(0,min(5,int(level_index)));offset=aim.aim_position(seconds,index,st['phase']);timeout=timed_out or seconds>aim.DURATIONS[index]
    if bool(st['pending'])!=(kind=='defender') and kind!='girar' and not timeout:raise ValueError('Acción no disponible')
    side=st['seats'].index(pid)%2;good=not timeout and abs(offset)<=.7
    event={'pid':pid,'kind':kind,'zone':direction,'offset':offset,'good':good,'timeout':timeout,'points':0,'goal_side':None,'row':ROWS[st['row']]}
    st['actions']+=1;st['stage']='result';rotate(st,side)
    if kind=='girar':change_possession(st,1-side);st['result']='Falta por girar la barra. Pelota para el rival.'
    elif st['pending']:
        shot=st['pending'];saved=good and kind=='defender' and direction==shot['zone']
        if saved:change_possession(st,side,0);st['result']='Atajó el arquero. Tiene la pelota el arquero.'
        else:
            scorer=shot['side'];points=2 if shot['row']==0 else 1;st['scores'][scorer]+=points;event.update(points=points,goal_side=scorer);st['result']='¡Gol! '+('Gol del arquero, vale doble.' if points==2 else 'Suma un gol.');st['round']+=1;change_possession(st,side)
            if st['scores'][scorer]>=st['target']:st['winner']=list(st['teams'][scorer]);st['stage']='done'
    elif timeout or not good:change_possession(st,1-side);st['result']='Fuera de tiempo. Pelota para el rival.' if timeout else 'Rebotó y la perdió. Pelota para el rival.'
    elif kind in ('pasar','volver'):
        st['row']=min(3,st['row']+1) if kind=='pasar' else max(0,st['row']-1);st['possession_steps']+=1;st['turn']=actor(st,side);st['result']='La tiene el '+ROWS[st['row']]+'.'
        if st['possession_steps']>=6:change_possession(st,1-side);st['result']='Seis pases sin tiro. Pelota para el rival.'
    else:
        st['pending']={'side':side,'row':st['row'],'zone':direction};st['turn']=actor(st,1-side);st['result']='Tiro a la '+direction+'. El rival defiende con timing.'
    st['throws'].append(event);return event

def timeout(st,pid):
    if st['stage']=='ready':start(st,pid,st['token'])
    return action(st,pid,st['token'],'defender' if st['pending'] else 'tirar',0,timed_out=True)
