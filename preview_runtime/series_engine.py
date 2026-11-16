"""Original sourced trivia banks. Titles only; no official character artwork/music."""
import json,random,re,unicodedata
from pathlib import Path
TITLES=[('simpsons','Los Simpson'),('chavo','El Chavo del 8'),('chapulin','El Chapulín Colorado'),('pitufos','Los Pitufos'),('chapatin','Dr. Chapatín'),('alf','ALF'),('scooby','Scooby-Doo'),('picapiedra','Los Picapiedra'),('supersonicos','Los Supersónicos'),('superpoderosas','Las Chicas Superpoderosas'),('dragonball','Dragon Ball: original, Z, GT y películas'),('dbsuper','Dragon Ball Super: anime 2015-2018'),('caballeros','Los Caballeros del Zodíaco'),('supercampeones','Supercampeones'),('johnny','Johnny Bravo'),('yogui','Oso Yogui'),('looney','Looney Tunes'),('rugrats','Rugrats'),('manotas','Pulpo Manotas'),('dongato','Don Gato'),('huckleberry','Huckleberry Hound'),('autoslocos','Los Autos Locos'),('tiroloco','Tiro Loco McGraw'),('silvestre','Silvestre y Tweety'),('chiflados','Los Tres Chiflados'),('zorro','El Zorro: Guy Williams')]
BANK=json.loads(Path(__file__).with_name('series_bank.json').read_text())
MIN_READY=300
EDITORIAL_HOLDS=set() # A bank can be retained here independently of its count.

def clean(t):return ''.join(c for c in unicodedata.normalize('NFD',str(t).lower()) if unicodedata.category(c)!='Mn').strip()
def catalog():return [dict(id=k,title=t,count=len(BANK.get(k,[])),ready=len(BANK.get(k,[]))>=MIN_READY and k not in EDITORIAL_HOLDS,scope='Serie Disney con Guy Williams: cuatro preguntas por cada uno de los 78 episodios regulares y ocho generales. Sin películas, otras adaptaciones ni los cuatro especiales posteriores.' if k=='zorro' else 'Anime televisivo 2015-2018; sin manga posterior ni estrenos nuevos.' if k=='dbsuper' else 'Selección de personajes y episodios de temporadas 1 a 30; no todas las temporadas tienen igual cantidad. Sin datos personales de actores.' if k=='simpsons' else 'Personajes y selección de sinopsis de la serie de acción real, en catálogos 1973-1979. No se afirma visionado íntegro. '+('Falta ampliar a 300.' if len(BANK.get(k,[]))<MIN_READY else str(len(BANK.get(k,[])))+' preguntas con revisión editorial local; dificultad estimada, sin calibración humana.') if k=='chavo' else '405 preguntas con revisión editorial local de fuentes y opciones; dificultad estimada, sin calibración humana. Sin afirmar visionado íntegro de episodios.' if k=='chapulin' else 'En preparación: falta verificar el banco.') for k,t in TITLES]
def ready():return [r['id'] for r in catalog() if r['ready']]
def validate():
 seen=set();questions=set()
 for title,bank in BANK.items():
  if title not in dict(TITLES):raise ValueError('Título sin catálogo')
  for q in bank:
   if q['id'] in seen or not q['q'] or len(q['options'])!=4 or len(set(map(clean,q['options'])))!=4 or not 0<=q['answer']<4 or not 0<=q['difficulty']<=5 or not q['source_url'].startswith('https://') or not q['evidence'] or not q['verified']:raise ValueError('Pregunta inválida')
   key=(title,clean(q['q']))
   if key in questions:raise ValueError('Pregunta repetida')
   questions.add(key);seen.add(q['id'])
validate()
def new_game(seats,mode='individual'):
 if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Configuración inválida')
 teams=[list(seats[::2]),list(seats[1::2])] if mode=='equipos' and len(seats)>1 else [[p] for p in seats]
 return dict(seats=list(seats),teams=teams,mode=mode,boards={t[0]:dict(score=0,count=0,member=0) for t in teams},turn=seats[0],stage='setup',winner=None,question=None,series=None,used=[],history=[],result='',seq=0)
def team(st,p):return next(t for t in st['teams'] if p in t)
def board(st,p):return st['boards'][team(st,p)[0]]
def spin(st,p,level=2,rng=None):
 if st['stage']!='spin' or st['turn']!=p or st['winner'] is not None:raise ValueError('No se puede girar')
 rng=rng or random;titles=ready()
 if not titles:raise ValueError('No hay bancos listos')
 candidates=[t for t in titles if t!=st['series']] or titles;title=rng.choice(candidates);pool=[q for q in BANK[title] if q['id'] not in st['used']]
 if not pool:
  st['used']=[k for k in st['used'] if not k.startswith(title+'-')];pool=BANK[title]
 distance=min(abs(q['difficulty']-level) for q in pool);pool=[q for q in pool if abs(q['difficulty']-level)==distance];q=dict(rng.choice(pool));correct=q['options'][q['answer']];opts=list(q['options']);rng.shuffle(opts);q.update(options=opts,answer=opts.index(correct));st['used'].append(q['id']);st.update(series=title,question=q,stage='question');st['seq']+=1;return q

def answer(st,p,index=None,timeout=False):
 if st['stage']!='question' or st['turn']!=p or st['winner'] is not None:raise ValueError('Fuera de turno')
 if not timeout and (isinstance(index,bool) or not isinstance(index,int) or not 0<=index<4):raise ValueError('Opción inválida')
 q=st['question'];correct=not timeout and index==q['answer'];b=board(st,p);b['count']+=1;b['score']+=int(correct);st['history'].append(dict(id=q['id'],player=p,correct=correct));t=team(st,p);b['member']=(b['member']+1)%len(t)
 eligible=[t for t in st['teams'] if st['boards'][t[0]]['count']<10]
 if not eligible:
  high=max(b['score'] for b in st['boards'].values());st['winner']=[p for t in st['teams'] if st['boards'][t[0]]['score']==high for p in t];st['stage']='done'
 else:
  start=st['teams'].index(t)
  for off in range(1,len(st['teams'])+1):
   nt=st['teams'][(start+off)%len(st['teams'])]
   if nt in eligible:st['turn']=nt[st['boards'][nt[0]]['member']];break
  st['stage']='spin'
 st['question']=None;return dict(correct=correct,revealed=q['options'][q['answer']],source_url=q['source_url'],evidence=q['evidence'])

def bot_option(options,level=2,rng=None):
 # No answer key enters this function. Bot is an openly described random participant.
 return (rng or random).randrange(len(options))
