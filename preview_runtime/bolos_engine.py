"""Bolos arcade: 5/10 entradas, dos tiros, un punto por bolo, sin bonus oficiales."""
import math
import aim_engine as aim
PIN_X={1:0,2:-.2,3:.2,4:-.4,5:0,6:.4,7:-.6,8:-.2,9:.2,10:.6}

def new_game(seats,frames=5):
    if frames not in (5,10) or len(seats)<2 or len(set(seats))!=len(seats):raise ValueError('Entradas o asientos inválidos')
    return {'seats':list(seats),'mode':'bolos','turn':seats[0],'scores':{p:0 for p in seats},'throws':[],'round':1,'frames':frames,'frame_turn':0,'ball':1,'standing':list(range(1,11)),'stage':'ready','token':0,'winner':None,'phase':math.pi/2,'result':''}

def knockdown(standing,offset,power):
    offset=float(offset);power=float(power)
    if not math.isfinite(offset) or not math.isfinite(power) or not 0<=power<=1:raise ValueError('Tiro inválido')
    if abs(offset)>1:return []
    if abs(offset)<.16 and power>.72:return list(standing)
    width=.12+.42*power
    return [p for p in standing if abs(PIN_X[p]-offset*.7)<=width]

def release(st,pid,token,elapsed,level_index=2,timed_out=False):
    if st['turn']!=pid or st['stage']!='aiming' or token!=st['token']:raise ValueError('Tiro fuera de turno')
    seconds=float(elapsed)
    if not math.isfinite(seconds) or seconds<0:raise ValueError('Tiempo inválido')
    index=max(0,min(5,int(level_index)));offset=aim.aim_position(seconds,index,st['phase']);timeout=timed_out or seconds>aim.DURATIONS[index]
    # Power rises/falls slowly while the lateral target moves. No random hidden pin result.
    power=.5+.5*math.sin(seconds*.75);fallen=[] if timeout else knockdown(st['standing'],offset,power)
    throw={'pid':pid,'round':st['round'],'ball':st['ball'],'offset':offset,'power':power,'fallen':fallen,'points':len(fallen),'timeout':timeout,'gutter':not timeout and abs(offset)>1,'standing_after':[p for p in st['standing'] if p not in fallen],'all_down':len(fallen)==len(st['standing'])}
    st['throws'].append(throw);st['scores'][pid]+=len(fallen);st['standing']=[p for p in st['standing'] if p not in fallen];st['stage']='result'
    if not st['standing'] or st['ball']==2:
        st['frame_turn']+=1;st['ball']=1;st['standing']=list(range(1,11))
        if st['frame_turn']>=st['frames']*len(st['seats']):
            best=max(st['scores'].values());st['winner']=[p for p in st['seats'] if st['scores'][p]==best];st['stage']='done'
        else:st['turn']=st['seats'][st['frame_turn']%len(st['seats'])];st['round']=st['frame_turn']//len(st['seats'])+1
    else:st['ball']=2
    return throw
