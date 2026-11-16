"""Original assisted falling-block puzzle, turn-based placement and no branded assets."""
import random
from copy import deepcopy
WIDTH=6
HEIGHT=12
SHAPES={'barra':((0,0),(1,0),(2,0),(3,0)),'cuadro':((0,0),(1,0),(0,1),(1,1)),'punta':((0,0),(1,0),(2,0),(1,1)),'gancho':((0,0),(0,1),(1,1),(2,1)),'curva':((1,0),(2,0),(0,1),(1,1))}
COLORS={'barra':'azul','cuadro':'dorado','punta':'violeta','gancho':'verde','curva':'coral'}

def rotate_cells(cells):
 cells=[(-y,x) for x,y in cells];mx=min(x for x,y in cells);my=min(y for x,y in cells)
 return tuple(sorted((x-mx,y-my) for x,y in cells))

def piece_cells(name,rotation):
 cells=SHAPES[name]
 for _ in range(rotation%4):cells=rotate_cells(cells)
 return cells

def new_game(seats,seed=None,level=2):
 if not 1<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
 st=dict(seats=list(seats),seed=random.randrange(1<<30) if seed is None else seed,turn=seats[0],difficulty=max(0,min(5,level)),level=1,phase='place',board=[[None]*WIDTH for _ in range(HEIGHT)],players={p:dict(score=0,lines=0,placed=0) for p in seats},piece=None,number=0,lines=0,seq=0,winner=None,result='Completá filas con piezas originales de colores. Mover, girar y soltar por turnos, sin gravedad automática continua.')
 spawn(st);return st

def fits(st,cells,x,y):
 return all(0<=x+dx<WIDTH and 0<=y+dy<HEIGHT and st['board'][y+dy][x+dx] is None for dx,dy in cells)

def landing(st,name=None,rotation=None,x=None):
 p=st['piece'];cells=piece_cells(name or p['name'],p['rotation'] if rotation is None else rotation);x=p['x'] if x is None else x
 if not fits(st,cells,x,0):return None
 y=0
 while fits(st,cells,x,y+1):y+=1
 return y

def finish(st,reason):
 high=max(p['score'] for p in st['players'].values());st['winner']=[p for p in st['seats'] if st['players'][p]['score']==high];st['phase']='done';st['result']+=reason

def spawn(st):
 st['number']+=1;rng=random.Random(f"piece:{st['seed']}:{st['number']}");name=rng.choice(tuple(SHAPES));st['piece']=dict(name=name,color=COLORS[name],rotation=0,x=1)
 if landing(st) is None:finish(st,' La pila llegó arriba. Fin de la partida.')

def move(st,pid,action,column=None):
 if st['phase']!='place' or st['turn']!=pid or st['winner'] is not None:raise ValueError('Fuera de turno')
 if action not in ('izquierda','derecha','girar','columna'):raise ValueError('Movimiento inválido')
 if action=='columna' and (type(column) is not int or not 1<=column<=WIDTH):raise ValueError('Columna inválida')
 p=st['piece'];rot=(p['rotation']+1)%4 if action=='girar' else p['rotation'];x=column-1 if action=='columna' else p['x']+(-1 if action=='izquierda' else 1 if action=='derecha' else 0)
 y=landing(st,rotation=rot,x=x)
 if y is None:raise ValueError('La pieza no cabe en esa posición')
 p['rotation']=rot;p['x']=x;st['seq']+=1;st['result']='Pieza '+p['name']+', giro '+str(rot+1)+', desde columna '+str(x+1)+'. Apoyaría en fila '+str(y+1)+' desde arriba.'

def drop(st,pid):
 if st['phase']!='place' or st['turn']!=pid or st['winner'] is not None:raise ValueError('Fuera de turno')
 p=st['piece'];y=landing(st)
 if y is None:raise ValueError('No hay espacio')
 for dx,dy in piece_cells(p['name'],p['rotation']):st['board'][y+dy][p['x']+dx]=p['color']
 full=[i for i,row in enumerate(st['board']) if all(row)];n=len(full);st['board']=[[None]*WIDTH for _ in full]+[row for i,row in enumerate(st['board']) if i not in full];score=(10,100,250,450,700)[n];person=st['players'][pid];person['score']+=score;person['lines']+=n;person['placed']+=1;st['lines']+=n;st['level']=min(12,1+st['lines']//3);st['seq']+=1;st['result']='Pieza '+p['name']+' colocada.'+(' '+str(n)+' línea(s) completa(s), se retiran y baja la pila.' if n else ' Sin línea completa esta vez.')+' '+str(score)+' puntos virtuales.'
 if st['lines']>=36:finish(st,' Meta de36líneas alcanzada.');return n
 i=st['seats'].index(pid);st['turn']=st['seats'][(i+1)%len(st['seats'])];spawn(st);return n

def suggest(st):
 best=None
 for rot in range(4):
  for x in range(WIDTH):
   y=landing(st,rotation=rot,x=x)
   if y is None:continue
   grid=deepcopy(st['board'])
   for dx,dy in piece_cells(st['piece']['name'],rot):grid[y+dy][x+dx]='x'
   rows=sum(all(row) for row in grid);grid=[[None]*WIDTH for _ in range(rows)]+[row for row in grid if not all(row)];heights=[];holes=0
   for c in range(WIDTH):
    seen=False;h=0
    for r in range(HEIGHT):
     if grid[r][c]:seen=True;h=max(h,HEIGHT-r)
     elif seen:holes+=1
    heights.append(h)
   value=rows*18-holes*9-sum(heights)*.7-sum(abs(heights[i]-heights[i-1]) for i in range(1,WIDTH))*.4
   item=dict(rotation=rot,column=x+1,row=y+1,value=value)
   if best is None or value>best['value']:best=item
 return best

def bot_place(st,pid):
 if st['turn']!=pid or st['winner'] is not None:raise ValueError('Fuera de turno')
 hint=suggest(st)
 if hint:st['piece'].update(rotation=hint['rotation'],x=hint['column']-1)
 return drop(st,pid)

def public_state(st):
 p=deepcopy(st['piece']);p['cells']=piece_cells(p['name'],p['rotation']);p['column']=p['x']+1;p['landing_row']=landing(st)
 return deepcopy({k:st[k] for k in ('turn','difficulty','level','phase','board','players','number','lines','seq','winner','result')})|{'piece':p,'width':WIDTH,'height':HEIGHT,'target_lines':36,'assisted':True,'window_seconds':(60,55,50,45,40,35)[st['difficulty']]}
