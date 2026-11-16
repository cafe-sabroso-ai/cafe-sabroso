"""Five-stone payana-inspired sonic arcade; simplified ten-pickup progression."""
import random,math
TASKS=[('unas',1)]*4+[('dos',2)]*2+[('tres',3),('tres',1),('cuatro',4),('grande',5)]
DURATIONS=(6.,5.5,5.,4.5,4.,3.5)
WIDTHS=(1.5,1.3,1.1,.9,.75,.6)

def timing(step,level=2):
 level=max(0,min(5,int(level)));phase=min(4,next((i for i,n in enumerate(('unas','dos','tres','cuatro','grande')) if n==TASKS[min(step,9)][0]),0));duration=DURATIONS[level];width=WIDTHS[level]*(1-phase*.09);center=duration*.78
 return {'duration':duration,'open':center-width/2,'close':center+width/2,'apex':duration*.5,'count':TASKS[min(step,9)][1],'phase':TASKS[min(step,9)][0]}

def new_game(seats,mode='individual'):
 if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Configuración inválida')
 teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
 return {'seats':list(seats),'teams':teams,'mode':mode,'boards':{t[0]:{'step':0,'throws':0,'done':False,'member':0,'last_success':None} for t in teams},'turn':seats[0],'winner':None,'seq':0,'stage':'ready','result':''}
def team(st,p):return next(t for t in st['teams'] if p in t)
def board(st,p):return st['boards'][team(st,p)[0]]
def start(st,p):
 if st['winner'] is not None or st['turn']!=p or st['stage']!='ready':raise ValueError('No se puede lanzar')
 st['stage']='flight';st['seq']+=1

def catch(st,p,elapsed,level=2,timeout=False):
 if st['winner'] is not None or st['turn']!=p or st['stage']!='flight':raise ValueError('Fuera de turno')
 if isinstance(elapsed,bool) or not isinstance(elapsed,(float,int)) or not math.isfinite(elapsed) or elapsed<0:raise ValueError('Tiempo inválido')
 b=board(st,p);cue=timing(b['step'],level);success=not timeout and cue['open']<=elapsed<=cue['close'];b['throws']+=1;b['step']+=int(success);b['last_success']=success;b['done']=b['step']>=10 or b['throws']>=20;st['stage']='ready';st['seq']+=1
 own=team(st,p);b['member']=(b['member']+1)%len(own)
 live=[t for t in st['teams'] if not st['boards'][t[0]]['done']]
 if not live:
  best=max(b['step'] for b in st['boards'].values());st['winner']=[q for q in st['seats'] if board(st,q)['step']==best]
 elif success and not b['done']:st['turn']=own[b['member']]
 else:
  i=st['teams'].index(own);nxt=next(st['teams'][(i+k)%len(st['teams'])] for k in range(1,len(st['teams'])+1) if st['teams'][(i+k)%len(st['teams'])] in live);st['turn']=nxt[st['boards'][nxt[0]]['member']]
 return {'success':success,'timeout':timeout,'count':cue['count'],'phase':cue['phase'],'elapsed':elapsed}

def bot_time(cue,level=2,rng=None):
 rng=rng or random;index=max(0,min(5,int(level)));width=cue['close']-cue['open'];center=(cue['open']+cue['close'])/2
 return max(0,min(cue['duration'],center+rng.gauss(0,width*(.9,.75,.6,.5,.4,.3)[index])))
