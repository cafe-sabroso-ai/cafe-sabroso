"""Short arcade court tennis: first set to four games, 3-all tiebreak.

One timed contact per turn, no double-service faults. Deuce ends with a
single deciding point after two returns to deuce. This is not official tennis.
"""
import math
import aim_engine as aim
import racket_engine as racket

def new_game(seats):
    st=racket.new_game(seats);st.update(mode='tenis',games=[0,0],game_points=[0,0],tie_points=[0,0],tiebreak=False,server_idx=0,tie_server_base=0)
    return st

def point_label(st):
    if st['tiebreak']:return str(st['tie_points'][0])+' a '+str(st['tie_points'][1])+' en desempate'
    a,b=st['game_points']
    if a>=3 and b>=3:
        if a==b:return 'iguales; punto decisivo' if a>=5 else 'iguales'
        return 'ventaja lado '+str(1 if a>b else 2)
    return ('0','15','30','40')[min(a,3)]+' a '+('0','15','30','40')[min(b,3)]

def award_point(st,side):
    if st['tiebreak']:
        st['tie_points'][side]+=1;a,b=st['tie_points']
        if max(a,b)>=7 and abs(a-b)>=2 or max(a,b)>=11:
            st['games'][side]+=1;st['winner']=list(st['teams'][side])
        else:
            n=sum(st['tie_points']);st['server_idx']=(st['tie_server_base']+(n+1)//2)%len(st['seats'])
    else:
        before=list(st['game_points']);st['game_points'][side]+=1;a,b=st['game_points']
        deciding=before[0]==before[1] and before[0]>=5
        if deciding or max(a,b)>=4 and abs(a-b)>=2:
            st['games'][side]+=1;st['game_points']=[0,0];ga,gb=st['games']
            st['server_idx']=(st['server_idx']+1)%len(st['seats'])
            if max(ga,gb)>=4 and abs(ga-gb)>=2:st['winner']=list(st['teams'][side])
            elif ga==gb==3:st['tiebreak']=True;st['tie_server_base']=st['server_idx']
    for i,team in enumerate(st['teams']):
        for pid in team:st['scores'][pid]=st['games'][i]
    st['server']=st['seats'][st['server_idx']];st['turn']=st['server'];st['rally']=0;st['incoming']='centro';st['round']+=1
    if st['winner']:st['stage']='done'

def release(st,pid,token,elapsed,level_index=2,timed_out=False,direction=None):
    if st['turn']!=pid or st['stage']!='aiming' or st['token']!=token:raise ValueError('Golpe fuera de turno')
    seconds=float(elapsed)
    if not math.isfinite(seconds) or seconds<0 or direction is not None and direction not in racket.ZONES:raise ValueError('Golpe inválido')
    index=max(0,min(5,int(level_index)));offset=aim.aim_position(seconds,index,st['phase']);timeout=timed_out or seconds>aim.DURATIONS[index]
    good=not timeout and abs(offset)<=.7;outgoing=direction or ('izquierda' if offset<-.25 else 'derecha' if offset>.25 else 'centro')
    shot={'pid':pid,'round':st['round'],'offset':offset,'points':0,'timeout':timeout,'good':good,'zone':outgoing,'rally':st['rally']+1,'point_winner':None}
    st['throws'].append(shot);st['stage']='result'
    if good:st['turn']=racket.other(st,pid);st['incoming']=outgoing;st['rally']+=1
    else:
        winner=racket.other(st,pid);shot['point_winner']=winner;shot['points']=1;st['point_count']+=1;award_point(st,st['seats'].index(winner)%2)
    shot['score_label']=point_label(st);return shot
