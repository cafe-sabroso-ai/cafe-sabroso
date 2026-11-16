"""Fictional arcade wave groups: no ballistics, real weapons advice or money."""
import random,math
DIRECTIONS=('izquierda','frente','derecha','atras','puerta','ventana')
SCENES=('Casa embrujada','Parque embrujado','Castillo','Cementerio','Hospital abandonado','Escuela','Barco fantasma','Mina','Supermercado','Subte')
TYPES=('lento','normal','rápido','muy rápido','resistente','acorazado','Mundial')
WEAPONS={'cuchillo':2,'espada':3,'ametralladora':4,'bomba':6}
BOSSES=('Guardián de niebla','Coloso de hojalata','Sombra del portón')
DINO_TYPES=('lento','corredor veloz','acorazado con cuernos','volador','nadador','gigante de cuello largo','guardián Mundial')
DINO_BOSSES=('Tiranosaurio rex','Guardián de cuernos','Coloso de cuello largo','Alas de tormenta','Señor del río')
DINO_SCENES=('Selva','Volcán','Desierto','Pantano','Cueva','Isla','Mar','Montañas','Playa','Glaciar','Cañón','Ruinas antiguas','Bosque de niebla','Tormenta')
def is_dino(st):return st.get('mode')=='dinosaurios'
def boss_total(st):return (5 if is_dino(st) else 3) if st['wave']==300 else 1

def quota(wave):return 10+5*(wave-1)

def new_game(seats,seed=None,mode='zombi'):
    if mode not in ('zombi','dinosaurios'):raise ValueError('Modo inválido')
    if not 1<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Escuadrón inválido')
    st={'mode':mode,'acted_players':[],'seats':list(seats),'seed':random.randrange(1<<30) if seed is None else seed,'players':{p:{'lives':3,'weapon':'espada','power':0,'shield':0,'points':0,'bomb_wait':0} for p in seats},'wave':1,'turn':seats[0],'phase':'wave','targets':[],'serial':0,'spawned':0,'kills':0,'bosses_beaten':0,'bosses_spawned':0,'losses':0,'steps':0,'winner':None,'seq':0,'reward':None,'scene':None}
    start_wave(st);return st

def alive(st):return [q for q in st['seats'] if st['players'][q]['lives']>0]

def start_wave(st):
    rng=random.Random(st['seed']+st['wave']*101);st.update(phase='wave',targets=[],spawned=0,kills=0,bosses_beaten=0,bosses_spawned=0,losses=0,steps=0,reward=None,scene=rng.choice(DINO_SCENES if is_dino(st) else SCENES),budget=150+min(30,st['wave']))
    if st['wave']==300:
        for p in st['players'].values():p['lives']=min(10,p['lives'])
    st['turn']=alive(st)[0];fill_targets(st)

def entrance_event(st,target):
    direction=target['direction']
    if direction not in ('puerta','ventana'):return
    st['environment_seq']=st.get('environment_seq',0)+1
    kind='door' if direction=='puerta' else 'window'
    noun='manada' if is_dino(st) else 'grupo de zombis'
    text=(f"Se abrió una puerta: entra {noun} {target['id']}." if kind=='door' else f"Se rompió el vidrio de una ventana: entra {noun} {target['id']}.")
    event={'id':st['environment_seq'],'kind':kind,'target':target['id'],'direction':direction,'text':text,'wave':st['wave']}
    st.setdefault('environment_events',[]).append(event)
    st['environment_events']=st['environment_events'][-8:]

