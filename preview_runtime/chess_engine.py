"""Original local chess rules. Coordinates a1=0. No external assets/engines."""
import copy,random
FILES='abcdefgh'
VALUES={'p':100,'n':320,'b':330,'r':500,'q':900,'k':0}

def square(text):
    text=str(text).lower().strip()
    if len(text)!=2 or text[0] not in FILES or text[1] not in '12345678':raise ValueError('Casilla inválida')
    return FILES.index(text[0])+8*(int(text[1])-1)

def label(s):return FILES[s%8]+str(s//8+1)
def side(p):return 'w' if p.isupper() else 'b'
def enemy(c):return 'b' if c=='w' else 'w'

def new_game(seats):
    if len(seats)!=2 or len(set(seats))!=2:raise ValueError('Dos jugadores distintos requeridos')
    board=list('RNBQKBNR'+'PPPPPPPP'+'.'*32+'pppppppp'+'rnbqkbnr')
    st={'seats':list(seats),'board':board,'color':'w','turn':seats[0],'castling':'KQkq','ep':None,'halfmove':0,'fullmove':1,'history':[],'repetitions':{},'winner':None,'draw':False,'result':''}
    st['repetitions'][position_key(st)]=1;return st

def position_key(st):
    ep=st['ep']
    if ep is not None and not any(m[1]==ep and st['board'][m[0]].lower()=='p' for m in legal_moves(st)):ep=None
    return ''.join(st['board'])+' '+st['color']+' '+st['castling']+' '+str(ep)

def attacked(st,target,by):
    b=st['board'];tx,ty=target%8,target//8
    for i,p in enumerate(b):
        if p=='.' or side(p)!=by:continue
        x,y=i%8,i//8;dx,dy=tx-x,ty-y;k=p.lower()
        if k=='p' and abs(dx)==1 and dy==(1 if by=='w' else -1):return True
        if k=='n' and (abs(dx),abs(dy)) in ((1,2),(2,1)):return True
        if k=='k' and max(abs(dx),abs(dy))==1:return True
        if k in 'brq' and (k in 'bq' and abs(dx)==abs(dy) and dx!=0 or k in 'rq' and ((dx==0)!=(dy==0))):
            sx=(dx>0)-(dx<0);sy=(dy>0)-(dy<0);cx,cy=x+sx,y+sy
            while (cx,cy)!=(tx,ty) and b[cx+cy*8]=='.':cx+=sx;cy+=sy
            if (cx,cy)==(tx,ty):return True
    return False

def in_check(st,color=None):
    c=color or st['color'];king='K' if c=='w' else 'k'
    return king not in st['board'] or attacked(st,st['board'].index(king),enemy(c))

def pseudo(st):
    b=st['board'];c=st['color'];moves=[]
    def add(i,j):
        if b[j]!='.' and (side(b[j])==c or b[j].lower()=='k'):return
        if b[i].lower()=='p' and j//8 in (0,7):moves.extend((i,j,q) for q in 'qrbn')
        else:moves.append((i,j,''))
    for i,p in enumerate(b):
        if p=='.' or side(p)!=c:continue
        x,y=i%8,i//8;k=p.lower()
        if k=='p':
            d=1 if c=='w' else -1;ny=y+d
            if 0<=ny<8:
                j=x+ny*8
                if b[j]=='.':
                    add(i,j)
                    if y==(1 if c=='w' else 6) and b[i+16*d]=='.':add(i,i+16*d)
                for nx in (x-1,x+1):
                    if 0<=nx<8:
                        j=nx+ny*8
                        if b[j]!='.' and side(b[j])!=c or j==st['ep']:add(i,j)
        elif k in 'nk':
            deltas=((1,2),(2,1),(-1,2),(-2,1),(1,-2),(2,-1),(-1,-2),(-2,-1)) if k=='n' else tuple((dx,dy) for dx in (-1,0,1) for dy in (-1,0,1) if dx or dy)
            for dx,dy in deltas:
                nx,ny=x+dx,y+dy
                if 0<=nx<8 and 0<=ny<8:add(i,nx+ny*8)
            if k=='k' and i==(4 if c=='w' else 60) and not in_check(st,c):
                for right,rook,path,dest in ((('K' if c=='w' else 'k'),i+3,(i+1,i+2),i+2),(('Q' if c=='w' else 'q'),i-4,(i-1,i-2,i-3),i-2)):
                    if right in st['castling'] and b[rook]==('R' if c=='w' else 'r') and all(b[q]=='.' for q in path) and not any(attacked(st,q,enemy(c)) for q in path[:2]):add(i,dest)
        else:
            directions=[]
            if k in 'bq':directions += [(1,1),(1,-1),(-1,1),(-1,-1)]
            if k in 'rq':directions += [(1,0),(-1,0),(0,1),(0,-1)]
            for dx,dy in directions:
                nx,ny=x+dx,y+dy
                while 0<=nx<8 and 0<=ny<8:
                    j=nx+ny*8;add(i,j)
                    if b[j]!='.':break
                    nx+=dx;ny+=dy
    return moves

def apply(st,move):
    i,j,prom=move;s={**st,'board':list(st['board'])};b=s['board'];p=b[i];capture=b[j]!='.';c=st['color']
    if p.lower()=='p' and j==st['ep'] and b[j]=='.':b[j+(-8 if c=='w' else 8)]='.';capture=True
    b[j]=prom.upper() if prom and c=='w' else prom if prom else p;b[i]='.'
    if p.lower()=='k' and abs(i-j)==2:
        r=i+3 if j>i else i-4;dest=i+1 if j>i else i-1;b[dest]=b[r];b[r]='.'
    rights=st['castling']
    for origin,chars in ((4,'KQ'),(60,'kq'),(0,'Q'),(7,'K'),(56,'q'),(63,'k')):
        if i==origin or j==origin:
            for ch in chars:rights=rights.replace(ch,'')
    s.update(castling=rights,ep=(i+j)//2 if p.lower()=='p' and abs(i-j)==16 else None,halfmove=0 if capture or p.lower()=='p' else st['halfmove']+1,fullmove=st['fullmove']+(c=='b'),color=enemy(c))
    s['turn']=s['seats'][0 if s['color']=='w' else 1];return s

def legal_moves(st):return [m for m in pseudo(st) if not in_check(apply(st,m),st['color'])]

def insufficient(st):
    pieces=[(i,p.lower()) for i,p in enumerate(st['board']) if p not in '.Kk']
    if not pieces:return True
    if len(pieces)==1 and pieces[0][1] in 'bn':return True
    return bool(pieces) and all(p=='b' for i,p in pieces) and len({(i%8+i//8)%2 for i,p in pieces})==1

def play(st,pid,origin,dest,promotion='q'):
    if st['winner'] is not None or st['draw'] or st['turn']!=pid:raise ValueError('Fuera de turno')
    i=square(origin);j=square(dest);moves=legal_moves(st);move=(i,j,promotion.lower() if st['board'][i].lower()=='p' and j//8 in (0,7) else '')
    if move not in moves:raise ValueError('Movimiento ilegal')
    old_color=st['color'];piece=st['board'][i];captured=st['board'][j];next_st=apply(st,move);st.update(next_st)
    st['history'].append({'pid':pid,'from':label(i),'to':label(j),'promotion':move[2],'piece':piece,'captured':captured})
    key=position_key(st);st['repetitions'][key]=st['repetitions'].get(key,0)+1
    possible=legal_moves(st);check=in_check(st)
    if not possible:
        if check:st['winner']=[pid];st['result']='Jaque mate.'
        else:st['draw']=True;st['result']='Tablas por ahogado.'
    elif insufficient(st):st['draw']=True;st['result']='Tablas por material insuficiente.'
    elif st['repetitions'][key]>=3:st['draw']=True;st['result']='Tablas automáticas por triple repetición en esta sala.'
    elif st['halfmove']>=100:st['draw']=True;st['result']='Tablas automáticas por cincuenta jugadas sin captura ni movimiento de peón.'
    else:st['result']='Jaque.' if check else 'Movimiento realizado.'
    return st['history'][-1]

def choose_move(st,level=2,rng=None):
    rng=rng or random;moves=legal_moves(st)
    if not moves:return None
    if level<1:return rng.choice(moves)
    def score(m):
        nxt=apply(st,m);replies=legal_moves(nxt)
        if not replies:return 100000 if in_check(nxt) else 0
        total=sum((1 if side(p)==st['color'] else -1)*VALUES[p.lower()] for p in nxt['board'] if p!='.')
        if level>=3:
            # One reply lookahead, public board only. Bounded CPU, no expert claim.
            total=min(sum((1 if side(p)==st['color'] else -1)*VALUES[p.lower()] for p in apply(nxt,r)['board'] if p!='.') for r in replies)
        return total+(20 if in_check(nxt) else 0)+rng.random()*max(1,30-level*5)
    return max(moves,key=score)
