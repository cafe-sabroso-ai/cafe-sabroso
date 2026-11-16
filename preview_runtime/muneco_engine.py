"""Find a toy in an original six-room house. Hidden room never belongs in client state."""
import random
ROOMS=('Sala','Cocina','Dormitorio','Baño','Estudio','Patio')
LINKS={0:(1,3),1:(0,2,4),2:(1,5),3:(0,4),4:(1,3,5),5:(2,4)}
TOYS=('perro','oso','gato','conejo','zorro','búho')

def distance(a,b):
    front=[a];seen={a};n=0
    while front:
        if b in front:return n
        front=[q for p in front for q in LINKS[p] if q not in seen];seen.update(front);n+=1

def new_game(seats,mode='individual',seed=None):
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Participantes o modo inválido')
    teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
    st={'seats':list(seats),'mode':mode,'seed':seed if seed is not None else random.randrange(1<<30),'teams':teams,'boards':{},'turn':seats[0],'winner':None,'seq':0,'result':''}
    for i,team in enumerate(teams):
        b={'variant_seed':st['seed']+i*104729,'room':0,'hidden_room':None,'toy':None,'lives':3,'score':0,'steps':0,'attempts':0,'done':False,'reason':'','visited':[],'checked':[],'history':{},'last_found':None};st['boards'][team[0]]=b;next_toy(st,b)
    return st

def board_id(st,pid):return next(team[0] for team in st['teams'] if pid in team)
def board(st,pid):return st['boards'][board_id(st,pid)]
def heat(b,room=None):
    d=distance(b['room'] if room is None else room,b['hidden_room']);return 'caliente' if d==0 else 'tibio' if d==1 else 'frío'
def observe(b):
    if b['room'] not in b['visited']:b['visited'].append(b['room'])
    b['history'][b['room']]=heat(b)
def next_toy(st,b):
    r=random.Random(b['variant_seed']+b['score']*7919);choices=[n for n in range(6) if n!=b.get('last_found')];b['hidden_room']=r.choice(choices);b['toy']=random.Random(st['seed']).sample(TOYS,6)[b['score']%6];b['room']=0;b['steps']=0;b['visited']=[];b['checked']=[];b['history']={};observe(b)

def clues(b):return 'Buscá el muñeco '+b['toy']+'. Estás en '+ROOMS[b['room']]+': '+heat(b)+'. Puertas a '+', '.join(ROOMS[q] for q in LINKS[b['room']])+'. '+str(b['lives'])+' vidas; '+str(b['score'])+' de tres hallazgos; '+str(b['steps'])+' de doce pasos en este intento.'+(' Lugares revisados sin hallazgo: '+', '.join(ROOMS[q] for q in b['checked'])+'.' if b['checked'] else '')

def public_board(b):
    return {k:b[k] for k in ('room','toy','lives','score','steps','attempts','done','reason','visited','checked','history','last_found')}|{'heat':heat(b),'clues':clues(b),'doors':list(LINKS[b['room']])}

def actions(st,pid):return list(LINKS[board(st,pid)['room']])+['buscar'] if st['turn']==pid and st['winner'] is None and not board(st,pid)['done'] else []

def play(st,pid,move):
    if move not in actions(st,pid):raise ValueError('Acción fuera de turno')
    b=board(st,pid);caught=b['toy'];searched=move=='buscar';found=False;revealed=None
    if not searched:b['room']=move;b['steps']+=1;observe(b);searched=b['steps']>=12
    if searched:
        b['attempts']+=1;found=b['room']==b['hidden_room']
        if found:
            revealed=b['room'];b['last_found']=revealed;b['score']+=1;b['lives']=min(6,b['lives']+1);b['done']=b['score']>=3;b['reason']='Tres muñecos encontrados' if b['done'] else ''
        else:
            if b['room'] not in b['checked']:b['checked'].append(b['room'])
            b['lives']-=1;b['done']=b['lives']==0;b['reason']='Sin vidas' if b['done'] else ''
        if not b['done']:
            if found:next_toy(st,b)
            else:b['room']=0;b['steps']=0;observe(b)
    st['seq']+=1;active=[p for p in st['seats'] if not board(st,p)['done']]
    if not active:
        best=max(b['score'] for b in st['boards'].values());st['winner']=[p for p in st['seats'] if board(st,p)['score']==best]
    else:
        start=st['seats'].index(pid);st['turn']=next(st['seats'][(start+i)%len(st['seats'])] for i in range(1,len(st['seats'])+1) if st['seats'][(start+i)%len(st['seats'])] in active)
    return {'searched':searched,'found':found,'revealed':revealed,'done':b['done'],'toy':caught}

def choose_move(st,pid,level=2,rng=None):
    """Bots consume the same observable history as humans, never hidden_room or seed."""
    rng=rng or random;b=public_board(board(st,pid));room=b['room'];doors=b['doors']
    if level==0 and rng.random()<.6:return rng.choice(doors+['buscar'])
    if b['heat']=='caliente':return 'buscar'
    if level==1:return rng.choice(doors)
    # Walk to an unvisited room using public map and history, not hidden location.
    front=[(room,[])];seen={room}
    while front:
        cur,path=front.pop(0)
        if cur not in b['visited']:return path[0]
        for q in LINKS[cur]:
            if q not in seen:seen.add(q);front.append((q,path+[q]))
    return rng.choice(doors)
