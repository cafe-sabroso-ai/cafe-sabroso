"""Nueve y media, proposed local-only rules. All totals use half-point integers."""
import random,copy
SUITS=('oros','copas','espadas','bastos')
RANKS=(1,2,3,4,5,6,7,10,11,12)
NAMES={1:'as',10:'sota',11:'caballo',12:'rey'}
TARGET=19
RULES='Variante propuesta para esta previa: baraja española de 40 cartas, sin ochos ni nueves. As vale uno, números del dos al siete su valor, sota, caballo y rey medio punto. Acercate a nueve y medio sin pasarte. Empezás con una carta. Podés pedir o plantarte. Nueve y medio exactos ganan un punto sin jugar la banca. Si te pasás, perdés una vida. La banca pide hasta siete y medio y después se planta; si se pasa, ganás. Empate no da puntos ni quita vidas. Cada mano ganada suma un punto virtual; cinco puntos ganan la partida. Al perder las tres vidas, termina la partida. No hay dinero, apuestas ni premios. Sin reloj de respuesta. Las reglas de banca, mazo y vidas quedan sujetas a tu revisión.'
def value(c):return 1 if c[0]>=10 else c[0]*2
def total(cards):return sum(map(value,cards))
def number(n):return 'medio'if n==1 else str(n//2)+(' y medio' if n%2 else '')
def cardname(c):return str(NAMES.get(c[0],c[0]))+' de '+c[1]
def deck(seed=None):
 d=[(r,s) for s in SUITS for r in RANKS];random.Random(seed).shuffle(d);return d
def fresh(seed=None):
 return {'deck':deck(seed),'hand':[],'bank':[],'discard':[],'score':0,'lives':3,'round':0,'phase':'ready','text':'Mesa lista. Elegí Repartir para empezar.','revision':0}
def lose(s):
 s['lives']-=1
 if s['lives']==0:s['phase']='done';s['text']+=' No quedan vidas. Partida terminada; podés empezar de nuevo.'
def win(s):
 s['score']+=1
 if s['score']>=5:s['phase']='done';s['text']+=' Llegaste a cinco puntos virtuales. ¡Ganaste la partida!'
def act(old,action):
 s=copy.deepcopy(old)
 if action=='restart':return fresh()
 if action=='deal':
  if s['phase'] not in ('ready','result'):raise ValueError('Primero terminá la mano actual.')
  # Shuffle only between hands, never mid-hand. At most 16 cards can reach 9.5 with this deck.
  s['discard']+=s['hand']+s['bank'];s['hand']=[];s['bank']=[]
  if len(s['deck'])<20:s['deck']+=s['discard'];s['discard']=[];random.SystemRandom().shuffle(s['deck'])
  s['hand']=[s['deck'].pop()];s['round']+=1;s['phase']='playing';s['text']='Salió '+cardname(s['hand'][0])+'. Tenés '+number(total(s['hand']))+'. ¿Carta o te plantás?'
 elif action=='hit':
  if s['phase']!='playing':raise ValueError('No hay una mano esperando carta.')
  c=s['deck'].pop();s['hand'].append(c);n=total(s['hand']);s['text']='Salió '+cardname(c)+'. Tenés '+number(n)+'.'
  if n>TARGET:s['phase']='result';s['text']+=' Te pasaste. Perdís una vida.';lose(s)
  elif n==TARGET:s['phase']='result';s['text']+=' ¡Nueve y medio exactos! Un punto virtual. La banca no juega.';win(s)
  else:s['text']+=' ¿Carta o te plantás?'
 elif action=='stand':
  if s['phase']!='playing':raise ValueError('No hay una mano para plantarse.')
  while total(s['bank'])<15:s['bank'].append(s['deck'].pop())
  a,b=total(s['hand']),total(s['bank']);s['phase']='result';s['text']='Te plantaste con '+number(a)+'. Banca: '+', '.join(map(cardname,s['bank']))+'. Total '+number(b)+'.'
  if b>TARGET or a>b:s['text']+=' Ganaste un punto virtual.';win(s)
  elif a==b:s['text']+=' Empate. Sin puntos ni pérdida de vidas.'
  else:s['text']+=' Gana la banca. Perdís una vida.';lose(s)
 else:raise ValueError('Acción no disponible.')
 s['revision']=old['revision']+1;return s
def view(s):
 def card(c):return {'rank':c[0],'suit':c[1],'name':cardname(c),'value':number(value(c))}
 return {k:s[k] for k in ('phase','score','lives','round','text','revision')}|{'hand':[card(c)for c in s['hand']],'bank':[card(c)for c in s['bank']],'total':number(total(s['hand'])),'bank_total':number(total(s['bank']))if s['bank'] else None,'remaining':len(s['deck'])}
