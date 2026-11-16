"""Original accessible toy claw, by grid steps. No money, randomness in grabs or real prizes."""
import random
SIZE=5
DIRS={'arriba':(-1,0),'abajo':(1,0),'izquierda':(0,-1),'derecha':(0,1)}
TOYS=('oso','perro','gato','conejo','zorro','búho')

def new_game(seats,mode='individual',seed=None):
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Participantes o modo inválido')
    teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
    st={'seats':list(seats),'mode':mode,'seed':seed if seed is not None else random.randrange(1<<30),'teams':teams,'boards':{},'turn':seats[0],'winner':None,'seq':0,'result':''}
    for team in teams:
        b={'claw':(2,2),'target':None,'toy':None,'lives':3,'score':0,'steps':0,'attempts':0,'done':False,'reason':''};st['boards'][team[0]]=b;next_toy(st,b)
    return st

def board_id(st,pid):return next(team[0] for team in st['teams'] if pid in team)
def board(st,pid):return st['boards'][board_id(st,pid)]
def next_toy(st,b):
    r=random.Random(st['seed']+b['score']*7919);b['target']=(r.randrange(5),r.randrange(5));b['toy']=random.Random(st['seed']).sample(TOYS,len(TOYS))[b['score']%len(TOYS)];b['claw']=(2,2);b['steps']=0

def clues(b):
    r,c=b['claw'];tr,tc=b['target'];dr,dc=tr-r,tc-c;distance=abs(dr)+abs(dc)
    return 'Buscá el '+b['toy']+'. Garra fila '+str(r+1)+', columna '+str(c+1)+'. '+('Estás encima: bajá la garra.' if distance==0 else ('Caliente. ' if distance==1 else 'Tibio. ' if distance<=3 else 'Frío. ')+('Misma fila' if not dr else str(abs(dr))+(' arriba' if dr<0 else ' abajo'))+', '+('misma columna' if not dc else str(abs(dc))+(' a la izquierda' if dc<0 else ' a la derecha'))+'.')+' '+str(b['lives'])+' vidas; '+str(b['score'])+' de tres peluches; '+str(b['steps'])+' de doce movimientos en este intento.'

def actions(st,pid):return list(DIRS)+['agarrar'] if st['turn']==pid and st['winner'] is None and not board(st,pid)['done'] else []

def play(st,pid,move):
    if move not in actions(st,pid):raise ValueError('Acción fuera de turno')
    b=board(st,pid);caught=b['toy'];edge=False;grab=move=='agarrar';won=False
    if not grab:
        dr,dc=DIRS[move];r,c=b['claw'];nr,nc=r+dr,c+dc;b['steps']+=1
        if 0<=nr<SIZE and 0<=nc<SIZE:b['claw']=(nr,nc)
        else:edge=True
        if b['steps']>=12:grab=True
    if grab:
        won=b['claw']==b['target'];b['attempts']+=1
        if won:b['score']+=1;b['lives']=min(6,b['lives']+1);b['done']=b['score']>=3;b['reason']='Tres peluches logrados' if b['done'] else ''
        else:b['lives']-=1;b['done']=b['lives']==0;b['reason']='Sin vidas' if b['done'] else ''
        if not b['done']:
            if won:next_toy(st,b)
            else:b['claw']=(2,2);b['steps']=0
    st['seq']+=1;active=[p for p in st['seats'] if not board(st,p)['done']]
    if not active:
        best=max(b['score'] for b in st['boards'].values());st['winner']=[p for p in st['seats'] if board(st,p)['score']==best]
    else:
        start=st['seats'].index(pid);st['turn']=next(st['seats'][(start+i)%len(st['seats'])] for i in range(1,len(st['seats'])+1) if st['seats'][(start+i)%len(st['seats'])] in active)
    return {'grab':grab,'won':won,'edge':edge,'done':b['done'],'toy':caught}

def choose_move(st,pid,level=2,rng=None):
    rng=rng or random;b=board(st,pid);r,c=b['claw'];tr,tc=b['target']
    if level==0 and rng.random()<.6:return rng.choice(actions(st,pid))
    if level==1 and rng.random()<.25:return rng.choice(list(DIRS))
    return 'arriba' if tr<r else 'abajo' if tr>r else 'izquierda' if tc<c else 'derecha' if tc>c else 'agarrar'
