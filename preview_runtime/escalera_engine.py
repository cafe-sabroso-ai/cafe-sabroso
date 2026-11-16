"""La Escalera del Saber: progression and final, independent of transport."""

def new_game(seats):
    if len(seats)<2 or len(set(seats))!=len(seats):raise ValueError('Necesitamos al menos dos asientos distintos')
    return {'seats':list(seats),'players':{p:{'step':1,'lives':3,'errors':0,'finished':False,'out':False,'bonus':False} for p in seats},'turn':seats[0],'stage':'climb','arrivals':[],'finalists':[],'winner':None,'result':'','seq':0,'reto':None}


def eligible(st):
    return [p for p in st['seats'] if not st['players'][p]['out'] and not st['players'][p]['finished']]


def advance(st,pid):
    options=st['finalists'] if st['stage']=='final' else eligible(st)
    options=[p for p in options if st['players'][p]['lives']>0]
    if not options:return
    i=st['seats'].index(pid)
    st['turn']=min(options,key=lambda q:(st['seats'].index(q)-i-1)%len(st['seats']))


def start_final(st,second=None):
    finalists=st['arrivals'][:2] if second is None else [st['arrivals'][0],second]
    if len(finalists)!=2 or len(set(finalists))!=2:raise ValueError('Faltan finalistas')
    st['finalists']=finalists;st['stage']='final';st['turn']=finalists[0]
    for p in finalists:
        data=st['players'][p];data['lives']=3+int(data['bonus']);data['out']=False
    st['seq']+=1


def choose_finalist(st,pid,other):
    if st['stage']!='choose' or pid!=st['arrivals'][0] or other not in st['seats'] or other==pid or not st['players'][other]['out']:raise ValueError('Elegí a alguien eliminado')
    start_final(st,other)


def answer(st,pid,correct):
    if st['stage'] not in ('climb','final') or pid!=st['turn']:raise ValueError('No es tu turno')
    data=st['players'][pid];st['seq']+=1
    if not correct:data['lives']-=1;data['errors']+=1
    if st['stage']=='final':
        if data['lives']<=0:
            data['out']=True;st['winner']=next(p for p in st['finalists'] if p!=pid);st['stage']='reto';st['turn']=st['winner'];return 'winner'
        advance(st,pid);return 'correct' if correct else 'wrong'
    if correct:data['step']+=1
    else:data['step']=max(1,data['step']-1)
    event='correct' if correct else 'wrong'
    if data['lives']<=0:data['out']=True;event='out'
    elif data['step']>=8:
        data['step']=8;data['finished']=True;data['bonus']=data['errors']==0
        if data['bonus']:data['lives']+=1
        st['arrivals'].append(pid);event='arrival'
    if len(st['arrivals'])>=2:start_final(st);return 'final'
    if not eligible(st):
        if st['arrivals']:st['stage']='choose';st['turn']=st['arrivals'][0];return 'choose'
        st['stage']='draw';st['turn']=None;return 'draw'
    advance(st,pid);return event


def wildcard(st,pid):
    if st['stage']!='climb' or st['turn']!=pid:raise ValueError('No corresponde comodín')
    st['players'][pid]['lives']+=2;st['seq']+=1
