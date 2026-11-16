"""Fictional training brigade vs colorful automata. No real armies or combat advice."""
import random
SCENES=('Campamento del Faro','Patio de las Banderitas','Estación de Nubes','Puente de Luz','Valle del Eco','Base del Cometa','Taller de Autómatas','Puesto del Amanecer')
SIGNALS=('azul','dorado','violeta')
FRONTS=('izquierda','centro','derecha')
WEATHER=('despejado','nublado','lluvia','viento')
DAYTIMES=('mañana','tarde','noche')

def spec(wave,seed):
 if type(wave) is not int or not 1<=wave<=300:raise ValueError('Oleada inválida')
 r=random.Random(f'{seed}:brigada:{wave}')
 return {'scene':r.choice(SCENES),'weather':r.choice(WEATHER),'daytime':r.choice(DAYTIMES),'quota':5+min(9,(wave-1)//25),'bosses':3 if wave==300 else 1 if wave%10==0 else 0,'approach':6 if wave<100 else 5}

def new_game(seats,seed=None):
 if not 1<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Brigada inválida')
 s={'seats':list(seats),'turn':seats[0],'seed':random.randrange(1<<30) if seed is None else seed,'wave':1,'phase':'wave','winner':None,'beacons':{f:6 for f in FRONTS},'battery':8,'max_battery':8,'radio':2,'shield':0,'last_signal':None,'targets':[],'spawned':0,'resolved':0,'serial':0,'seq':0,'moves':[],'players':{p:{'points':0} for p in seats},'reward':None}
 start_wave(s);return s

def total(s):return s['spec']['quota']+s['spec']['bosses']
def start_wave(s):
 s['spec']=spec(s['wave'],s['seed']);s.update(phase='wave',targets=[],spawned=0,resolved=0,battery=s['max_battery'],radio=2,shield=0,last_signal=None,reward=None);s['turn']=s['seats'][0];fill(s)

def fill(s):
 r=random.Random(f"{s['seed']}:{s['wave']}:{s['serial']}:brigada")
 while len(s['targets'])<4 and s['spawned']<total(s):
  boss=s['spawned']>=s['spec']['quota'];s['serial']+=1;sequence=list(SIGNALS);r.shuffle(sequence)
  s['targets'].append({'id':s['serial'],'name':('Autómata director ' if boss else 'Dron de prácticas ')+str(s['serial']),'front':r.choice(FRONTS),'sequence':sequence if boss else [r.choice(SIGNALS)],'step':0,'approach':s['spec']['approach']+(3 if boss else 0),'boss':boss})
  s['spawned']+=1

def cost(s,a):return 3 if s['last_signal']==a else 2

def legal_actions(s,pid):
 if s['winner'] is not None or s['phase']!='wave' or s['turn']!=pid or pid not in s['players']:return []
 a=['recargar','escudo']+[c for c in SIGNALS if s['battery']>=cost(s,c)]
 if s['radio']>0:a.append('radio')
 return a

def play(s,pid,action):
 if action not in legal_actions(s,pid):raise ValueError('Acción fuera de turno o sin carga')
 saved=0;damage=0;hits=0
 if action in SIGNALS:
  s['battery']-=cost(s,action);s['last_signal']=action
  for t in list(s['targets']):
   if t['sequence'][t['step']]==action:
    t['step']+=1;hits+=1
    if t['step']==len(t['sequence']):s['targets'].remove(t);s['resolved']+=1;saved+=1;s['players'][pid]['points']+=12 if t['boss'] else 4
 elif action=='recargar':s['battery']=min(s['max_battery'],s['battery']+4);s['last_signal']=None
 elif action=='escudo':s['shield']=min(3,s['shield']+2);s['battery']=min(s['max_battery'],s['battery']+1)
 elif action=='radio':s['radio']-=1
 for t in list(s['targets']):
  if action=='radio':continue
  t['approach']-=1
  if t['approach']<=0:
   s['targets'].remove(t);s['resolved']+=1
   if s['shield']:s['shield']-=1
   else:s['beacons'][t['front']]=max(0,s['beacons'][t['front']]-1);damage+=1
 s['seq']+=1;e={'pid':pid,'action':action,'saved':saved,'hits':hits,'damage':damage,'wave':s['wave'],'seq':s['seq']};s['moves']=(s['moves']+[e])[-30:]
 if min(s['beacons'].values())==0:s['winner']=[];s['phase']='over'
 elif s['resolved']>=total(s):
  for f in FRONTS:s['beacons'][f]=min(6,s['beacons'][f]+1)
  for p in s['players'].values():p['points']+=15
  if s['wave']==300:s['winner']=list(s['seats']);s['phase']='over'
  else:s['phase']='reward';s['reward']='Mejorar batería o reparar balizas. Gratis, sin dinero ni puntos.'
 else:fill(s)
 s['turn']=s['seats'][(s['seats'].index(pid)+1)%len(s['seats'])];return e

def continue_wave(s,pid,reward='reparar'):
 if s['phase']!='reward' or s['winner'] is not None or pid!=s['seats'][0] or reward not in ('bateria','reparar'):raise ValueError('Recompensa inválida')
 if reward=='bateria':s['max_battery']=min(12,s['max_battery']+1)
 else:
  for f in FRONTS:s['beacons'][f]=min(6,s['beacons'][f]+2)
 s['wave']+=1;start_wave(s)

def choose_move(s,pid,level=2):
 actions=legal_actions(s,pid)
 if not actions:return None
 if level==0:return random.Random(f"bot:{s['seed']}:{s['seq']}:{pid}").choice(actions)
 counts={c:sum(t['sequence'][t['step']]==c for t in s['targets']) for c in SIGNALS}
 urgent=min(s['targets'],key=lambda t:t['approach']);signal=urgent['sequence'][urgent['step']]
 if urgent['approach']<=2 and signal in actions:return signal
 available=[c for c in SIGNALS if c in actions and counts[c]]
 if available:return max(available,key=lambda c:(counts[c],-cost(s,c)))
 if min(t['approach'] for t in s['targets'])<=1 and 'radio' in actions:return 'radio'
 return 'recargar'

def public_state(s):
 return {k:s[k] for k in ('wave','phase','winner','beacons','battery','max_battery','radio','shield','turn','seq','reward')}|{'scene':s['spec']['scene'],'weather':s['spec']['weather'],'daytime':s['spec']['daytime'],'resolved':s['resolved'],'total':total(s),'costs':{c:cost(s,c) for c in SIGNALS},'players':{p:dict(d) for p,d in s['players'].items()},'targets':[{k:v for k,v in t.items() if k not in ('sequence','step')}|{'signal':t['sequence'][t['step']],'steps_left':len(t['sequence'])-t['step']} for t in s['targets']],'actions':legal_actions(s,s['turn'])}
