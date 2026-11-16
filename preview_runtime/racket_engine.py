"""Short arcade racket rally, not a regulation sports simulation."""
import math
import aim_engine as aim
ZONES=('izquierda','centro','derecha')

def new_game(seats,mode='pingpong'):
    if len(seats) not in (2,4) or len(set(seats))!=len(seats) or mode!='pingpong':raise ValueError('Dos o cuatro jugadores y modo válido requeridos')
    return {'seats':list(seats),'teams':[list(seats[::2]),list(seats[1::2])],'mode':mode,'turn':seats[0],'server':seats[0],'scores':{p:0 for p in seats},'throws':[],'round':1,'stage':'ready','token':0,'phase':math.pi/2,'winner':None,'result':'','incoming':'centro','rally':0,'point_count':0}

def other(st,pid):return st['seats'][(st['seats'].index(pid)+1)%len(st['seats'])]

def release(st,pid,token,elapsed,level_index=2,timed_out=False,direction=None):
    if st['turn']!=pid or st['stage']!='aiming' or st['token']!=token:raise ValueError('Devolución fuera de turno')
    seconds=float(elapsed)
    if not math.isfinite(seconds) or seconds<0 or direction is not None and direction not in ZONES:raise ValueError('Golpe inválido')
    index=max(0,min(5,int(level_index)));offset=aim.aim_position(seconds,index,st['phase']);timeout=timed_out or seconds>aim.DURATIONS[index]
    # A zone is a direction of return, not an automatic success. Timing still matters.
    good=not timeout and abs(offset)<=.7
    outgoing=direction or ('izquierda' if offset<-.25 else 'derecha' if offset>.25 else 'centro')
    shot={'pid':pid,'round':st['round'],'offset':offset,'points':0,'timeout':timeout,'good':good,'zone':outgoing,'rally':st['rally']+1,'point_winner':None}
    st['throws'].append(shot);st['stage']='result'
    if good:
        st['turn']=other(st,pid);st['incoming']=outgoing;st['rally']+=1
    else:
        winner=other(st,pid)
        for mate in st['teams'][st['seats'].index(winner)%2]:st['scores'][mate]+=1
        shot['point_winner']=winner;shot['points']=1;st['point_count']+=1;st['rally']=0
        a,b=[st['scores'][p] for p in st['seats'][:2]]
        if max(a,b)>=7 and abs(a-b)>=2 or max(a,b)>=11:st['winner']=list(st['teams'][0 if a>b else 1]);st['stage']='done'
        else:
            # Two serves each, one serve each from 6-all (arcade deuce).
            count=st['point_count'];idx=(count//2)%len(st['seats']) if min(a,b)<6 else (6+count-12)%len(st['seats'])
            st['server']=st['seats'][idx];st['turn']=st['server'];st['round']=count+1;st['incoming']='centro'
    return shot
