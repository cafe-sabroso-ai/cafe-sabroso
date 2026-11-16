"""Original, turn-based motorcycle arcade. No brands, bets or real circuits."""
import random
VARIANTS=('pista','montana','agua')
WEATHER=('despejado','nublado','lluvia')
DAYTIMES=('mañana','tarde','noche')
TRACKS={
 'velocidad':('recta','curva izquierda','recta','curva derecha','recta','chicana'),
 'tecnico':('curva izquierda','chicana','recta','curva derecha','chicana','recta'),
 'mixto':('recta','curva derecha','curva izquierda','recta','chicana','recta'),
}
TERRAIN_TRACKS={'montana':{'sierra':('cuesta','rocas','barro','salto','cuesta','recta'),'sendero':('rocas','recta','salto','barro','cuesta','recta')},'agua':{'bahia':('recta','boya izquierda','ola','boya derecha','corriente','recta'),'canal':('corriente','boya derecha','recta','ola','boya izquierda','recta')}}
POWERS=('turbo','agarre','escudo')
FINISH=300
MAX_ROUNDS=40

def new_game(seats,countries,seed=None,variant='pista',track=None,weather=None,daytime=None):
 if variant not in VARIANTS or not 2<=len(seats)<=20 or len(set(seats))!=len(seats):raise ValueError('Carrera inválida')
 if not countries or len(set(countries))!=len(countries) or any(not isinstance(c,str) or not c.strip() for c in countries):raise ValueError('Catálogo de países inválido')
 rng=random.Random(seed);seed=rng.randrange(1<<30) if seed is None else seed
 catalog=TRACKS if variant=='pista' else TERRAIN_TRACKS[variant]
 track=track or rng.choice(tuple(catalog));weather=weather or rng.choice(WEATHER);daytime=daytime or rng.choice(DAYTIMES)
 if track not in catalog or weather not in WEATHER or daytime not in DAYTIMES:raise ValueError('Escenario inválido')
 return {'variant':variant,'seed':seed,'country':rng.choice(list(countries)),'track':track,'weather':weather,'daytime':daytime,
  'seats':list(seats),'turn':seats[0],'round':1,'moves':[],'winner':None,'podium':[],
  'racers':{p:{'distance':0,'energy':6,'lane':i%3,'powers':{k:1 for k in POWERS},'shield':False} for i,p in enumerate(seats)}}

def segment(st):
 catalog=TRACKS if st['variant']=='pista' else TERRAIN_TRACKS[st['variant']]
 return catalog[st['track']][(st['round']-1)%len(catalog[st['track']])]

def ideal_lane(piece):return 0 if piece in ('curva izquierda','boya izquierda') else 2 if piece in ('curva derecha','boya derecha') else 1
def ranking(st):return sorted(st['seats'],key=lambda p:(-st['racers'][p]['distance'],st['seats'].index(p)))
def legal_actions(st,pid):
 if st['winner'] is not None or st['turn']!=pid or pid not in st['racers']:return []
 r=st['racers'][pid];a=['crucero','frenar']
 if r['energy']>=2:a.append('acelerar')
 if st['variant']=='montana' and r['energy']>=2:a.append('saltar')
 if st['variant']=='agua' and r['energy']>=1:a.append('maniobra')
 if r['lane']>0:a.append('izquierda')
 if r['lane']<2:a.append('derecha')
 return a+[k for k in POWERS if r['powers'][k]>0]

