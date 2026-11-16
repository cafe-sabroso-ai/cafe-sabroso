"""Original turn-based race, no bets. Public energy, distances and powers."""
import random
MODES=('caballos','autitos','aviones')
WEATHER=('sol','nublado','lluvia','tormenta')

def new_game(seats,mode='caballos',rng=None):
    if mode not in MODES or len(seats)<2 or len(seats)>20 or len(set(seats))!=len(seats):raise ValueError('Carrera inválida')
    rng=rng or random
    return {'seats':list(seats),'mode':mode,'turn':seats[0],'distance':{p:0 for p in seats},'energy':{p:5 for p in seats},'powers':{p:{'turbo':1,'escudo':1,'viento':1} for p in seats},'shields':{p:False for p in seats},'slow':{p:False for p in seats},'moves':[],'round':1,'winner':None,'podium':[],'weather':rng.choice(WEATHER),'result':''}

def ranking(st):return sorted(st['seats'],key=lambda p:(-st['distance'][p],st['seats'].index(p)))

def legal_actions(st,pid):
    if st['winner'] is not None or st['turn']!=pid:return []
    actions=['trotar']
    if st['energy'][pid]>=2:actions.append('acelerar')
    if st['mode']!='caballos':actions.extend(p for p,n in st['powers'][pid].items() if n)
    return actions

def play(st,pid,action,rng=None):
    if action not in legal_actions(st,pid):raise ValueError('Acción fuera de turno o sin energía/poder')
    rng=rng or random;target=None;blocked=False
    if action=='acelerar':advance=rng.randint(7,11);st['energy'][pid]-=2
    else:advance=rng.randint(3,5);st['energy'][pid]=min(5,st['energy'][pid]+1)
    if action in ('turbo','escudo','viento'):
        st['powers'][pid][action]-=1
        if action=='turbo':advance+=7
        elif action=='escudo':st['shields'][pid]=True
        elif action=='viento':
            target=next(p for p in ranking(st) if p!=pid)
            if st['shields'][target]:st['shields'][target]=False;blocked=True
            else:st['slow'][target]=True
    if st['slow'][pid]:advance=max(1,advance-4);st['slow'][pid]=False
    # Weather is cosmetic and audible, not a hidden advantage for one country.
    st['distance'][pid]=min(100,st['distance'][pid]+advance)
    move={'pid':pid,'action':action,'advance':advance,'target':target,'blocked':blocked,'round':st['round']};st['moves'].append(move)
    # Finish at the end of a complete round so seat order does not decide ties.
    count=len(st['moves']);st['turn']=st['seats'][count%len(st['seats'])]
    if count%len(st['seats'])==0:
        if max(st['distance'].values())>=100 or st['round']>=20:
            best=max(st['distance'].values());st['winner']=[p for p in st['seats'] if st['distance'][p]==best];st['podium']=ranking(st)
        else:st['round']+=1
    return move

def choose_move(st,pid,level=2,rng=None):
    rng=rng or random;actions=legal_actions(st,pid)
    if not actions:return None
    if level==0:return rng.choice(actions)
    if st['mode']!='caballos':
        if 'turbo' in actions and st['distance'][pid]>=80:return 'turbo'
        if 'escudo' in actions and not st['shields'][pid] and any(st['powers'][q]['viento'] for q in st['seats'] if q!=pid):return 'escudo'
        if 'viento' in actions and st['distance'][ranking(st)[0]]>st['distance'][pid]+8:return 'viento'
    return 'acelerar' if 'acelerar' in actions else 'trotar'
