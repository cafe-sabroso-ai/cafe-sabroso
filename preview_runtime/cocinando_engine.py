"""Fictional cooking-order memory game, not real cooking instructions."""
import random
RECIPES={
 'Sándwich arcoíris':('pan nube','untable de luna','hojas verdes','rodajas de sol','tapa de estrellas'),
 'Sopa de planetas':('olla vacía','caldo de cometa','cubitos de planeta','remolino violeta','brillo final'),
 'Galletas musicales':('bol de notas','harina de canción','mezcla de ritmo','molde de clave','decoración de campanas'),
 'Ensalada de colores':('plato blanco','hojas esmeralda','cuadrados rojos','círculos amarillos','lluvia de semillas'),
 'Helado de nubes':('copa azul','nube de vainilla','nube de frutilla','salsa de arcoíris','estrella de azúcar'),
 'Pizza espacial':('base de luna','salsa de marte','queso de saturno','anillos de colores','banderita de cohete'),
 'Torta del jardín':('bandeja verde','disco de bizcocho','crema de flores','pétalos de colores','mariposa de papel'),
 'Brochetas de fiesta':('palito mágico','cubo naranja','esfera violeta','triángulo verde','moño de fiesta')}

def new_game(seats,mode='individual',recipe='Sándwich arcoíris',seed=None):
 if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos') or recipe not in RECIPES:raise ValueError('Configuración inválida')
 seed=seed if seed is not None else random.randrange(1<<30);rng=random.Random(seed);recipes=[recipe]+rng.sample([r for r in RECIPES if r!=recipe],2);teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
 cards=[]
 for r in recipes:
  order=list(range(5));rng.shuffle(order);cards.append(order)
 st={'seats':list(seats),'teams':teams,'mode':mode,'seed':seed,'recipes':recipes,'cards':cards,'boards':{},'turn':seats[0],'winner':None,'seq':0,'result':''}
 for t in teams:st['boards'][t[0]]={'round':0,'step':0,'score':0,'done':False,'stage':'memorize','assisted':False,'bot_memory':list(RECIPES[recipe]),'revealed':None}
 return st

def team(st,p):return next(t for t in st['teams'] if p in t)
def board(st,p):return st['boards'][team(st,p)[0]]
def recipe(st,b):return st['recipes'][min(b['round'],2)]
def public_board(st,b,show=False):
 r=recipe(st,b);return {k:b[k] for k in ('round','step','score','done','stage','assisted','revealed')}|{'recipe':r,'cards':[{'id':slot,'word':RECIPES[r][i]} for slot,i in enumerate(st['cards'][min(b['round'],2)])] if show else [],'sequence':list(RECIPES[r]) if show and not b['done'] and (b['stage']=='memorize' or b['assisted']) else []}

def check(st,p):
 if st['winner'] is not None or st['turn']!=p or board(st,p)['done']:raise ValueError('Fuera de turno')
def ready(st,p):
 check(st,p);b=board(st,p)
 if b['stage']!='memorize':raise ValueError('Ya empezó')
 b['stage']='repeat';st['seq']+=1

def help_order(st,p):
 check(st,p);b=board(st,p)
 if b['stage']!='repeat':raise ValueError('Primero memorizá')
 b['assisted']=True;st['seq']+=1

def guess(st,p,index=None,timeout=False):
 check(st,p);b=board(st,p)
 if b['stage']!='repeat':raise ValueError('Primero memorizá')
 if not timeout and (type(index) is not int or not 0<=index<5):raise ValueError('Tarjeta inválida')
 r=recipe(st,b);answer=b['step'];correct=not timeout and st['cards'][b['round']][index]==answer;points=int(correct and not b['assisted']);b['score']+=points;b['revealed']=RECIPES[r][answer];b['step']+=1;b['assisted']=False
 if b['step']==5:
  b['round']+=1;b['step']=0;b['done']=b['round']>=3
  if not b['done']:b['stage']='memorize';b['bot_memory']=list(RECIPES[recipe(st,b)])
 st['seq']+=1;live=[q for q in st['seats'] if not board(st,q)['done']]
 if not live:
  best=max(b['score'] for b in st['boards'].values());st['winner']=[q for q in st['seats'] if board(st,q)['score']==best]
 else:
  i=st['seats'].index(p);st['turn']=next(st['seats'][(i+k)%len(st['seats'])] for k in range(1,len(st['seats'])+1) if st['seats'][(i+k)%len(st['seats'])] in live)
 return {'correct':correct,'points':points,'revealed':b['revealed'],'timeout':timeout}

def choose(st,p,level=2,rng=None):
 """Only the earlier shown memory and public current cards, never future recipes."""
 rng=rng or random;b=board(st,p);view=public_board(st,b,True)
 if view['stage']=='memorize':return 'ready'
 recalled=b['bot_memory'][view['step']];options=view['cards'];correct=next(o['id'] for o in options if o['word']==recalled)
 return rng.choice([o['id'] for o in options if o['id']!=correct]) if rng.random()<(0.35,.15,.03)[max(0,min(2,level))] else correct
