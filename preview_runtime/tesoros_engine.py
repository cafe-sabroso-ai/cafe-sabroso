"""Three hidden treasures, coarse public temperature clues and private search boards."""
import random
SIZE=5
LIMIT=50
MOVES={'arriba':(-1,0),'derecha':(0,1),'abajo':(1,0),'izquierda':(0,-1)}
def distance(a,b):return abs(a//SIZE-b//SIZE)+abs(a%SIZE-b%SIZE)
def heat(d):return 'caliente' if d<=1 else 'tibio' if d<=3 else 'frío'
def new_game(seats,mode='individual',seed=None):
 if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Configuración inválida')
 seed=seed if seed is not None else random.randrange(1<<30);teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
 st={'seats':list(seats),'teams':teams,'mode':mode,'seed':seed,'targets':random.Random(seed).sample([x for x in range(25) if x!=12],3),'boards':{},'turn':seats[0],'winner':None,'seq':0,'result':''}
 for t in teams:
  b={'pos':12,'actions':0,'score':0,'done':False,'found':[],'history':[],'visited':[12],'dug':[]};b['heat']=heat(distance(12,st['targets'][0]));b['history']=[{'pos':12,'heat':b['heat']}];st['boards'][t[0]]=b
 return st

def team(st,p):return next(t for t in st['teams'] if p in t)
def board(st,p):return st['boards'][team(st,p)[0]]
def public_board(st,b):return {k:b[k] for k in ('pos','actions','score','done','heat')}|{'found':list(b['found']),'visited':list(b['visited']),'dug':list(b['dug']),'history':[dict(h) for h in b['history']]}

def move(st,p,action=None,timeout=False):
 if st['winner'] is not None or st['turn']!=p or board(st,p)['done']:raise ValueError('Fuera de turno')
 if not timeout and action not in (*MOVES,'excavar'):raise ValueError('Acción inválida')
 b=board(st,p);b['actions']+=1;found=False;bump=False
 if not timeout:
  if action in MOVES:
   dr,dc=MOVES[action];r,c=divmod(b['pos'],5);r+=dr;c+=dc
   if 0<=r<5 and 0<=c<5:b['pos']=r*5+c
   else:bump=True
  elif b['pos']==st['targets'][b['score']]:b['found'].append(b['pos']);b['score']+=1;found=True;b['history']=[];b['dug']=[]
  elif b['pos'] not in b['dug']:b['dug'].append(b['pos'])
 if b['pos'] not in b['visited']:b['visited'].append(b['pos'])
 b['done']=b['score']==3 or b['actions']>=LIMIT
 if b['score']<3:
  b['heat']=heat(distance(b['pos'],st['targets'][b['score']]));b['history'].append({'pos':b['pos'],'heat':b['heat']})
 else:b['heat']='completo'
 st['seq']+=1;live=[q for q in st['seats'] if not board(st,q)['done']]
 if not live:
  best=max(b['score'] for b in st['boards'].values());st['winner']=[q for q in st['seats'] if board(st,q)['score']==best]
 else:
  i=st['seats'].index(p);st['turn']=next(st['seats'][(i+k)%len(st['seats'])] for k in range(1,len(st['seats'])+1) if st['seats'][(i+k)%len(st['seats'])] in live)
 return {'found':found,'bump':bump,'timeout':timeout,'done':b['done']}

def candidates(view):return [cell for cell in range(25) if cell not in view['found'] and cell not in view['dug'] and all(heat(distance(cell,h['pos']))==h['heat'] for h in view['history'])]
def choose(st,p,level=2,rng=None):
 """Only public coarse clues, search history and excavations are used."""
 rng=rng or random;v=public_board(st,board(st,p));possible=candidates(v);target=min(possible,key=lambda x:distance(v['pos'],x)) if possible else v['pos'];delta=(target//5-v['pos']//5,target%5-v['pos']%5)
 action='excavar' if target==v['pos'] else 'arriba' if delta[0]<0 else 'abajo' if delta[0]>0 else 'izquierda' if delta[1]<0 else 'derecha'
 return rng.choice([*MOVES,'excavar']) if rng.random()<(0.12,.04,0)[max(0,min(2,level))] else action
