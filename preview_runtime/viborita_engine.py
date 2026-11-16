"""Original accessible snake: one cardinal step per turn, independent circuits."""
import random
from collections import deque
DIRS={'arriba':(-1,0),'derecha':(0,1),'abajo':(1,0),'izquierda':(0,-1)}
OPPOSITE={'arriba':'abajo','abajo':'arriba','derecha':'izquierda','izquierda':'derecha'}
SIZE=8
MAX_STEPS=60
GOAL=10

def food_for(st,pid):
    board=st['boards'][pid];free=[(r,c) for r in range(SIZE) for c in range(SIZE) if (r,c) not in board['body']]
    return random.Random(st['seed']+board['score']*7919).choice(free) if free else None

def new_game(seats,seed=None):
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
    st={'seats':list(seats),'seed':seed if seed is not None else random.randrange(1<<30),'boards':{},'turn':seats[0],'winner':None,'seq':0,'result':''}
    for pid in seats:
        st['boards'][pid]={'body':[(3,3),(3,2),(3,1)],'direction':'derecha','food':None,'score':0,'steps':0,'done':False,'reason':''}
        st['boards'][pid]['food']=food_for(st,pid)
    return st

def legal_actions(st,pid):
    b=st['boards'].get(pid)
    return [d for d in DIRS if d!=OPPOSITE[b['direction']]] if b and not b['done'] and st['winner'] is None and st['turn']==pid else []

def destination(b,direction):
    r,c=b['body'][0];dr,dc=DIRS[direction];return r+dr,c+dc

def danger(b,direction):
    target=destination(b,direction)
    if not(0<=target[0]<SIZE and 0<=target[1]<SIZE):return 'pared'
    # The tail moves away on a non-growing step, so entering that cell is legal.
    if target in (b['body'] if target==b['food'] else b['body'][:-1]):return 'cuerpo'
    return ''

def play(st,pid,direction):
    if direction not in legal_actions(st,pid):raise ValueError('Dirección inválida o fuera de turno')
    b=st['boards'][pid];collision=danger(b,direction);b['direction']=direction;b['steps']+=1;ate=False
    if collision:b['done']=True;b['reason']='Choque con '+collision
    else:
        target=destination(b,direction);ate=target==b['food'];b['body'].insert(0,target)
        if ate:b['score']+=1;b['food']=food_for(st,pid)
        else:b['body'].pop()
        if b['score']>=GOAL or b['food'] is None:b['done']=True;b['reason']='Meta de frutas'
        elif b['steps']>=MAX_STEPS:b['done']=True;b['reason']='Sesenta pasos completos'
    st['seq']+=1
    active=[q for q in st['seats'] if not st['boards'][q]['done']]
    if not active:
        best=max(st['boards'][q]['score'] for q in st['seats']);st['winner']=[q for q in st['seats'] if st['boards'][q]['score']==best]
    else:
        start=st['seats'].index(pid)
        st['turn']=next(st['seats'][(start+i)%len(st['seats'])] for i in range(1,len(st['seats'])+1) if st['seats'][(start+i)%len(st['seats'])] in active)
    return {'ate':ate,'collision':collision,'done':b['done'],'score':b['score']}

def clues(b):
    r,c=b['body'][0];fr,fc=b['food'] if b['food'] is not None else (r,c)
    dr,dc=fr-r,fc-c
    fruit=('misma fila' if not dr else str(abs(dr))+(' arriba' if dr<0 else ' abajo'))+', '+('misma columna' if not dc else str(abs(dc))+(' a la izquierda' if dc<0 else ' a la derecha'))
    paths=[]
    for d in DIRS:
        paths.append(d+(': no se puede invertir' if d==OPPOSITE[b['direction']] else ': peligro '+danger(b,d) if danger(b,d) else ': libre'))
    return ('Cabeza fila '+str(r+1)+', columna '+str(c+1)+', va hacia '+b['direction']+'. Fruta fila '+str(fr+1)+', columna '+str(fc+1)+': '+fruit+'. '+'. '.join(paths)+'. '+str(b['score'])+' frutas, paso '+str(b['steps'])+' de sesenta.')

def choose_move(st,pid,level=2,rng=None):
    rng=rng or random;actions=legal_actions(st,pid)
    if not actions:return None
    b=st['boards'][pid];safe=[d for d in actions if not danger(b,d)]
    if level<=0 or not safe:return rng.choice(actions)
    if level==1:return rng.choice(safe)
    # Public board only: shortest route to current fruit, with flood-fill space as tie-break.
    blocked=set(b['body'][:-1]);food=b['food']
    def evaluate(d):
        start=destination(b,d);queue=deque([(start,0)]);seen={start};distance=99
        while queue:
            cell,n=queue.popleft()
            if cell==food:distance=min(distance,n)
            for dr,dc in DIRS.values():
                nxt=(cell[0]+dr,cell[1]+dc)
                if 0<=nxt[0]<SIZE and 0<=nxt[1]<SIZE and nxt not in blocked and nxt not in seen:seen.add(nxt);queue.append((nxt,n+1))
        return (len(seen)<len(b['body'])+2,distance,-len(seen)) if level>=3 else (distance,)
    return min(safe,key=evaluate)