def fill_targets(st):
    needed=quota(st['wave']);chunk=max(1,math.ceil(needed/6));rng=random.Random(st['seed']+st['wave']*8191+st['serial']*31)
    while len(st['targets'])<3 and st['spawned']<needed:
        count=min(chunk,needed-st['spawned']);kind=min(6,(st['wave']-1)//40);kind=rng.randint(0,kind);hp=2+kind+min(6,st['wave']//50);st['serial']+=1
        st['targets'].append({'id':st['serial'],'direction':'arriba' if is_dino(st) and kind==3 else rng.choice(DIRECTIONS),'kind':(DINO_TYPES if is_dino(st) else TYPES)[kind],'count':count,'hp':hp,'max_hp':hp,'approach':6-kind//2,'boss':False,'name':('Manada ' if is_dino(st) else 'Grupo ')+str(st['serial'])});st['spawned']+=count;entrance_event(st,st['targets'][-1])
    if st['kills']>=needed:
        final=boss_total(st)
        while len(st['targets'])<3 and st['bosses_spawned']<final:
            index=st['bosses_spawned'];hp=8+min(12,st['wave']//20);st['serial']+=1
            st['targets'].append({'id':st['serial'],'direction':'arriba' if is_dino(st) and index==3 else rng.choice(DIRECTIONS),'kind':'jefe','count':1,'hp':hp,'max_hp':hp,'approach':6,'boss':True,'name':(DINO_BOSSES if is_dino(st) else BOSSES)[index]});st['bosses_spawned']+=1;entrance_event(st,st['targets'][-1])

def choose_weapon(st,pid,weapon):
    if st['winner'] is not None or pid not in st['players'] or not st['players'][pid]['lives'] or weapon not in WEAPONS:raise ValueError('Arma arcade inválida')
    st['players'][pid]['weapon']=weapon

def lose_life(st,pid):
    p=st['players'][pid]
    if p['shield']:p['shield']-=1;return False
    p['lives']=max(0,p['lives']-1);st['losses']+=1;return True

def finish_if_dead(st):
    if not alive(st):st['winner']=[];st['phase']='over';return True
    return False

def next_turn(st,pid):
    living=alive(st)
    if not living:return
    i=st['seats'].index(pid);st['turn']=next(st['seats'][(i+j)%len(st['seats'])] for j in range(1,len(st['seats'])+1) if st['seats'][(i+j)%len(st['seats'])] in living)

def wave_reward(st):
    cap=10 if st['wave']==300 else 20
    flawless=st['losses']==0
    if flawless:
        for q in alive(st):st['players'][q]['lives']=min(cap,st['players'][q]['lives']+1)
    rng=random.Random(st['seed']+st['wave']*53);reward=rng.choice(('escudo','potencia','puntos'));st['reward']={'kind':reward,'flawless':flawless}
    for q in alive(st):
        p=st['players'][q];p['points']+=20
        if reward=='escudo':p['shield']=min(3,p['shield']+1)
        elif reward=='potencia':p['power']=min(8,p['power']+1)
        else:p['points']+=20
    if st['wave']==300:st['winner']=alive(st);st['phase']='over'
    else:st['phase']='reward'

def attack(st,pid,target_id):
    if st['winner'] is not None or st['phase']!='wave' or st['turn']!=pid or pid not in alive(st) or type(target_id) is not int:raise ValueError('Ataque fuera de turno')
    target=next((t for t in st['targets'] if t['id']==target_id),None)
    if target is None:raise ValueError('Grupo inexistente')
    p=st['players'][pid];weapon=p['weapon']
    if weapon=='bomba' and p['bomb_wait']:raise ValueError('Bomba recargando: elegí otra arma')
    damage=WEAPONS[weapon]+p['power'];target['hp']=max(0,target['hp']-damage);st['steps']+=1;st['seq']+=1
    if pid not in st['acted_players']:st['acted_players'].append(pid)
    for q in st['players'].values():q['bomb_wait']=max(0,q['bomb_wait']-1)
    if weapon=='bomba':p['bomb_wait']=2
    cleared=target['hp']==0
    if cleared:
        if target['boss']:st['bosses_beaten']+=1;p['points']+=10
        else:st['kills']+=target['count'];p['points']+=target['count']
        st['targets'].remove(target)
    lost=0
    for other in st['targets']:
        if other is target:continue
        other['approach']-=1
        if other['approach']<=0:
            lost+=int(lose_life(st,pid));other['approach']=4
    if not finish_if_dead(st):
        fill_targets(st)
        if st['kills']>=quota(st['wave']) and st['bosses_beaten']==boss_total(st):wave_reward(st)
        else:next_turn(st,pid)
    return {'cleared':cleared,'count':target['count'] if cleared and not target['boss'] else 0,'boss':target['boss'],'name':target['name'],'lost':lost,'weapon':weapon,'direction':target['direction']}

def expire_wave(st):
    if st['phase']!='wave' or st['winner'] is not None:raise ValueError('Oleada no activa')
    for q in alive(st):st['players'][q]['shield']=0;lose_life(st,q)
    if not finish_if_dead(st):st['phase']='retry'
    st['seq']+=1

def continue_wave(st):
    if st['phase'] not in ('reward','retry') or st['winner'] is not None:raise ValueError('No corresponde continuar')
    old_losses=st['losses'];retry=st['phase']=='retry'
    if not retry:st['wave']+=1
    start_wave(st)
    if retry:st['losses']=old_losses

def buy(st,pid,item):
    if st['phase']!='reward' or st['winner'] is not None or pid not in alive(st) or item not in ('potencia','escudo'):raise ValueError('Mejora no disponible')
    p=st['players'][pid];key='power' if item=='potencia' else 'shield';cap=8 if item=='potencia' else 3;price=30 if item=='potencia' else 15
    if p['points']<price or p[key]>=cap:raise ValueError('Faltan puntos virtuales o está al máximo')
    p['points']-=price;p[key]+=1

def bot_target(st):
    return min(st['targets'],key=lambda t:(t['approach'],-t['boss'],t['hp']))['id'] if st['targets'] else None

def clues(st):
    return ('Oleada '+str(st['wave'])+'. Cuota '+str(quota(st['wave']))+', mataste '+str(st['kills'])+', quedan '+str(quota(st['wave'])-st['kills'])+'. Jefes vencidos '+str(st['bosses_beaten'])+' de '+str(boss_total(st))+'. '+'. '.join(t['name']+', '+t['kind']+', '+str(t['count'])+' en grupo, '+t['direction']+', resistencia '+str(t['hp'])+', se acerca en '+str(t['approach'])+' acciones' for t in sorted(st['targets'],key=lambda t:t['approach']))+'.')
