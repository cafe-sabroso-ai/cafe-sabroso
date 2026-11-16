"""Accessible six-hole mole game. Current cue is public; future appearances stay private."""
import random
HOLES=[{'id':i,'position':('arriba' if i<3 else 'abajo')+' '+('izquierda','centro','derecha')[i%3],'pan':(-.7,0,.7)[i%3],'frequency':640 if i<3 else 320} for i in range(6)]

def new_game(seats,mode='individual',seed=None):
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Configuración inválida')
    teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
    seed=seed if seed is not None else random.randrange(1<<30)
    st={'seats':list(seats),'teams':teams,'mode':mode,'seed':seed,'boards':{},'turn':seats[0],'winner':None,'seq':0,'result':''}
    for i,t in enumerate(teams):
        rng=random.Random(seed+i*104729);appearances=[]
        for _ in range(10):appearances.append(rng.choice([x for x in range(6) if not appearances or x!=appearances[-1]]))
        st['boards'][t[0]]={'appearances':appearances,'round':0,'score':0,'done':False,'revealed':None,'last_correct':None}
    return st

def team(st,p):return next(t for t in st['teams'] if p in t)
def board(st,p):return st['boards'][team(st,p)[0]]
def public_board(st,b,show=False):
    return {k:b[k] for k in ('round','score','done','revealed','last_correct')}|{'cue':dict(HOLES[b['appearances'][b['round']]]) if show and not b['done'] else None}

def guess(st,p,index=None,timeout=False):
    if st['winner'] is not None or st['turn']!=p or board(st,p)['done']:raise ValueError('Fuera de turno')
    if not timeout and (type(index) is not int or not 0<=index<6):raise ValueError('Hueco inválido')
    b=board(st,p);target=b['appearances'][b['round']];correct=not timeout and index==target;b['score']+=int(correct);b['revealed']=target;b['last_correct']=correct;b['round']+=1;b['done']=b['round']>=10;st['seq']+=1
    live=[q for q in st['seats'] if not board(st,q)['done']]
    if not live:
        best=max(b['score'] for b in st['boards'].values());st['winner']=[q for q in st['seats'] if board(st,q)['score']==best]
    else:
        i=st['seats'].index(p);st['turn']=next(st['seats'][(i+k)%len(st['seats'])] for k in range(1,len(st['seats'])+1) if st['seats'][(i+k)%len(st['seats'])] in live)
    return {'correct':correct,'points':int(correct),'revealed':dict(HOLES[target]),'timeout':timeout}

def choose(st,p,level=2,rng=None):
    """Only current public cue, never the sequence or random seed."""
    rng=rng or random;cue=public_board(st,board(st,p),True)['cue']
    return cue['id'] if rng.random()>(.35,.15,.03)[max(0,min(2,level))] else rng.choice([i for i in range(6) if i!=cue['id']])
