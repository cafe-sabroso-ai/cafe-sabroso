"""Original rule engines. No networking, hidden-information-safe bot inputs."""
from collections import Counter
import random
SPANISH=('oros','copas','espadas','bastos')
FRENCH=('corazones','diamantes','tréboles','picas')
RANK_ES={1:'as',10:'sota',11:'caballo',12:'rey'}
RANK_FR={11:'jota',12:'reina',13:'rey',14:'as'}
POINTS={1:11,3:10,12:4,11:3,10:2}
STRENGTH={rank:i for i,rank in enumerate((2,4,5,6,7,10,11,12,3,1))}
TITLES={'brisca':'Brisca del Café','guerra':'Guerra de Cartas','pesca':'Pesca de Cartas'}

def name(card,game):
 r,s=card
 return str((RANK_ES if game=='brisca' else RANK_FR).get(r,r))+' de '+s

def deck(game):return [(r,s)for s in (SPANISH if game=='brisca' else FRENCH) for r in ((1,2,3,4,5,6,7,10,11,12)if game=='brisca' else range(2,15))]

def fresh(game,seats,seed=None):
 if game not in TITLES or len(set(seats))!=len(seats):raise ValueError('Juego o participantes inválidos.')
 n=len(seats)
 if n not in ((2,4)if game=='brisca' else (2,)if game=='guerra' else (2,3,4,5)):raise ValueError('Cantidad de participantes inválida.')
 rng=random.Random(seed);cards=deck(game);rng.shuffle(cards)
 st=dict(game=game,seats=list(seats),turn=seats[0],hands={p:[]for p in seats},phase='playing',seq=0,winners=[],reason='',result='Partida comenzada.',last=[],scores={p:0 for p in seats},taken={p:[]for p in seats},stock=[],trick=[],trump=None,books={p:[]for p in seats},round=0,pot=[],seen=set())
 if game=='guerra':
  for i,c in enumerate(cards):st['hands'][seats[i%2]].append(c)
  remember(st)
 else:
  count=3 if game=='brisca' else 7 if n<4 else 5
  for _ in range(count):
   for p in seats:st['hands'][p].append(cards.pop())
  if game=='brisca':
   st['trump']=cards[0];st['stock']=cards
  else:
   st['stock']=cards
   for p in seats:collect_books(st,p)
   fish_turn(st,seats[0])
 return st

def team(st,p):return st['seats'].index(p)%2 if st['game']=='brisca' and len(st['seats'])==4 else st['seats'].index(p)

def finish(st,winners,reason):st.update(phase='done',winners=list(winners),reason=reason,result=reason)

def brisca_winner(trick,trump):
 lead=trick[0][1][1]
 return max(trick,key=lambda pair:(2 if pair[1][1]==trump else 1 if pair[1][1]==lead else 0,STRENGTH[pair[1][0]]))[0]

def end_brisca(st):
 totals={t:sum(st['scores'][p]for p in st['seats']if team(st,p)==t)for t in set(team(st,p)for p in st['seats'])};high=max(totals.values());ws=[p for p in st['seats']if totals[team(st,p)]==high]
 finish(st,ws,'Brisca terminada. Se repartieron los 120 puntos. '+('Empate.'if len(set(totals.values()))==1 else 'Ganó el mayor puntaje.'))

def play_brisca(st,p,card):
 if card not in st['hands'][p]:raise ValueError('Esa carta no está en tu mano.')
 st['hands'][p].remove(card);st['trick'].append((p,card));st['result']='Carta jugada: '+name(card,'brisca')+'.'
 if len(st['trick'])<len(st['seats']):st['turn']=st['seats'][(st['seats'].index(p)+1)%len(st['seats'])];return
 winner=brisca_winner(st['trick'],st['trump'][1]);points=sum(POINTS.get(c[0],0)for _,c in st['trick']);st['scores'][winner]+=points;st['taken'][winner].extend(c for _,c in st['trick']);st['last']=list(st['trick']);st['trick']=[];st['round']+=1
 # Stock is a stack; the exposed trump was placed at the bottom and is last drawn.
 order=st['seats'][st['seats'].index(winner):]+st['seats'][:st['seats'].index(winner)]
 for q in order:
  if st['stock']:st['hands'][q].append(st['stock'].pop())
 st['turn']=winner;st['result']='Baza para persona '+str(st['seats'].index(winner)+1)+': '+str(points)+' puntos.'
 if not any(st['hands'].values()):end_brisca(st)

def war_key(st):return tuple(tuple(st['hands'][p])for p in st['seats'])
def remember(st):st['seen'].add(war_key(st))
def war_step(st):
 a,b=st['seats'];st['round']+=1;st['last']=[]
 while True:
  available=[p for p in (a,b)if st['hands'][p]]
  if len(available)<2:
   if available:
    winner=available[0];st['hands'][winner].extend(st['pot']);st['pot']=[];finish(st,[winner],'Guerra terminada: la otra persona no tiene cartas para seguir.')
   else:finish(st,[],'Empate: ambas personas se quedaron sin cartas durante la guerra.')
   return
  ca=st['hands'][a].pop(0);cb=st['hands'][b].pop(0);st['last'].extend([(a,ca),(b,cb)]);st['pot'].extend([ca,cb])
  if ca[0]!=cb[0]:
   winner=a if ca[0]>cb[0]else b
   st['hands'][winner].extend(st['pot']);won=len(st['pot']);st['pot']=[];st['result']='Persona '+str(st['seats'].index(winner)+1)+' recoge '+str(won)+' cartas.';break
  # One face-down card then another face-up. A last remaining card is face-up.
  for p in (a,b):
   if len(st['hands'][p])>1:st['pot'].append(st['hands'][p].pop(0))
  if not any(st['hands'].values()):finish(st,[],'Empate sin cartas en una guerra.');return
 if not st['hands'][a]or not st['hands'][b]:finish(st,[a if st['hands'][a]else b],'Guerra terminada: una persona reunió todas las cartas.');return
 if war_key(st)in st['seen']:finish(st,[],'Empate por repetición exacta de los dos mazos.');return
 if st['round']>=1000:finish(st,[],'Empate al llegar al límite de mil batallas.');return
 remember(st);st['turn']=st['seats'][st['round']%2]

