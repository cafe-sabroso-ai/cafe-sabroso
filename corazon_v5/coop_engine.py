"""Local cooperative house. No realtime attacks, no production registration."""
from copy import deepcopy
from collections import deque
import re,unicodedata
import house_engine as solo
from characters import CHARACTERS
SUGGESTIONS=['Compañero App','Guardián App','Soldado App','Capitán Pantufla','Doña Chapoteo','Zombi No Gracias']
FREE={'left','right','weapon_cuchillo','weapon_disparo'}
ACTION={'walk','run','back','open','close','bar','pass'}|FREE|{'attack_z'+str(i) for i in range(1,11)}|{'attack_jefe'}

def nickname(value,existing=()):
    value=unicodedata.normalize('NFKC',value)
    value=''.join(c for c in value if c.isprintable() and unicodedata.category(c) not in ('Cf','Cc'))
    value=re.sub(r'\s+',' ',value).strip()[:24]
    if not value:raise ValueError('Escribí un apodo de hasta 24 letras, números o signos.')
    if any(c in value for c in '<>'):raise ValueError('Usá texto simple, sin signos de etiqueta.')
    base=value;number=2
    while value.casefold() in {x.casefold() for x in existing}:
        suffix=' '+str(number);value=base[:24-len(suffix)]+suffix;number+=1
    return value

def player(pid,name,character):
    if character not in CHARACTERS:raise ValueError('Elegí uno de los cuatro cuerpos y voces.')
    return {'id':pid,'name':name,'character':character,'room':'entrada','facing':'norte','known':['entrada'],'weapon':'cuchillo','lives':3,'connected':True,'removed':False,'path':['entrada'],'last_action':'inicio'}

def new_game():
    base=solo.new_game()
    return {k:deepcopy(base[k]) for k in ('door','enemies','kills','total','boss_spawned','boss_beaten','next_enemy','pool_effect','revealed')}|{'players':[],'phase':'lobby','round':1,'turn':None,'acted':[],'paused':False,'pause_reason':'','cleared':False,'finished':False,'enemy_phases':0,'newborn':[],'event':0}

def active(st):return [p for p in st['players'] if not p['removed'] and p['lives']>0]
def find(st,pid):return next(p for p in st['players'] if p['id']==pid)

def path(a,b,door,passable=True):
    if a==b:return []
    q=deque([(a,[])]);seen={a}
    while q:
        node,steps=q.popleft()
        for nxt in solo.ROOMS[node]['exits'].values():
            if nxt in seen:continue
            if passable and solo.door_between(node,nxt) and door['state'] in ('cerrada','trabada'):continue
            if nxt==b:return steps+[nxt]
            seen.add(nxt);q.append((nxt,steps+[nxt]))
    return None

def target(st,e):
    options=[]
    for i,p in enumerate(active(st)):
        steps=path(e['room'],p['room'],st['door'])
        if steps is not None:options.append((len(steps),i,p,steps))
    blocked=False
    if not options:
        blocked=True
        for i,p in enumerate(active(st)):
            steps=path(e['room'],p['room'],st['door'],False)
            if steps is not None:options.append((len(steps),i,p,steps))
    if not options:return None,[],blocked
    _,_,p,steps=min(options,key=lambda o:(o[0],o[1]))
    return p,steps,blocked

