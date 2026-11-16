"""Original generated maze with points and geometric wisps. One step per turn."""
import random
from collections import deque
DIRS={'arriba':(-1,0),'derecha':(0,1),'abajo':(1,0),'izquierda':(0,-1)}
SIZE=11
MAX_STEPS=120

def neighbors(cell,floor):
    return [(d,(cell[0]+dr,cell[1]+dc)) for d,(dr,dc) in DIRS.items() if (cell[0]+dr,cell[1]+dc) in floor]

def distances(start,floor):
    out={start:0};queue=deque([start])
    while queue:
        cell=queue.popleft()
        for _,n in neighbors(cell,floor):
            if n not in out:out[n]=out[cell]+1;queue.append(n)
    return out

def new_maze(seed):
    rng=random.Random(seed);floor={(1,1)};stack=[(1,1)]
    while stack:
        r,c=stack[-1];options=[(r+dr*2,c+dc*2) for dr,dc in DIRS.values() if 1<=r+dr*2<SIZE-1 and 1<=c+dc*2<SIZE-1 and (r+dr*2,c+dc*2) not in floor]
        if not options:stack.pop();continue
        nxt=rng.choice(options);floor.add(((r+nxt[0])//2,(c+nxt[1])//2));floor.add(nxt);stack.append(nxt)
    loops=[(r,c) for r in range(1,10) for c in range(1,10) if (r,c) not in floor and ((r%2==1 and (r,c-1) in floor and (r,c+1) in floor) or (c%2==1 and (r-1,c) in floor and (r+1,c) in floor))]
    floor.update(rng.sample(loops,min(5,len(loops))))
    return floor

def new_game(seats,seed=None):
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
    seed=random.randrange(1<<30) if seed is None else seed;floor=new_maze(seed);spawn=(1,1);dist=distances(spawn,floor);far=sorted(floor,key=lambda p:(dist[p],p),reverse=True)
    away=distances(far[0],floor);ghosts=[far[0],next(p for p in far if away[p]>=5 and dist[p]>=5)]
    st={'seats':list(seats),'seed':seed,'floor':floor,'spawn':spawn,'ghost_spawns':ghosts,'turn':seats[0],'boards':{},'winner':None,'seq':0,'result':''}
    for q in seats:st['boards'][q]={'position':spawn,'ghosts':list(ghosts),'dots':set(floor)-{spawn},'score':0,'steps':0,'lives':3,'done':False,'reason':''}
    return st

def legal_actions(st,pid):
    b=st['boards'].get(pid)
    return [d for d,_ in neighbors(b['position'],st['floor'])]+['esperar'] if b and not b['done'] and st['winner'] is None and pid==st['turn'] else []

def ghost_step(st,b):
    dist=distances(b['position'],st['floor']);ghosts=list(b['ghosts'])
    for i,g in enumerate(ghosts):
        blocked=set(ghosts[:i]+ghosts[i+1:]);options=[p for _,p in neighbors(g,st['floor']) if p not in blocked]
        if options:ghosts[i]=min(options,key=lambda p:(dist[p],p))
    b['ghosts']=ghosts

def play(st,pid,direction):
    if direction not in legal_actions(st,pid):raise ValueError('Fuera de turno o pared')
    b=st['boards'][pid];b['steps']+=1
    if direction!='esperar':dr,dc=DIRS[direction];b['position']=(b['position'][0]+dr,b['position'][1]+dc)
    ate=b['position'] in b['dots']
    if ate:b['dots'].remove(b['position']);b['score']+=1
    caught=b['position'] in b['ghosts'];ghost_moved=False
    if not caught and b['steps']%3==0:ghost_step(st,b);ghost_moved=True;caught=b['position'] in b['ghosts']
    if caught:b['lives']-=1;b['position']=st['spawn'];b['ghosts']=list(st['ghost_spawns'])
    if not b['lives']:b['done']=True;b['reason']='Sin vidas'
    elif not b['dots']:b['done']=True;b['reason']='Todos los puntos'
    elif b['steps']>=MAX_STEPS:b['done']=True;b['reason']='Ciento veinte pasos completos'
    st['seq']+=1;active=[q for q in st['seats'] if not st['boards'][q]['done']]
    if not active:
        best=max(st['boards'][q]['score'] for q in st['seats']);st['winner']=[q for q in st['seats'] if st['boards'][q]['score']==best]
    else:
        start=st['seats'].index(pid);st['turn']=next(st['seats'][(start+i)%len(st['seats'])] for i in range(1,len(st['seats'])+1) if st['seats'][(start+i)%len(st['seats'])] in active)
    return {'ate':ate,'caught':caught,'ghost_moved':ghost_moved}

def closest_dot(st,b,avoid=()):
    floor=st['floor']-set(avoid);queue=deque([(b['position'],None,0)]);seen={b['position']}
    while queue:
        cell,first,n=queue.popleft()
        if cell in b['dots']:return first,n
        for d,p in neighbors(cell,floor):
            if p not in seen:seen.add(p);queue.append((p,first or d,n+1))
    return None,None

def clues(st,b):
    r,c=b['position'];dist=distances(b['position'],st['floor']);paths=[];openings=dict(neighbors(b['position'],st['floor']))
    for d in DIRS:paths.append(d+(': pared' if d not in openings else ': fantasma, peligro' if openings[d] in b['ghosts'] else ': paso libre'))
    first,n=closest_dot(st,b);target='Punto más cercano: '+str(n)+' pasos; primer paso '+str(first)+'. ' if first else ''
    return ('Personaje fila '+str(r+1)+', columna '+str(c+1)+'. '+'. '.join(paths)+'. '+target+'Fantasmas a '+', '.join(str(dist[g]) for g in b['ghosts'])+' pasos de camino. '+str(3-b['steps']%3)+' pasos hasta que se muevan. '+str(b['lives'])+' vidas, '+str(b['score'])+' puntos, paso '+str(b['steps'])+' de ciento veinte.')

def choose_move(st,pid,level=2,rng=None):
    rng=rng or random;actions=legal_actions(st,pid)
    if not actions:return None
    b=st['boards'][pid]
    if level<=0:return rng.choice(actions)
    danger=set(b['ghosts'])
    if level>=3 and b['steps']%3==2:danger.update(p for g in b['ghosts'] for _,p in neighbors(g,st['floor']))
    safe=[d for d,p in neighbors(b['position'],st['floor']) if p not in danger]
    first,_=closest_dot(st,b,danger)
    if first in safe:return first
    if safe:
        dist=[distances(g,st['floor']) for g in b['ghosts']]
        return max(safe,key=lambda d:min(m[(b['position'][0]+DIRS[d][0],b['position'][1]+DIRS[d][1])] for m in dist)) if level>=2 else rng.choice(safe)
    return 'esperar'
