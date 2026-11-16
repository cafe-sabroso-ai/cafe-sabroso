"""Five hidden-object riddle rounds. Public bot sees only released clues and candidates."""
import random
from veoveo_content import SCENES,COLORS

def objects(scene):return [{'id':i,'word':v[0],'color':v[1],'shape':v[2],'use':v[3],'art':v[4],'fill':COLORS[v[1]]} for i,v in enumerate(SCENES[scene])]
def new_game(seats,mode='individual',scene='casa',seed=None):
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos') or scene not in SCENES:raise ValueError('Configuración inválida')
    teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats];seed=seed if seed is not None else random.randrange(1<<30)
    st={'seats':list(seats),'teams':teams,'mode':mode,'scene':scene,'seed':seed,'boards':{},'turn':seats[0],'winner':None,'seq':0,'result':''}
    for i,t in enumerate(teams):
        targets=random.Random(seed+i*104729).sample(range(len(SCENES[scene])),5);st['boards'][t[0]]={'targets':targets,'round':0,'score':0,'clues':1,'done':False,'revealed':None,'last_correct':None}
    return st

def team(st,p):return next(t for t in st['teams'] if p in t)
def board(st,p):return st['boards'][team(st,p)[0]]
def target(st,b):return objects(st['scene'])[b['targets'][b['round']]]
def clues(st,b):
    obj=target(st,b);return ['Es de color '+obj['color']+'.',obj['shape'],obj['use']][:b['clues']]
def check(st,p):
    if st['winner'] is not None or st['turn']!=p or board(st,p)['done']:raise ValueError('Fuera de turno')
def hint(st,p):
    check(st,p);b=board(st,p)
    if b['clues']>=3:raise ValueError('Ya están las tres pistas')
    b['clues']+=1;st['seq']+=1

def public_board(st,b,show=False):
    return {k:b[k] for k in ('round','score','clues','done','revealed','last_correct')}|{'hints':clues(st,b) if show and not b['done'] else []}

def guess(st,p,index=None,timeout=False):
    check(st,p)
    if not timeout and (type(index) is not int or not 0<=index<len(SCENES[st['scene']])):raise ValueError('Objeto inválido')
    b=board(st,p);revealed=target(st,b);correct=not timeout and index==revealed['id'];points=4-b['clues'] if correct else 0;b['score']+=points;b['revealed']=revealed['id'];b['last_correct']=correct;b['round']+=1;b['clues']=1;b['done']=b['round']>=5;st['seq']+=1
    live=[q for q in st['seats'] if not board(st,q)['done']]
    if not live:
        best=max(b['score'] for b in st['boards'].values());st['winner']=[p for p in st['seats'] if board(st,p)['score']==best]
    else:
        i=st['seats'].index(p);st['turn']=next(st['seats'][(i+k)%len(st['seats'])] for k in range(1,len(st['seats'])+1) if st['seats'][(i+k)%len(st['seats'])] in live)
    return {'correct':correct,'points':points,'revealed':revealed['word'],'timeout':timeout}

def choose(st,p,level=2,rng=None):
    """Only a public projection is used below: no targets, seed, or hidden access."""
    rng=rng or random;view=public_board(st,board(st,p),True);bank=objects(st['scene']);h=view['hints'];possible=[o for o in bank if ('Es de color '+o['color']+'.')==h[0] and (len(h)<2 or o['shape']==h[1]) and (len(h)<3 or o['use']==h[2])]
    if level>0 and len(possible)>1 and view['clues']<3:return 'hint'
    pool=possible if rng.random()>(.3,.12,.03)[max(0,min(2,level))] else bank
    return rng.choice(pool)['id']
