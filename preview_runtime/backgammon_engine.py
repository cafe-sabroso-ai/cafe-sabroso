"""Backgammon sin apuestas, cubo ni dinero. Blancas bajan del 24 al 1.
Movimientos legales maximizan el uso de dados; entrada, golpes y salida incluidos.
"""
from functools import lru_cache
import re, random


def new_game():
    points=[0]*25
    for p,n in [(24,2),(13,5),(8,3),(6,5),(1,-2),(12,-5),(17,-3),(19,-5)]:points[p]=n
    return {'points':points,'bar':{'w':0,'b':0},'off':{'w':0,'b':0},
            'turn':'w','dice':[],'rolled':False,'winner':None,'last':None}


def opening(st,white,black):
    if white==black:raise ValueError('Empate en la salida: repetí los dados')
    if any(type(d) is not int or d not in range(1,7) for d in (white,black)):raise ValueError('Dado inválido')
    st['turn']='w' if white>black else 'b';st['dice']=[white,black];st['rolled']=True


def roll(st,dice):
    if st['winner'] or st['rolled']:raise ValueError('No corresponde tirar dados ahora')
    if len(dice)!=2 or any(type(d) is not int or d not in range(1,7) for d in dice):raise ValueError('Dados inválidos')
    st['dice']=list(dice)*2 if dice[0]==dice[1] else list(dice);st['rolled']=True


def pack(st):
    return tuple(st['points']),st['bar']['w'],st['bar']['b'],st['off']['w'],st['off']['b'],tuple(sorted(st['dice'])),st['turn']


def atomic(pos,die):
    points,bw,bb,ow,ob,dice,turn=pos;sign=1 if turn=='w' else -1
    bar=bw if turn=='w' else bb
    origins=[0] if bar else [i for i in range(1,25) if points[i]*sign>0]
    home=not bar and all(not points[i]*sign>0 for i in (range(7,25) if turn=='w' else range(1,19)))
    result=[]
    for origin in origins:
        dest=(25-die if turn=='w' else die) if origin==0 else origin-sign*die
        if 1<=dest<=24:
            if points[dest]*sign>=-1:result.append((origin,dest,die))
        elif home:
            exact=(dest==0 if turn=='w' else dest==25)
            behind=any(points[i]*sign>0 for i in (range(origin+1,7) if turn=='w' else range(19,origin)))
            if exact or not behind:result.append((origin,25,die))
    return result


def advance(pos,move):
    points,bw,bb,ow,ob,dice,turn=pos;points=list(points);dice=list(dice);origin,dest,die=move
    sign=1 if turn=='w' else -1
    if origin==0:
        if turn=='w':bw-=1
        else:bb-=1
    else:points[origin]-=sign
    if dest==25:
        if turn=='w':ow+=1
        else:ob+=1
    else:
        if points[dest]==-sign:
            points[dest]=0
            if turn=='w':bb+=1
            else:bw+=1
        points[dest]+=sign
    dice.remove(die)
    return tuple(points),bw,bb,ow,ob,tuple(dice),turn


def legal_moves(st):
    if st['winner'] or not st['rolled'] or not st['dice']:return []
    pos=pack(st)
    @lru_cache(maxsize=None)
    def depth(p):
        if p[3]>=15 or p[4]>=15:return 0
        moves=[m for d in set(p[5]) for m in atomic(p,d)]
        return max((1+depth(advance(p,m)) for m in moves),default=0)
    best=depth(pos)
    moves=[m for d in sorted(set(pos[5]),reverse=True) for m in atomic(pos,d) if 1+depth(advance(pos,m))==best or advance(pos,m)[3]>=15 or advance(pos,m)[4]>=15]
    if best==1 and len(pos[5])==2 and pos[5][0]!=pos[5][1] and moves:
        highest=max(m[2] for m in moves);moves=[m for m in moves if m[2]==highest]
    return moves


def apply_move(st,origin,dest,die):
    move=(origin,dest,die)
    if move not in legal_moves(st):raise ValueError('Jugada inválida: usá una de las jugadas legales indicadas')
    hit=dest!=25 and st['points'][dest]==(-1 if st['turn']=='w' else 1)
    pos=advance(pack(st),move)
    st['points']=list(pos[0]);st['bar']={'w':pos[1],'b':pos[2]};st['off']={'w':pos[3],'b':pos[4]};st['dice']=list(pos[5])
    st['last']={'from':origin,'to':dest,'die':die,'hit':hit}
    if st['off'][st['turn']]==15:st['winner']=st['turn']
    return st['last']


def finish_turn(st):
    if st['winner'] or not st['rolled'] or legal_moves(st):raise ValueError('Todavía quedan jugadas legales')
    st['dice']=[];st['rolled']=False;st['turn']='b' if st['turn']=='w' else 'w'


WORDS={'uno':1,'dos':2,'tres':3,'cuatro':4,'cinco':5,'seis':6,'siete':7,'ocho':8,'nueve':9,'diez':10,'once':11,'doce':12,'trece':13,'catorce':14,'quince':15,'dieciseis':16,'dieciséis':16,'diecisiete':17,'dieciocho':18,'diecinueve':19,'veinte':20,'veintiuno':21,'veintidos':22,'veintidós':22,'veintitres':23,'veintitrés':23,'veinticuatro':24,'barra':0,'afuera':25,'fuera':25,'salida':25}

def parse_move(text,st):
    tokens=re.findall(r'[0-9]+|[a-záéíóúñ]+',str(text).lower())
    nums=[int(t) if t.isdigit() else WORDS[t] for t in tokens if t.isdigit() or t in WORDS]
    legal=legal_moves(st)
    if len(nums)==1 and 1<=nums[0]<=len(legal) and any(t in tokens for t in ('jugada','opcion','opción')):return legal[nums[0]-1]
    if len(nums) not in (2,3):return None
    candidates=[m for m in legal if m[:2]==tuple(nums[:2]) and (len(nums)==2 or m[2]==nums[2])]
    return candidates[0] if len(candidates)==1 else None


def choose_move(st):
    moves=legal_moves(st)
    if not moves:return None
    sign=1 if st['turn']=='w' else -1
    def score(m):
        pos=advance(pack(st),m);points=pos[0]
        return (100 if m[1]==25 else 0)+(30 if m[1]!=25 and st['points'][m[1]]==-sign else 0)+sum(3 for n in points[1:] if n*sign>=2)-sum(2 for n in points[1:] if n*sign==1)
    return max(moves,key=score)
