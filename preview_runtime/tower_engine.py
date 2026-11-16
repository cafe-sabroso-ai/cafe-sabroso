"""Original probabilistic wooden tower. Transparent risk model, not real physics."""
import random
POS=('izquierda','centro','derecha')

def new_game(seats):
    if len(seats)<2 or len(seats)>20 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
    return {'seats':list(seats),'turn':seats[0],'layers':[[True]*3 for _ in range(12)],'moves':[],'successes':{p:0 for p in seats},'winner':None,'loser':None,'collapsed':False,'result':''}

def legal_moves(st):
    if st['winner'] is not None:return []
    highest=max(i for i,row in enumerate(st['layers']) if all(row))
    return [(i,j) for i,row in enumerate(st['layers'][:highest]) for j,present in enumerate(row) if present]

def risk(st,layer,pos):
    if (layer,pos) not in legal_moves(st):raise ValueError('Bloque no disponible')
    row=st['layers'][layer];remaining=sum(row)-1
    weakness=.4 if remaining==0 else .12 if remaining==1 else .02
    # Center-only supports better than a single side. Neighbor gaps and height add risk.
    if remaining==1 and pos!=1 and row[1]:weakness-=.05
    neighbors=sum(3-sum(st['layers'][i]) for i in (layer-1,layer+1) if 0<=i<len(st['layers']))
    return min(.9,.02+weakness+neighbors*.02+len(st['moves'])*.003+(len(st['layers'])-12)*.004)

def risk_name(chance):return 'bajo' if chance<.12 else 'medio' if chance<.3 else 'alto'

def play(st,pid,layer,pos,rng=None):
    if st['turn']!=pid or st['winner'] is not None:raise ValueError('Fuera de turno')
    chance=risk(st,layer,pos);rng=rng or random;fallen=rng.random()<chance
    move={'pid':pid,'layer':layer,'pos':pos,'risk':chance,'collapsed':fallen};st['moves'].append(move);st['layers'][layer][pos]=False
    if fallen:
        st['collapsed']=True;st['loser']=pid;st['winner']=[p for p in st['seats'] if p!=pid]
    else:
        st['successes'][pid]+=1
        if all(st['layers'][-1]):st['layers'].append([False]*3)
        target=st['layers'][-1].index(False);st['layers'][-1][target]=True;move['placed_layer']=len(st['layers'])-1;move['placed_pos']=target
        st['turn']=st['seats'][(st['seats'].index(pid)+1)%len(st['seats'])]
        if not legal_moves(st):st['winner']=list(st['seats']);st['result']='No quedan bloques legales: empate.'
    return move

def choose_move(st,level=2,rng=None):
    rng=rng or random;moves=legal_moves(st)
    if not moves:return None
    if level==0:return rng.choice(moves)
    # Risk uses public gaps, not a future random roll.
    ranked=sorted(moves,key=lambda m:risk(st,*m));pool=ranked[:max(1,len(ranked)//(level+1))];return rng.choice(pool)