def orientation(st,pid=None):
    if st['phase']=='lobby':return 'Sala local. '+str(len([p for p in st['players'] if not p['removed']]))+' personas. Se necesitan de dos a cuatro. La persona que creó la sala inicia.'
    turn=find(st,st['turn'])['name'] if st['turn'] else 'nadie'
    text='Ronda '+str(st['round'])+'. '+('Pausa: '+st['pause_reason']+'. ' if st['paused'] else '')+('Casa despejada. ' if st['cleared'] else 'Todo el equipo sin vidas. ' if st['finished'] else 'Turno de '+turn+'. ')
    text+=' '.join(p['name']+': '+solo.ROOMS[p['room']]['name']+', mira al '+p['facing']+', '+str(p['lives'])+' vidas'+(', desconectado' if not p['connected'] else '')+'.' for p in st['players'] if not p['removed'])
    text+=' Puerta '+st['door']['state']+', resistencia '+str(st['door']['hp'])+'. Vencidos '+str(st['kills'])+' de diez. Jefe '+('vencido' if st['boss_beaten'] else 'presente' if st['boss_spawned'] else 'pendiente')+'. '
    if pid:
        p=find(st,pid);text+='Tus salidas: '+'. '.join(d+' a '+solo.ROOMS[r]['name'] for d,r in solo.ROOMS[p['room']]['exits'].items())+'. '
    for e in st['enemies']:
        if e['hp']<=0:continue
        t,steps,blocked=target(st,e)
        text+=e['name']+' en '+solo.ROOMS[e['room']]['name']+', resistencia '+str(e['hp'])+'. '
        if t:text+='Objetivo previsto: '+t['name']+('. Debe superar la puerta.' if blocked else '. ')+(' Contacto: ataca en '+str((e['contact']+(1 if e['runner'] else 0))//(2 if e['runner'] else 1))+' fases enemigas.' if not steps else '')+' '
    text+='No hay reloj. Los enemigos actúan una vez cuando la última persona confirma su acción de la ronda. Los objetivos se recalculan si alguien cambia de habitación.'
    return text

def start(st):
    if st['phase']!='lobby':raise ValueError('La sala ya empezó.')
    seats=[p for p in st['players'] if not p['removed']]
    if not 2<=len(seats)<=4:raise ValueError('Se necesitan de dos a cuatro personas.')
    if not all(p['connected'] for p in seats):raise ValueError('Esperá a que se conecten todas las personas.')
    st['phase']='play';st['turn']=seats[0]['id']
    return 'Equipo listo. Una acción por persona y después una fase enemiga. Sin bloqueo entre compañeros ni fuego amigo. Diez enemigos y un jefe compartidos. '+orientation(st)

def spawn(st,notes):
    if not all(e['hp']<=0 for e in st['enemies']):return
    if st['kills']<10:
        n=st['next_enemy'];st['enemies']=[solo.make_enemy(n),solo.make_enemy(n+1)];st['next_enemy']+=2
        notes.append('Nueva pareja: '+st['enemies'][0]['name']+' y '+st['enemies'][1]['name']+'. Salen de la pileta del patio. No actúan en esta fase de aparición.')
    elif not st['boss_spawned']:
        st['enemies']=[solo.make_enemy(11,True)];st['boss_spawned']=True
        notes.append('Los diez vencidos. Sale de la pileta el Guardián del patio, jefe final, resistencia cuatro. No actúa en esta fase de aparición.')
    else:
        st['cleared']=True;st['phase']='won';st['turn']=None;notes.append('¡Casa despejada! Victoria del equipo: diez enemigos y jefe final vencidos.');return
    st['newborn']=[e['id'] for e in st['enemies']];st['revealed']=True
    st['pool_effect']={**(st.get('pool_effect') or {}),'kind':'both' if st.get('pool_effect') else 'emerge','enemies':st['newborn'][:]}

def enemy_phase(st):
    notes=['Fase enemiga de la ronda '+str(st['round'])+'.'];st['enemy_phases']+=1
    for e in st['enemies']:
        if e['hp']<=0:continue
        p,steps,blocked=target(st,e)
        if not p:break
        speed=2 if e['runner'] else 1
        if not steps:
            e['contact']-=speed
            if e['contact']<=0:
                p['lives']=max(0,p['lives']-1);e['contact']=5
                notes.append(e['name']+' alcanza a '+p['name']+': pierde una vida.'+(' Sin vidas, queda como espectador.' if not p['lives'] else ''))
            else:notes.append(e['name']+' cerca de '+p['name']+', ataca en '+str((e['contact']+speed-1)//speed)+' fases enemigas.')
        else:
            e['approach']=max(0,e['approach']-speed)
            if e['approach']>0:notes.append(e['name']+' avanza '+str(speed)+' pasos hacia '+p['name']+'.');continue
            nxt=steps[0]
            if solo.door_between(e['room'],nxt) and st['door']['state'] in ('cerrada','trabada'):
                st['door']['hp']=max(0,st['door']['hp']-speed)
                if not st['door']['hp']:st['door']['state']='rota';notes.append('La puerta se rompe. No se repara en este piloto.')
                else:notes.append('Golpes en la puerta. Resistencia '+str(st['door']['hp'])+'.')
            else:
                e['room']=nxt;e['approach']=2;e['contact']=5
                notes.append(e['name']+' entra en '+solo.ROOMS[nxt]['name']+'. No ataca al entrar.')
    st['newborn']=[]
    if not active(st):st['finished']=True;st['phase']='lost';st['turn']=None;notes.append('Todo el equipo quedó sin vidas. Fin de esta prueba.')
    return notes

def next_turn(st,notes):
    seats=active(st);remaining=[p for p in seats if p['id'] not in st['acted']]
    if not remaining:
        notes.extend(enemy_phase(st));spawn(st,notes)
        if st['phase']!='play':return
        st['round']+=1;st['acted']=[];remaining=active(st)
    st['turn']=remaining[0]['id'] if remaining else None

def act(original,pid,action):
    st=deepcopy(original);p=find(st,pid)
    if st['phase']!='play' or st['paused']:raise ValueError('La partida está en pausa o terminó.')
    if p['removed'] or p['lives']<=0 or st['turn']!=pid:raise ValueError('No es tu turno. Podés escuchar orientación.')
    if action not in ACTION:raise ValueError('Acción no disponible.')
    notes=[];accepted=False;st['pool_effect']=None
    if action=='pass':accepted=True;notes.append(p['name']+' pasa el turno.');p['last_action']='pass';p['path']=[p['room']]
    else:
        temp=solo.new_game(p['character'])
        for k in ('door','enemies','kills','total','boss_spawned','boss_beaten','next_enemy','revealed'):temp[k]=deepcopy(st[k])
        for k in ('room','facing','known','weapon','lives'):temp[k]=deepcopy(p[k])
        # Solo validator/action mechanics, but no solo enemy phase or wave spawn.
        new=solo.act(temp,action,advance=False,spawn=False)
        accepted=new['step']>temp['step']
        for k in ('room','facing','known','weapon','path','last_action'):p[k]=deepcopy(new[k])
        for k in ('door','enemies','kills','boss_spawned','boss_beaten','next_enemy','revealed','pool_effect'):st[k]=deepcopy(new[k])
        notes.append(p['name']+': '+new.get('_notes',new['last'].split(solo.orientation(new))[0]).replace('Trabajar la puerta también deja avanzar a los enemigos.','Esta acción entrega el turno; los enemigos actúan al finalizar la ronda.').replace('Desde la entrada no alcanzás la puerta del salón.','Desde esta habitación no alcanzás la puerta del salón.'))
    if not accepted and action not in FREE:return st,' '.join(notes),False
    st['event']+=1
    if accepted:
        st['acted'].append(pid)
        # Wave arrival is at round boundary, so nobody loses their action to a mid-round respawn.
        next_turn(st,notes)
    return st,' '.join(notes),accepted
