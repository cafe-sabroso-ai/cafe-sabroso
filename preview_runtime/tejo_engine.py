"""Original short sand-disc arcade: three rounds, closest to the mark wins."""
import math
import aim_engine as aim

def new_game(seats):
    if len(seats)<2 or len(seats)>20 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
    return {'seats':list(seats),'mode':'tejo','turn':seats[0],'scores':{p:0 for p in seats},'distance_totals':{p:0 for p in seats},'throws':[],'round':1,'stage':'ready','token':0,'winner':None,'phase':math.pi/2,'result':'','round_result':None}

def release(st,pid,token,elapsed,level_index=2,timed_out=False):
    if st['turn']!=pid or st['stage']!='aiming' or st['token']!=token:raise ValueError('Tiro fuera de turno')
    seconds=float(elapsed)
    if not math.isfinite(seconds) or seconds<0:raise ValueError('Tiempo inválido')
    index=max(0,min(5,int(level_index)));offset=aim.aim_position(seconds,index,st['phase']);timeout=timed_out or seconds>aim.DURATIONS[index]
    # Signed lateral distance in centimeters from the mark, plus small fixed depth gap.
    distance=500 if timeout else round(math.hypot(offset*160,5))
    throw={'pid':pid,'round':st['round'],'offset':offset,'distance':distance,'points':0,'timeout':timeout}
    st['throws'].append(throw);st['distance_totals'][pid]+=distance;st['stage']='result';st['round_result']=None
    n=len(st['throws']);count=len(st['seats'])
    if n%count==0:
        this_round=st['throws'][-count:];valid=[q for q in this_round if not q['timeout']]
        best=min((q['distance'] for q in valid),default=None)
        winners=[q['pid'] for q in valid if q['distance']==best]
        for p in winners:st['scores'][p]+=1
        st['round_result']={'round':st['round'],'winners':winners,'distance':best}
    if n==3*count:
        best=max(st['scores'].values());st['winner']=[p for p in st['seats'] if st['scores'][p]==best];st['stage']='done'
    else:st['turn']=st['seats'][n%count];st['round']=n//count+1
    return throw
