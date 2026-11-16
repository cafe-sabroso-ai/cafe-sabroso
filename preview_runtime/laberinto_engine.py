"""Private perfect maze; each team discovers local corridors. No bot sees unseen cells."""
import random
DIRS=[(-1,0),(0,1),(1,0),(0,-1)]
HEADINGS=['norte','este','sur','oeste']
MOVES=('izquierda','derecha','avanzar')
SIZE=5
LIMIT=100

def neighbor(cell,d):
 r,c=divmod(cell,SIZE);dr,dc=DIRS[d];r+=dr;c+=dc
 return r*SIZE+c if 0<=r<SIZE and 0<=c<SIZE else None

def maze(seed):
 rng=random.Random(seed);edges={i:[] for i in range(SIZE*SIZE)};seen={0};stack=[0]
 while stack:
  cell=stack[-1];options=[(d,neighbor(cell,d)) for d in range(4) if neighbor(cell,d) is not None and neighbor(cell,d) not in seen]
  if not options:stack.pop();continue
  d,n=rng.choice(options);edges[cell].append(d);edges[n].append((d+2)%4);seen.add(n);stack.append(n)
 return edges

def new_game(seats,mode='individual',seed=None):
 if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Configuración inválida')
 seed=seed if seed is not None else random.randrange(1<<30);teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
 st={'seats':list(seats),'teams':teams,'mode':mode,'seed':seed,'layout':maze(seed),'boards':{},'turn':seats[0],'winner':None,'seq':0,'result':''}
 for t in teams:st['boards'][t[0]]={'pos':0,'heading':1,'actions':0,'done':False,'escaped':False,'known':{0:list(st['layout'][0])},'bumps':0}
 return st

def team(st,p):return next(t for t in st['teams'] if p in t)
def board(st,p):return st['boards'][team(st,p)[0]]
def public_board(st,b):return {k:b[k] for k in ('pos','heading','actions','done','escaped','bumps')}|{'known':{str(c):list(exits) for c,exits in b['known'].items()}}
def local_cues(b):
 exits=b['known'].get(b['pos'],b['known'].get(str(b['pos']),[]))
 return {name:(b['heading']+offset)%4 in exits for name,offset in (('adelante',0),('derecha',1),('atrás',2),('izquierda',3))}

def move(st,p,action=None,timeout=False):
 if st['winner'] is not None or st['turn']!=p or board(st,p)['done']:raise ValueError('Fuera de turno')
 if not timeout and action not in MOVES:raise ValueError('Movimiento inválido')
 b=board(st,p);b['actions']+=1;bump=False
 if not timeout:
  if action in ('izquierda','derecha'):b['heading']=(b['heading']+(-1 if action=='izquierda' else 1))%4
  elif b['heading'] in st['layout'][b['pos']]:b['pos']=neighbor(b['pos'],b['heading']);b['known'][b['pos']]=list(st['layout'][b['pos']])
  else:bump=True;b['bumps']+=1
 b['escaped']=b['pos']==SIZE*SIZE-1;b['done']=b['escaped'] or b['actions']>=LIMIT;st['seq']+=1
 live=[q for q in st['seats'] if not board(st,q)['done']]
 if not live:
  escaped=[q for q in st['seats'] if board(st,q)['escaped']];best=min((board(st,q)['actions'] for q in escaped),default=None);st['winner']=[q for q in escaped if board(st,q)['actions']==best]
 else:
  i=st['seats'].index(p);st['turn']=next(st['seats'][(i+k)%len(st['seats'])] for k in range(1,len(st['seats'])+1) if st['seats'][(i+k)%len(st['seats'])] in live)
 return {'bump':bump,'timeout':timeout,'escaped':b['escaped'],'done':b['done'],'actions':b['actions']}

def choose(st,p,level=2,rng=None):
 """BFS to a frontier using visited-cell exits only; no layout or seed access."""
 rng=rng or random;b=public_board(st,board(st,p));known={int(k):v for k,v in b['known'].items()};queue=[(b['pos'],[])];seen={b['pos']};path=[]
 for cell,route in queue:
  if cell not in known:path=route;break
  for d in known[cell]:
   n=neighbor(cell,d)
   if n is not None and n not in seen:seen.add(n);queue.append((n,route+[d]))
 if not path:return 'derecha'
 target=path[0];delta=(target-b['heading'])%4;action='avanzar' if delta==0 else 'izquierda' if delta==3 else 'derecha'
 return rng.choice(MOVES) if rng.random()<(0.1,.025,0)[max(0,min(2,level))] else action
