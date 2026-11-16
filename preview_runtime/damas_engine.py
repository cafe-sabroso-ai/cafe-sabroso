"""Damas 8x8: variante corta, captura obligatoria, damas de un paso.

Coordinates are a1..h8; light men move toward rank 8, dark toward rank 1.
No external package, artwork or network access.
"""
import re

FILES = 'abcdefgh'
NUMBERS = {'uno':'1','dos':'2','tres':'3','cuatro':'4','cinco':'5','seis':'6','siete':'7','ocho':'8'}
LETTERS = {'a':'a','be':'b','b':'b','ce':'c','c':'c','de':'d','d':'d','e':'e','efe':'f','f':'f','ge':'g','g':'g','hache':'h','h':'h'}


def coords(square):
    if not isinstance(square,str) or not re.fullmatch('[a-h][1-8]',square):
        raise ValueError('Casilla inválida')
    return FILES.index(square[0]),int(square[1])-1


def square(x,y):
    return FILES[x]+str(y+1) if 0<=x<8 and 0<=y<8 else None


def side(piece):
    return piece.lower() if piece else None


def new_game():
    board={}
    for y in range(8):
        for x in range(8):
            if (x+y)%2==0 and (y<3 or y>4):
                board[square(x,y)]='w' if y<3 else 'b'
    state={'board':board,'turn':'w','forced':None,'winner':None,'draw':False,
           'quiet':0,'ply':0,'history':{},'last':None}
    remember(state)
    return state


def key(state):
    return (state['turn'],tuple(sorted(state['board'].items())))


def remember(state):
    k=key(state)
    state['history'][k]=state['history'].get(k,0)+1
    if state['history'][k]>=3:
        state['draw']=True


def piece_moves(state,origin,captures_only=False):
    board=state['board'];piece=board.get(origin)
    if not piece:return []
    x,y=coords(origin)
    directions=[(dx,dy) for dx in (-1,1) for dy in (-1,1)] if piece.isupper() else [(dx,1 if piece=='w' else -1) for dx in (-1,1)]
    result=[]
    for dx,dy in directions:
        step=square(x+dx,y+dy)
        if not step:continue
        target=board.get(step)
        if not target and not captures_only:
            result.append((origin,step,None))
        elif target and side(target)!=side(piece):
            landing=square(x+2*dx,y+2*dy)
            if landing and landing not in board:result.append((origin,landing,step))
    return result


def legal_moves(state):
    if state.get('winner') or state.get('draw'):return []
    if state['forced']:
        return piece_moves(state,state['forced'],True)
    moves=[m for origin,p in state['board'].items() if side(p)==state['turn'] for m in piece_moves(state,origin)]
    captures=[m for m in moves if m[2]]
    return captures or moves


def apply_move(state,origin,dest):
    if state.get('winner') or state.get('draw'):raise ValueError('La partida terminó')
    legal=legal_moves(state)
    move=next((m for m in legal if m[:2]==(origin,dest)),None)
    if move is None:
        if state.get('forced'):raise ValueError('Tenés que seguir capturando con la misma ficha')
        if any(m[2] for m in legal):raise ValueError('Hay captura obligatoria: elegí una de las capturas indicadas')
        raise ValueError('Esa jugada no es válida: mové una casilla en diagonal hacia adelante')
    board=state['board'];piece=board.pop(origin);captured=move[2]
    if captured:board.pop(captured)
    promoted=piece.islower() and (dest[1]=='8' if piece=='w' else dest[1]=='1')
    if promoted:piece=piece.upper()
    board[dest]=piece
    state['last']={'from':origin,'to':dest,'captured':captured,'promoted':promoted}
    state['quiet']=0 if captured or promoted else state['quiet']+1
    if captured and not promoted and piece_moves(state,dest,True):
        state['forced']=dest
        return dict(state['last'],again=True)
    state['forced']=None
    state['turn']='b' if state['turn']=='w' else 'w'
    state['ply']+=1
    if not any(side(p)==state['turn'] for p in board.values()) or not legal_moves(state):
        state['winner']='b' if state['turn']=='w' else 'w'
    elif state['quiet']>=80:
        state['draw']=True
    else:remember(state)
    return dict(state['last'],again=False)


def parse_move(text):
    text=str(text).lower().strip()
    # Direct coordinates and spoken letters/numbers, including "de c tres a d cuatro".
    tokens=re.findall('[a-záéíóúñ]+|[0-9]+',text)
    compact=re.findall(r'(?<![a-z])[a-h][1-8](?![0-9])',text)
    if len(compact)==2:return tuple(compact)
    result=[]
    for i in range(len(tokens)-1):
        if tokens[i] in LETTERS:
            n=NUMBERS.get(tokens[i+1],tokens[i+1])
            if n in '12345678' and len(n)==1:
                result.append(LETTERS[tokens[i]]+n)
    return tuple(result) if len(result)==2 else None


def choose_move(state):
    moves=legal_moves(state)
    if not moves:return None
    # Material-aware two-ply opponent response, deterministic tie break.
    import copy
    us=state['turn']
    def evaluate(st):
        if st['winner']:return 10000 if st['winner']==us else -10000
        return sum((3 if p.isupper() else 1)*(1 if side(p)==us else -1) for p in st['board'].values())
    def score(move):
        st=copy.deepcopy(state);apply_move(st,*move[:2])
        if st['turn']==us or st['winner'] or st['draw']:return evaluate(st)
        replies=[]
        for reply in legal_moves(st):
            test=copy.deepcopy(st);apply_move(test,*reply[:2]);replies.append(evaluate(test))
        return min(replies,default=evaluate(st))
    return max(moves,key=lambda m:(score(m),bool(m[2]),m[1]))
