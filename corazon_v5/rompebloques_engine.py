"""Original turn-based assisted brick breaker, no instant-physics claim."""
import random
from copy import deepcopy
COLORS=('azul','dorado','violeta','verde','coral')
LEVELS=50

def new_game(seats,seed=None,level=2):
 if not 1<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
 if type(level) is not int or not 0<=level<=5:raise ValueError('Dificultad inválida')
 st=dict(seats=list(seats),seed=random.randrange(1<<30) if seed is None else seed,turn=seats[0],difficulty=level,level=1,phase='ready',players={p:dict(score=0,lives=3,hits=0) for p in seats},board=[],cue=None,seq=0,cleared=0,winner=None,result='Cincuenta niveles de bloques de colores. Elegí Lanzar para empezar.')
 build_board(st);return st

def build_board(st):
 # Preserve the original first twelve boards. Later walls fit six visible rows.
 level=st['level']
 if type(level) is not int or not 1<=level<=LEVELS:raise ValueError('Nivel inválido')
 rows=min(6,2+(level-1)//3)
 board=[]
 for r in range(rows):
  for c in range(5):
   if level<=12:hp=2 if level>=7 and (r+c)%3==0 else 1
   else:
    # 38 distinct fixed armor patterns. Six low bits encode each level;
    # the remaining cells gradually increase two-layer density.
    index=r*5+c
    hp=1+(((level-13)>>index)&1) if index<6 else 1+int((index*7+level*3)%24 < 4+(level-13)//4)
   board.append(dict(row=r+1,column=c+1,color=COLORS[c],hp=hp))
 st['board']=board

def legal_actions(st,pid):
 if st['turn']!=pid or st['winner'] is not None:return []
 return ['lanzar'] if st['phase']=='ready' else ['columna '+str(c) for c in range(1,6)] if st['phase']=='ball' else []

def set_cue(st):
 rng=random.Random(f"brick:{st['seed']}:{st['level']}:{st['seq']}")
 columns=sorted({b['column'] for b in st['board']});column=rng.choice(columns);brick=max((b for b in st['board'] if b['column']==column),key=lambda b:b['row'])
 st['cue']=dict(column=column,row=brick['row'],color=brick['color'],armor=brick['hp'],window_seconds=(45,40,35,30,25,20)[st['difficulty']])

def launch(st,pid):
 if 'lanzar' not in legal_actions(st,pid):raise ValueError('No se puede lanzar')
 st['phase']='ball';st['seq']+=1;set_cue(st);st['result']='Bola lanzada. Mové la barra a la columna anunciada.'

def finish(st):
 high=max(p['score'] for p in st['players'].values());st['winner']=[p for p in st['seats'] if st['players'][p]['score']==high];st['phase']='done';st['cue']=None

def hit(st,pid,column=None,timeout=False):
 if st['phase']!='ball' or st['turn']!=pid or st['winner'] is not None:raise ValueError('Fuera de turno')
 if not timeout and (type(column) is not int or not 1<=column<=5):raise ValueError('Columna inválida')
 cue=st['cue'];correct=not timeout and column==cue['column'];p=st['players'][pid];st['seq']+=1
 if correct:
  brick=next(b for b in st['board'] if b['column']==cue['column'] and b['row']==cue['row']);brick['hp']-=1;points=30+5*st['level'];p['score']+=points;p['hits']+=1
  if brick['hp']==0:
   st['board'].remove(brick);st['result']='Rompiste bloque '+brick['color']+', fila '+str(brick['row'])+', columna '+str(brick['column'])+'. '+str(points)+' puntos virtuales.'
  else:st['result']='Rebote en bloque '+brick['color']+', fila '+str(brick['row'])+'. Queda una capa. '+str(points)+' puntos virtuales.'
 else:p['lives']-=1;st['result']='Bola perdida. '+('Se agotó la ventana asistida. ' if timeout else 'La barra no estaba en la columna anunciada. ')+str(p['lives'])+' vidas virtuales para esta persona.'
 if not st['board']:
  st['cleared']+=1;st['phase']='between';st['cue']=None;st['result']+=' Nivel '+str(st['level'])+' limpio.'
  if st['level']==LEVELS:finish(st)
  return dict(correct=correct,cleared=True)
 eligible=[q for q in st['seats'] if st['players'][q]['lives']>0]
 if not eligible:finish(st);return dict(correct=correct,cleared=False)
 i=st['seats'].index(pid);st['turn']=next(st['seats'][(i+j)%len(st['seats'])] for j in range(1,len(st['seats'])+1) if st['seats'][(i+j)%len(st['seats'])] in eligible)
 if correct:set_cue(st)
 else:st['phase']='ready';st['cue']=None
 return dict(correct=correct,cleared=False)

def next_level(st):
 if st['phase']!='between' or st['winner'] is not None:raise ValueError('Nivel no terminado')
 st['level']+=1;build_board(st);st['phase']='ready';st['seq']+=1;st['result']='Nivel '+str(st['level'])+'. '+str(len(st['board']))+' bloques, '+('algunos con dos capas.' if st['level']>=7 else 'una capa por bloque.')

def choose_move(st,pid,level=2):
 if not legal_actions(st,pid):return None
 if st['phase']=='ready':return 'lanzar'
 rng=random.Random(f"bot:{st['seed']}:{pid}:{st['seq']}");c=st['cue']['column'] if rng.random()<(.75,.82,.9,.94,.98,1)[max(0,min(5,level))] else rng.randrange(1,6)
 return 'columna '+str(c)

def public_state(st):
 return deepcopy({k:st[k] for k in ('turn','difficulty','level','phase','players','board','cue','seq','cleared','winner','result')})|{'total_levels':LEVELS,'columns':5,'assisted':True,'actions':legal_actions(st,st['turn'])}
