"""Fictional cooperative Western arcade. No ethnicity enemies or real weapon simulation."""
import random
SCENES=('Pueblo del Sol','Estación del Viento','Cañón de Cobre','Puente del Arroyo','Rancho de las Nubes','Caravana del Desierto','Molino del Alba','Salón de las Linternas','Paso de las Rocas','Mina de Cristal')
WEATHER=('despejado','nublado','lluvia','viento')
DAYTIMES=('mañana','tarde','noche')
LANES=('izquierda','centro','derecha')
KINDS=('bromista','veloz','con escudo de cartón','vigía')
BOSSES=('Capitán Sombrero','Gigante de Cartón','Trío del Silbato')
MAX_WAVES=300

def wave_spec(wave,seed):
 if type(wave) is not int or not 1<=wave<=MAX_WAVES:raise ValueError('Oleada inválida')
 rng=random.Random(f'{seed}:western:{wave}')
 return {'scene':rng.choice(SCENES),'weather':rng.choice(WEATHER),'daytime':rng.choice(DAYTIMES),
         'quota':4+min(8,(wave-1)//30),'bosses':3 if wave==300 else 1 if wave%10==0 else 0,
         'hp':2+min(3,(wave-1)//75),'approach':5 if wave<100 else 4,'wave':wave}

def new_game(seats,seed=None):
 if not 1<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Equipo inválido')
 st={'seats':list(seats),'turn':seats[0],'seed':random.randrange(1<<30) if seed is None else seed,'wave':1,'town':12,'barrier':0,'players':{p:{'energy':6,'points':0} for p in seats},'targets':[],'serial':0,'resolved':0,'spawned':0,'moves':[],'seq':0,'phase':'wave','winner':None,'reward':None,'upgrades':{'lazo':0,'campana':0},'result':''}
 start_wave(st);return st

def start_wave(st):
 st['spec']=wave_spec(st['wave'],st['seed']);st.update(targets=[],resolved=0,spawned=0,phase='wave',wave_steps=0,barrier=0,reward=None)
 for p in st['players'].values():p['energy']=6
 st['turn']=st['seats'][0];fill(st)

def total(st):return st['spec']['quota']+st['spec']['bosses']

def fill(st):
 spec=st['spec'];rng=random.Random(f"{st['seed']}:{st['wave']}:{st['serial']}")
 while len(st['targets'])<3 and st['spawned']<total(st):
  n=st['spawned'];boss=n>=spec['quota'];st['serial']+=1;kind=rng.choice(KINDS)
  st['targets'].append({'id':st['serial'],'lane':rng.choice(LANES),'kind':'jefe' if boss else kind,'name':BOSSES[n-spec['quota']] if boss else 'Bandido de utilería '+str(st['serial']),'hp':spec['hp']+(3 if boss else 0),'approach':spec['approach']+(2 if boss else 0),'boss':boss})
  st['spawned']+=1

def legal_actions(st,pid):
 if st['winner'] is not None or st['phase']!='wave' or st['turn']!=pid or pid not in st['players']:return []
 a=['descansar','barrera'];energy=st['players'][pid]['energy']
 if energy>=1:a.append('lazo')
 if energy>=3:a.append('campana')
 return a

def play(st,pid,action,target=None):
 if action not in legal_actions(st,pid):raise ValueError('Acción fuera de turno o sin energía')
 chosen=next((t for t in st['targets'] if t['id']==target),None)
 if action=='lazo' and (type(target) is not int or chosen is None):raise ValueError('Objetivo inválido')
 p=st['players'][pid];saved=0;damage=0;missed=0
 if action=='lazo':p['energy']-=1;chosen['hp']=max(0,chosen['hp']-(3+st['upgrades']['lazo']))
 elif action=='campana':
  p['energy']-=3
  for t in st['targets']:t['hp']=max(0,t['hp']-(2+st['upgrades']['campana']))
 elif action=='barrera':st['barrier']=min(3,st['barrier']+2);p['energy']=min(6,p['energy']+1)
 else:p['energy']=min(6,p['energy']+3)
 for t in list(st['targets']):
  if t['hp']==0:st['targets'].remove(t);st['resolved']+=1;saved+=1;p['points']+=15 if t['boss'] else 5
 # A lasso holds its target for this turn. Other targets still approach.
 for t in list(st['targets']):
  if t is chosen and action=='lazo':continue
  t['approach']-=1
  if t['approach']<=0:
   st['targets'].remove(t);st['resolved']+=1;missed+=1
   if st['barrier']:st['barrier']-=1
   else:st['town']=max(0,st['town']-1);damage+=1
 st['wave_steps']+=1;st['seq']+=1
 event={'pid':pid,'action':action,'target':target,'saved':saved,'missed':missed,'damage':damage,'wave':st['wave'],'seq':st['seq']}
 st['moves'].append(event)
 # Keep a bounded event log for long sessions.
 st['moves']=st['moves'][-30:]
 if st['town']==0:st['phase']='over';st['winner']=[]
 elif st['resolved']>=total(st):
  st['town']=min(12,st['town']+2)
  for q in st['players'].values():q['points']+=20
  if st['wave']==300:st['winner']=list(st['seats']);st['phase']='over'
  else:st['phase']='reward';st['reward']='Elegí lazo, campana o reparar. No cuesta dinero ni puntos.'
 else:fill(st)
 st['turn']=st['seats'][(st['seats'].index(pid)+1)%len(st['seats'])]
 return event

def continue_wave(st,pid,reward='reparar'):
 if st['phase']!='reward' or st['winner'] is not None or pid!=st['seats'][0] or reward not in ('lazo','campana','reparar'):raise ValueError('Recompensa inválida')
 if reward=='reparar':st['town']=min(12,st['town']+3)
 else:st['upgrades'][reward]=min(3,st['upgrades'][reward]+1)
 st['wave']+=1;start_wave(st)

def choose_move(st,pid,level=2):
 actions=legal_actions(st,pid)
 if not actions:return None,None
 if level==0:
  a=random.Random(f"bot:{st['seed']}:{st['seq']}:{pid}").choice(actions);return a,st['targets'][0]['id'] if a=='lazo' else None
 # Only public target info, no access to the future random stream.
 urgent=sorted(st['targets'],key=lambda t:(t['approach'],t['hp']))
 if 'campana' in actions and sum(t['hp']<=2+st['upgrades']['campana'] for t in urgent)>=2:return 'campana',None
 if 'lazo' in actions:return 'lazo',urgent[0]['id']
 return ('barrera',None) if urgent[0]['approach']<=1 else ('descansar',None)

def public_state(st):
 return {k:st[k] for k in ('wave','town','barrier','turn','seq','phase','winner','reward','upgrades')}|{'scene':st['spec']['scene'],'weather':st['spec']['weather'],'daytime':st['spec']['daytime'],'resolved':st['resolved'],'total':total(st),'targets':[dict(t) for t in st['targets']],'players':{p:dict(d) for p,d in st['players'].items()},'actions':legal_actions(st,st['turn'])}