def play(st,pid,action):
 if action not in legal_actions(st,pid):raise ValueError('Acción fuera de turno o no disponible')
 r=st['racers'][pid];rng=random.Random(f"{st['seed']}:{st['round']}:{st['seats'].index(pid)}")
 old=r['distance'];lane=r['lane'];piece=segment(st);weather=st['weather']
 advance=rng.randint(7,9);penalty=0;rebufo=0;blocked=False
 if action=='acelerar':advance+=5;r['energy']-=2
 elif action=='saltar':advance+=3;r['energy']-=2
 elif action=='maniobra':advance+=2;r['energy']-=1
 elif action=='frenar':advance=5;r['energy']=min(6,r['energy']+2)
 else:r['energy']=min(6,r['energy']+1)
 if action=='izquierda':r['lane']-=1
 elif action=='derecha':r['lane']+=1
 if action in POWERS:
  r['powers'][action]-=1
  if action=='turbo':advance+=8
  if action=='escudo':r['shield']=True
 # The same public track and weather rules apply to every country and racer.
 ideal=ideal_lane(piece)
 hazard=piece in ('curva izquierda','curva derecha','chicana','boya izquierda','boya derecha') and action in ('acelerar','turbo') and r['lane']!=ideal
 if hazard:penalty+=4
 if st['variant']=='montana':
  if piece in ('rocas','salto') and action not in ('saltar','agarre','frenar'):penalty+=3
  if piece=='barro' and action not in ('agarre','crucero','frenar'):penalty+=2
  if piece=='cuesta' and r['energy']==0:penalty+=2
 elif st['variant']=='agua':
  if piece in ('ola','corriente') and action not in ('maniobra','agarre','frenar'):penalty+=3
 if weather=='lluvia' and action in ('acelerar','turbo'):penalty+=2
 if action=='agarre':penalty=0;advance+=2
 if action=='saltar' and piece in ('rocas','salto'):penalty=0
 if action=='maniobra' and piece in ('ola','corriente'):penalty=0
 if penalty and r['shield']:penalty=0;r['shield']=False;blocked=True
 # Rebufo uses the previous complete round, not earlier moves in this round.
 snapshot=st.get('round_snapshot')
 if snapshot is None:
  snapshot={q:dict(distance=d['distance'],lane=d['lane']) for q,d in st['racers'].items()}
  snapshot[pid]={'distance':old,'lane':lane};st['round_snapshot']=snapshot
 if action not in ('frenar','turbo') and any(0<snapshot[q]['distance']-snapshot[pid]['distance']<=12 and snapshot[q]['lane']==r['lane'] for q in st['seats'] if q!=pid):rebufo=2
 advance=max(1,advance-penalty+rebufo);r['distance']=min(FINISH,old+advance)
 move={'pid':pid,'action':action,'advance':r['distance']-old,'lane':r['lane'],'segment':piece,'penalty':penalty,'shield_used':blocked,'rebufo':rebufo,'round':st['round']}
 st['moves'].append(move);count=len(st['moves']);st['turn']=st['seats'][count%len(st['seats'])]
 if count%len(st['seats'])==0:
  st.pop('round_snapshot',None)
  if max(d['distance'] for d in st['racers'].values())>=FINISH or st['round']>=MAX_ROUNDS:
   best=max(d['distance'] for d in st['racers'].values());st['winner']=[q for q in st['seats'] if st['racers'][q]['distance']==best];st['podium']=ranking(st)
  else:st['round']+=1
 return move

def choose_move(st,pid,level=2):
 actions=legal_actions(st,pid)
 if not actions:return None
 rng=random.Random(f"bot:{st['seed']}:{len(st['moves'])}:{pid}")
 if level==0:return rng.choice(actions)
 r=st['racers'][pid];piece=segment(st);ideal=ideal_lane(piece)
 if st['variant']=='montana' and piece in ('rocas','salto') and 'saltar' in actions:return 'saltar'
 if st['variant']=='agua' and piece in ('ola','corriente') and 'maniobra' in actions:return 'maniobra'
 if st['weather']=='lluvia' and 'agarre' in actions and piece!='recta':return 'agarre'
 if piece!='recta' and r['lane']!=ideal:return 'izquierda' if r['lane']>ideal else 'derecha'
 if 'turbo' in actions and piece=='recta' and (r['distance']>=260 or st['round']>20):return 'turbo'
 return 'acelerar' if 'acelerar' in actions and (piece=='recta' or st['weather']!='lluvia') else 'crucero'

def commentary(st,move):
 # Text is original and brief so voice can yield to controls and microphone.
 if st['winner'] is not None:return '¡Bandera de llegada! Cerramos la vuelta con igualdad de turnos.'
 if move['shield_used']:return 'El escudo protegió la moto. Seguimos en carrera.'
 if move['rebufo']:return '¡Aprovechó el rebufo para acercarse!'
 if move['penalty']:return 'Pista exigente: conviene preparar la curva y cuidar el agarre.'
 if move['action'] in ('izquierda','derecha'):return 'Se abre de carril para buscar el adelantamiento.'
 return 'Motor parejo, mirada al siguiente tramo.'
