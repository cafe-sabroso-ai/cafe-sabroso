"""Numbered original sound/color memory circuits, one per player/team."""
import random
CELLS=(('amarillo','arriba a la izquierda','tambor',220),('azul','arriba al centro','campana',330),('rojo','arriba a la derecha','maraca',440),('verde','abajo a la izquierda','flauta',550),('violeta','abajo al centro','cuerda',660),('naranja','abajo a la derecha','gota',770))

def cells(count):
    if count not in (4,6):raise ValueError('Elegí cuatro o seis')
    out=[{'id':i,'color':x[0],'position':x[1],'sound':x[2],'frequency':x[3]} for i,x in enumerate(CELLS[:count])]
    if count==4:
        for c,pos in zip(out,('arriba a la izquierda','arriba a la derecha','abajo a la izquierda','abajo a la derecha')):c['position']=pos
    return out

def new_game(seats,count=4,mode='individual',seed=None):
    cells(count)
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Participantes o modo inválido')
    teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
    st={'seats':list(seats),'count':count,'mode':mode,'teams':teams,'seed':seed if seed is not None else random.randrange(1<<30),'boards':{},'turn':seats[0],'winner':None,'seq':0,'result':''}
    for i,t in enumerate(teams):
        b={'seed':st['seed']+i*104729,'sequence':[],'response':[],'lives':3,'steps':0,'attempts':0,'done':False,'stage':'memorize'};st['boards'][t[0]]=b;next_sequence(st,b)
    return st

def team(st,p):return next(t for t in st['teams'] if p in t)
def board(st,p):return st['boards'][team(st,p)[0]]
def next_sequence(st,b):
    # A success adds one cell; a failed attempt starts a fresh sequence of the same length.
    r=random.Random(b['seed']+b['attempts']*7919)
    if len(b['sequence'])==b['steps'] and b['sequence']:b['sequence'].append(r.randrange(st['count']))
    else:b['sequence']=[r.randrange(st['count']) for _ in range(b['steps']+1)]
    b['response']=[];b['stage']='memorize'

def check(st,p,stage):
    if st['winner'] is not None or st['turn']!=p or board(st,p)['done'] or board(st,p)['stage']!=stage:raise ValueError('Fuera de turno')
def ready(st,p):check(st,p,'memorize');board(st,p)['stage']='repeat';st['seq']+=1

def edit(st,p,move):
    check(st,p,'repeat');b=board(st,p)
    if move=='undo':b['response']=b['response'][:-1]
    elif move=='clear':b['response']=[]
    elif type(move) is int and 0<=move<st['count'] and len(b['response'])<12:b['response'].append(move)
    else:raise ValueError('Casillero inválido')
    st['seq']+=1

def submit(st,p,timeout=False):
    check(st,p,'repeat');b=board(st,p);correct=not timeout and b['response']==b['sequence'];old=list(b['sequence']);b['attempts']+=1
    if correct:b['steps']+=1
    else:b['lives']-=1
    b['done']=b['lives']==0 or b['steps']>=12
    if b['done']:b['stage']='done';b['response']=[]
    else:
        if not correct:b['sequence']=[]
        next_sequence(st,b)
    live=[q for q in st['seats'] if not board(st,q)['done']];st['seq']+=1
    if not live:
        best=max(b['steps'] for b in st['boards'].values());st['winner']=[q for q in st['seats'] if board(st,q)['steps']==best]
    else:
        i=st['seats'].index(p);st['turn']=next(st['seats'][(i+k)%len(st['seats'])] for k in range(1,len(st['seats'])+1) if st['seats'][(i+k)%len(st['seats'])] in live)
    return {'correct':correct,'done':b['done'],'length':len(old)}

def public_board(b,show=False):
    return {k:b[k] for k in ('response','lives','steps','attempts','done','stage')}|{'length':len(b['sequence']),'sequence':list(b['sequence']) if show and b['stage']=='memorize' else []}

def bot_response(st,p,level=2,rng=None):
    rng=rng or random;b=board(st,p);ans=list(b['sequence']);chance=(.35,.27,.18,.12,.07,.03)[max(0,min(5,level))]*max(1,len(ans)/4)
    if ans and rng.random()<min(.85,chance):
        i=rng.randrange(len(ans));ans[i]=(ans[i]+rng.randrange(1,st['count']))%st['count']
    return ans