def collect_books(st,p):
 counts=Counter(c[0]for c in st['hands'][p])
 for rank,n in counts.items():
  if n==4:
   st['books'][p].append(rank);st['taken'][p].extend(c for c in st['hands'][p]if c[0]==rank);st['hands'][p]=[c for c in st['hands'][p]if c[0]!=rank];st['scores'][p]+=1

def fish_turn(st,p):
 if sum(map(len,st['books'].values()))==13:
  high=max(st['scores'].values());finish(st,[q for q in st['seats']if st['scores'][q]==high],'Pesca terminada: se reunieron los trece cuartetos.');return
 start=st['seats'].index(p)
 for i in range(len(st['seats'])):
  q=st['seats'][(start+i)%len(st['seats'])]
  if not st['hands'][q]and st['stock']:st['hands'][q].append(st['stock'].pop());collect_books(st,q)
  if st['hands'][q]:st['turn']=q;return
 raise ValueError('Estado de pesca sin jugada legal.')

def ask_fish(st,p,target,rank):
 if target not in st['seats']or target==p or (not st['hands'][target]and not st['stock']):raise ValueError('Elegí una persona rival con cartas.')
 if type(rank)is not int or rank not in [c[0]for c in st['hands'][p]]:raise ValueError('Solo podés pedir un rango que ya tengas.')
 catch=[c for c in st['hands'][target]if c[0]==rank];st['last']=[]
 if catch:
  st['hands'][target]=[c for c in st['hands'][target]if c[0]!=rank];st['hands'][p].extend(catch);st['result']='Recibió '+str(len(catch))+' carta(s) del rango pedido. Conserva el turno.'
 else:
  draw=st['stock'].pop()if st['stock']else None
  if draw:st['hands'][p].append(draw)
  success=draw is not None and draw[0]==rank
  st['result']='¡A pescar! '+('Robó el rango pedido. Conserva el turno.'if success else 'Robó una carta privada. Cambia el turno.'if draw else 'No quedan cartas para robar. Cambia el turno.')
  catch=success
 st['last']=[(p,c)for c in catch]if isinstance(catch,list)else ([(p,draw)]if catch else [])
 st['result']='Persona '+str(st['seats'].index(p)+1)+' pidió '+str(RANK_FR.get(rank,rank))+' a persona '+str(st['seats'].index(target)+1)+'. '+st['result']
 collect_books(st,p);st['round']+=1
 nextp=p if catch else st['seats'][(st['seats'].index(p)+1)%len(st['seats'])];fish_turn(st,nextp)

def act(st,p,action):
 if st['phase']!='playing'or p!=st['turn']:raise ValueError('Esperá tu turno o empezá otra partida.')
 if not isinstance(action,dict):raise ValueError('Jugada inválida.')
 game=st['game']
 if game=='brisca':
  c=action.get('card');
  if not isinstance(c,list)or len(c)!=2 or type(c[0])is not int or not isinstance(c[1],str):raise ValueError('Carta inválida.')
  play_brisca(st,p,tuple(c))
 elif game=='guerra':
  if action.get('move')!='reveal':raise ValueError('Elegí dar vuelta las cartas.')
  war_step(st)
 else:ask_fish(st,p,action.get('target'),action.get('rank'))
 st['seq']+=1

def view(st,p):
 game=st['game']
 # No stock order, other hands, deck order, RNG seed or captured hidden cards.
 return dict(game=game,phase=st['phase'],turn=st['turn'],seq=st['seq'],round=st['round'],hand=[]if game=='guerra'else [list(c)for c in st['hands'].get(p,[])],counts={q:len(v)for q,v in st['hands'].items()},scores=st['scores'].copy(),books={q:list(v)for q,v in st['books'].items()},trump=list(st['trump'])if st['trump']else None,stock=len(st['stock']),trump_available=bool(st['stock'])if game=='brisca'else False,trick=[(q,list(c))for q,c in st['trick']],last=[(q,list(c))for q,c in st['last']],result=st['result'],winners=st['winners'][:],reason=st['reason'],team={q:team(st,q)for q in st['seats']})

def bot_move(public,rng=None):
 """Only the same hand/public state that a real player sees enters here."""
 rng=rng or random
 game=public['game']
 if game=='guerra':return {'move':'reveal'}
 hand=public['hand']
 if game=='brisca':return {'card':rng.choice(hand)}
 rank=rng.choice(hand)[0];choices=[q for q,n in public['counts'].items()if q!=public['turn']and (n>0 or public['stock']>0)]
 return {'target':rng.choice(choices),'rank':rank}
