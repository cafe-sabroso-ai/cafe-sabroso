"""Elimination RPS tournament, sealed sequential choices, first to two wins."""
import random
CHOICES=('piedra','papel','tijera')
BEATS={'piedra':'tijera','papel':'piedra','tijera':'papel'}

def new_game(seats,seed=None):
 if not 2<=len(seats)<=16 or len(set(seats))!=len(seats):raise ValueError('Se necesitan entre dos y dieciséis participantes')
 seed=seed if seed is not None else random.randrange(1<<30);order=list(seats);random.Random(seed).shuffle(order)
 st={'seats':list(seats),'seed':seed,'order':order,'round':1,'queue':[],'advancing':[],'duel':None,'turn':None,'winner':None,'seq':0,'history':[],'last_hand':None,'result':''};make_round(st,order);next_duel(st);return st

def make_round(st,seats):
 st['queue']=[seats[i:i+2] for i in range(0,len(seats),2)];st['advancing']=[]

def next_duel(st):
 while st['queue']:
  pair=st['queue'].pop(0)
  if len(pair)==1:st['advancing'].append(pair[0]);st['history'].append({'round':st['round'],'pair':pair,'winner':pair[0],'score':None,'hands':0,'reason':'pase libre'});continue
  st['duel']={'pair':pair,'score':{p:0 for p in pair},'hands':0,'choices':{}};st['turn']=pair[0];return
 if len(st['advancing'])==1:st['winner']=st['advancing'][0];st['turn']=None;return
 st['round']+=1;make_round(st,list(st['advancing']));next_duel(st)

def public(st,pid=None):
 d=st['duel'];pair=d['pair'];return {'round':st['round'],'turn':st['turn'],'winner':st['winner'],'seq':st['seq'],'pair':list(pair),'score':dict(d['score']),'hands':d['hands'],'pending':[p for p in pair if p in d['choices']],'own_choice':d['choices'].get(pid) if pid in d['choices'] else None,'own_submitted':pid in d['choices'],'history':[dict(h) for h in st['history']],'last_hand':dict(st['last_hand']) if st['last_hand'] else None,'queue':[list(p) for p in st['queue']],'advancing':list(st['advancing'])}

def play(st,p,choice=None,timeout=False):
 d=st['duel']
 if st['winner'] is not None or st['turn']!=p or p in d['choices']:raise ValueError('Fuera de turno')
 if not timeout and choice not in CHOICES:raise ValueError('Elección inválida')
 d['choices'][p]=None if timeout else choice;st['seq']+=1
 if len(d['choices'])==1:st['turn']=next(q for q in d['pair'] if q!=p);return {'resolved':False}
 a,b=d['pair'];ca,cb=d['choices'][a],d['choices'][b];winner=None
 if ca is None and cb is not None:winner=b
 elif cb is None and ca is not None:winner=a
 elif ca!=cb and ca is not None and cb is not None:winner=a if BEATS[ca]==cb else b
 if winner is not None:d['score'][winner]+=1
 d['hands']+=1;st['last_hand']={'pair':list(d['pair']),'choices':dict(d['choices']),'winner':winner,'hand':d['hands'],'score':dict(d['score'])};duel_winner=None;reason='dos victorias'
 if max(d['score'].values())>=2:duel_winner=max(d['pair'],key=lambda q:d['score'][q])
 elif d['hands']>=20:
  if d['score'][a]!=d['score'][b]:duel_winner=max(d['pair'],key=lambda q:d['score'][q]);reason='tope de veinte manos, mayor puntaje'
  else:duel_winner=random.Random(st['seed']+st['seq']*104729).choice(d['pair']);reason='tope de veinte manos, empate y sorteo'
 if duel_winner is not None:
  st['history'].append({'round':st['round'],'pair':list(d['pair']),'winner':duel_winner,'score':dict(d['score']),'hands':d['hands'],'reason':reason});st['advancing'].append(duel_winner);next_duel(st)
 else:d['choices']={};st['turn']=d['pair'][d['hands']%2]
 return {'resolved':True,'hand_winner':winner,'duel_winner':duel_winner,'reason':reason if duel_winner is not None else None}

def choose(st,p,level=2,rng=None):
 """Independent random choice. Never reads the rival's sealed choice."""
 return (rng or random).choice(CHOICES)
