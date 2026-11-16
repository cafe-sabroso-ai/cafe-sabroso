"""La escondida: private choices, rotating seeker, finite public searches."""
import random
SCENES={
 'casa':('Casa', ['sofá','cortina','mesa','armario','cama','bañera','alacena','escalera','sillón','biblioteca','balcón','lavadero']),
 'escuela':('Escuela',['pupitre','pizarrón','armario','biblioteca','escenario','banco','bebedero','árbol','tobogán','escalera','portería','depósito']),
 'parque':('Parque',['roble','arbusto','banco','fuente','tobogán','hamaca','puente','quiosco','estatua','rosal','pérgola','tronco']),
 'mansion':('Mansión',['cortina','armadura','biblioteca','piano','chimenea','escalera','baúl','espejo','sofá','columna','biombo','balcón']),
 'camping':('Camping',['carpa','pino','tronco','roca','mesa','fogón','cabaña','canoa','mochila','arbusto','puente','hamaca']),
 'museo':('Museo',['estatua','columna','vitrina','banco','cortina','panel','escalera','maqueta','armadura','esqueleto','mural','baúl'])}

def new_game(seats,scene='casa'):
 if not 2<=len(seats)<=10 or len(set(seats))!=len(seats) or scene not in SCENES:raise ValueError('Configuración inválida')
 return dict(seats=list(seats),scene=scene,round=0,turn=seats[0],stage='setup',hides={},found={},searched=[],attempts=0,scores={p:0 for p in seats},winner=None,history=[],result='')
def start_round(st):
 if st['winner'] is not None:raise ValueError('Partida terminada')
 st.update(turn=st['seats'][st['round']],stage='hide',hides={},found={},searched=[],attempts=0,history=[],result='')
def hide(st,p,spot):
 if st['stage']!='hide' or p not in st['seats'] or p==st['turn'] or p in st['hides'] or isinstance(spot,bool) or not isinstance(spot,int) or not 0<=spot<12:raise ValueError('Escondite inválido')
 st['hides'][p]=spot

def begin_search(st):
 if st['stage']!='hide':raise ValueError('Fuera de fase')
 for p in st['seats']:
  if p!=st['turn'] and p not in st['hides']:st['hides'][p]=random.randrange(12)
 st['stage']='search'

def distance(a,b):
 ar,ac=divmod(a,4);br,bc=divmod(b,4);return abs(ar-br)+abs(ac-bc)
def search(st,p,spot=None):
 if st['stage']!='search' or p!=st['turn']:raise ValueError('Fuera de turno')
 if spot is not None and (isinstance(spot,bool) or not isinstance(spot,int) or not 0<=spot<12 or spot in st['searched']):raise ValueError('Lugar inválido o repetido')
 st['attempts']+=1;found=[];heat=None
 if spot is not None:
  st['searched'].append(spot);found=[q for q,x in st['hides'].items() if x==spot and q not in st['found']]
  for q in found:st['found'][q]=spot;st['scores'][p]+=1
  unseen=[x for q,x in st['hides'].items() if q not in st['found']]
  if unseen:
   d=min(distance(spot,x) for x in unseen);heat='caliente' if d<=1 else 'tibia' if d<=3 else 'fría'
 event=dict(spot=spot,found=found,heat=heat);st['history'].append(event)
 if st['attempts']>=8 or len(st['found'])==len(st['seats'])-1:
  for q in st['hides']:
   if q not in st['found']:st['scores'][q]+=1
  st['stage']='round_end';st['round']+=1
  if st['round']==len(st['seats']):
   high=max(st['scores'].values());st['winner']=[q for q in st['seats'] if st['scores'][q]==high];st['stage']='done'
 return event

def public(st,p=None):
 return dict(scene=st['scene'],round=st['round'],turn=st['turn'],stage=st['stage'],ready=len(st['hides']),total=len(st['seats'])-1,own=st['hides'].get(p) if p in st['seats'] and p!=st['turn'] else None,found=[dict(id=q,spot=x) for q,x in st['found'].items()],searched=list(st['searched']),attempts=st['attempts'],scores=dict(st['scores']),history=[dict(e,found=list(e['found'])) for e in st['history']],winner=st['winner'],result=st['result'])

def bot_search(st):
 # Deliberately no access to hides: public observations only.
 choices=[i for i in range(12) if i not in st['searched']]
 return random.choice(choices)
