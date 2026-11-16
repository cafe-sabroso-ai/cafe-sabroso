"""Bounded syllable chaining: all options are visible, no free-text dictionary judgment."""
import random
from cadena_content import RAW
THEMES=('casa','naturaleza','comida','viaje','objetos')
def norm(x):return ' '.join(str(x).lower().translate(str.maketrans('áéíóúü','aeiouu')).split())
def syllable(x):
    x=norm(x);return x[1:] if x.startswith('rr') else x
BANK=[{'id':i,'word':w,'syllables':s,'theme':t,'first':syllable(s.split('-')[0]),'last':syllable(s.split('-')[-1])} for i,(w,s,t) in enumerate(RAW)]
def new_game(seats,mode='individual',theme='casa',seed=None):
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos') or theme not in THEMES:raise ValueError('Configuración inválida')
    teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
    st={'seats':list(seats),'teams':teams,'mode':mode,'theme':theme,'seed':seed if seed is not None else random.randrange(1<<30),'turn':seats[0],'scores':dict.fromkeys(seats,0),'lives':{t[0]:3 for t in teams},'used':[],'chain':[],'links':0,'resets':0,'current':None,'winner':None,'seq':0,'result':''};new_seed(st);return st

def team(st,p):return next(t for t in st['teams'] if p in t)
def alive(st,p):return st['lives'][team(st,p)[0]]>0
def candidates(st):
    tail=BANK[st['current']]['last'];return [b['id'] for b in BANK if b['first']==tail and b['id'] not in st['used']]
def new_seed(st):
    # Keep used words across restarts; choose a seed with at least one unused continuation.
    possible=[b['id'] for b in BANK if b['id'] not in st['used'] and any(c['id']!=b['id'] and c['id'] not in st['used'] and c['first']==b['last'] for c in BANK)]
    themed=[i for i in possible if BANK[i]['theme']==st['theme']];r=random.Random(st['seed']+st['resets']*7919);st['current']=r.choice(themed or possible) if possible else None
    if st['current'] is None:return False
    st['used'].append(st['current']);st['chain'].append({'seed':st['current']});return True

def play(st,p,index=None,timeout=False):
    if st['winner'] is not None or st['turn']!=p or not alive(st,p):raise ValueError('Fuera de turno')
    if not timeout and (type(index) is not int or not 0<=index<len(BANK)):raise ValueError('Palabra inválida')
    repeated=index in st['used'] if not timeout else False;correct=not timeout and index in candidates(st);reset=False
    if correct:
        for q in team(st,p):st['scores'][q]+=1
        st['links']+=1;st['current']=index;st['used'].append(index);st['chain'].append({'word':index,'player':p})
    else:st['lives'][team(st,p)[0]]-=1
    st['seq']+=1;live=[q for q in st['seats'] if alive(st,q)]
    if st['links']>=20 or not live:finish(st)
    else:
        if not candidates(st):
            st['resets']+=1;reset=True
            if not new_seed(st):finish(st)
        if st['winner'] is None:
            i=st['seats'].index(p);st['turn']=next(st['seats'][(i+k)%len(st['seats'])] for k in range(1,len(st['seats'])+1) if st['seats'][(i+k)%len(st['seats'])] in live)
    return {'correct':correct,'repeated':repeated,'reset':reset,'timeout':timeout}
def finish(st):
    best=max(st['scores'].values());st['winner']=[p for p in st['seats'] if st['scores'][p]==best]
def bot_move(st,level=2,rng=None):
    rng=rng or random;good=candidates(st);available=[b['id'] for b in BANK if b['id'] not in st['used']]
    return rng.choice(good) if good and rng.random()>(.3,.12,.03)[max(0,min(2,level))] else rng.choice(available or list(range(len(BANK))))
