"""Small solo, turn-based house exploration. Separate from classic wave rules."""
from copy import deepcopy
ROOMS={'entrada':{'name':'Entrada','exits':{'norte':'salon'}},'salon':{'name':'Salón','exits':{'sur':'entrada','este':'cocina'}},'cocina':{'name':'Cocina','exits':{'oeste':'salon','sur':'patio'}},'patio':{'name':'Patio','exits':{'norte':'cocina'}}}
HEADINGS=('norte','este','sur','oeste')

def make_enemy(number,boss=False):
    runner=not boss and number%2==1
    return {'id':'jefe' if boss else 'z'+str(number),'name':'Guardián del patio, jefe final' if boss else 'Zombi '+str(number)+(' corredor' if runner else ' caminante'),'runner':runner,'boss':boss,'pool_origin':boss or number>2,'room':'patio' if boss or number>2 else 'cocina','approach':6 if number>2 or boss else 8,'hp':4 if boss else 1 if runner else 2,'contact':5}

def new_game(character='tomas'):
    from characters import CHARACTERS
    if character not in CHARACTERS:raise ValueError('Personaje inválido')
    return {'character':character,'weapon':'cuchillo','pool_effect':None,'room':'entrada','facing':'norte','known':['entrada'],'revealed':False,'door':{'state':'cerrada','hp':4,'max':4},'lives':3,'step':0,'paused':False,'finished':False,'cleared':False,'last':'','event':0,'last_action':'inicio','path':['entrada'],'kills':0,'total':10,'boss_spawned':False,'boss_beaten':False,'enemies':[make_enemy(1),make_enemy(2)],'next_enemy':3}


def door_between(a,b):return {a,b}=={'salon','cocina'}
def visible(st):return [e for e in st['enemies'] if e['hp']>0 and (st['revealed'] or e['room']==st['room'])]
def direction(st,target):
    for direction,room in ROOMS[st['room']]['exits'].items():
        if room==target:return direction
    return 'más allá del salón'

def orientation(st):
    exits=[]
    for d,r in ROOMS[st['room']]['exits'].items():
        label=ROOMS[r]['name']
        if door_between(st['room'],r):label+='; puerta '+st['door']['state']+(', resistencia '+str(st['door']['hp']) if st['door']['state'] in ('cerrada','trabada') else '')
        exits.append(d+': '+label)
    enemies=visible(st)
    threats=' '.join(e['name']+', '+('corre dos pasos por acción' if e['runner'] else 'camina un paso por acción')+', '+('en esta habitación, ataca en '+str((e['contact']+(1 if e['runner'] else 0))//(2 if e['runner'] else 1))+' acciones' if e['room']==st['room'] else 'en '+ROOMS[e['room']]['name']+', hacia '+direction(st,e['room']))+', resistencia '+str(e['hp'])+'.' for e in enemies)
    hidden=any(e['hp']>0 for e in st['enemies']) and not enemies
    if hidden:threats='Se escuchan pasos detrás de la puerta, algunos rápidos. No sabés cuántos enemigos hay.'
    progress=' Vencidos '+str(st['kills'])+' de diez zombis. '+('Jefe final vencido. ' if st['boss_beaten'] else 'Jefe final presente. ' if st['boss_spawned'] else 'Después de los diez aparece el jefe final en el patio. ')
    return ROOMS[st['room']]['name']+'. Mirás al '+st['facing']+'. Salidas: '+'. '.join(exits)+'. '+threats+(' Pileta de agua celeste, al este del patio. No necesitás entrar al agua.' if st['room']=='patio' else '')+' Tenés '+str(st['lives'])+' vidas. '+progress+('Pausa. ' if st['paused'] else '')+('Casa despejada. ' if st['cleared'] else '')

def route(a,b):
    if a==b:return a
    graph={a:list(v['exits'].values()) for a,v in ROOMS.items()}
    queue=[(a,[])];seen={a}
    for node,path in queue:
        for nxt in graph[node]:
            if nxt in seen:continue
            if nxt==b:return (path+[nxt])[0]
            seen.add(nxt);queue.append((nxt,path+[nxt]))
    return a

def advance_enemies(st):
    notes=[]
    for e in st['enemies']:
        if e['hp']<=0:continue
        speed=2 if e['runner'] else 1
        if e['room']==st['room']:
            if len(st.get('path',[]))>1:
                e['contact']=5
                notes.append(e['name']+' en esta habitación. Ataca en '+str((5+speed-1)//speed)+' acciones. Escuchá y elegí tu respuesta.')
                continue
            e['contact']-=speed
            if e['contact']<=0:
                st['lives']=max(0,st['lives']-1);e['contact']=5
                notes.append(e['name']+' te alcanza: perdés una vida.')
            else:notes.append(e['name']+' cerca: ataca en '+str((e['contact']+(1 if e['runner'] else 0))//(2 if e['runner'] else 1))+' acciones.')
            continue
        e['approach']=max(0,e['approach']-speed)
        if e['approach']>0:
            if st['revealed']:notes.append(e['name']+' se acerca '+str(speed)+' pasos.')
            continue
        nxt=route(e['room'],st['room'])
        if door_between(e['room'],nxt) and st['door']['state'] in ('cerrada','trabada'):
            door=st['door'];door['hp']=max(0,door['hp']-speed)
            if door['hp']==0:
                door['state']='rota';st['revealed']=True
                notes.append('¡La puerta se rompe! El paso queda abierto. No podés volver a trabarla en esta prueba.')
            else:notes.append('Golpes en la puerta. Resistencia '+str(door['hp'])+'. '+('Está a punto de romperse.' if door['hp']<=2 else ''))
        else:
            e['room']=nxt;e['approach']=2;e['contact']=5
            if nxt==st['room']:st['revealed']=True;notes.append(e['name']+' entra en tu habitación. '+('Corre.' if e['runner'] else 'Camina.'))
            elif st['revealed']:notes.append(e['name']+' pasa a '+ROOMS[nxt]['name']+'.')
    if not st['lives']:st['finished']=True;notes.append('Te quedaste sin vidas. Reiniciar esta prueba es gratis y no cambia Oleadas.')
    return notes

def act(st,action,advance=True,spawn=True):
    """Returns a new state. Invalid/read/turn/pause never advance threats."""
    st=deepcopy(st);notes=[];st['path']=[st['room']];st['last_action']=action;st['pool_effect']=None
    if action=='restart':return new_game(st['character'])
    if action in ('weapon_cuchillo','weapon_disparo'):
        st['weapon']=action.removeprefix('weapon_');st['last']='Elegiste '+('cuchillo arcade' if st['weapon']=='cuchillo' else 'disparo arcade')+'. Mismo daño uno, sin munición ni compras. No gasta acción. '+orientation(st);return st
    if action=='read':st['last']='Orientación. '+orientation(st);return st
    if action=='pause':st['paused']=True;st['last']='Pausa. Nada se mueve ni ataca. '+orientation(st);return st
    if action=='resume':st['paused']=False;st['last']='Seguís explorando. '+orientation(st);return st
    if action in ('left','right'):
        i=HEADINGS.index(st['facing']);st['facing']=HEADINGS[(i+(-1 if action=='left' else 1))%4];st['last']='Girás hacia el '+st['facing']+'. '+orientation(st);st['event']+=1;return st
    if st['paused'] or st['finished']:
        st['last']='La prueba está en pausa o terminó. Elegí seguir o reiniciar. '+orientation(st);return st
    accepted=False
    if action in ('walk','back','run'):
        heading=HEADINGS[(HEADINGS.index(st['facing'])+2)%4] if action=='back' else st['facing']
        current=st['room'];hops=1
        for _ in range(hops):
            nxt=ROOMS[current]['exits'].get(heading)
            if not nxt:notes.append('No hay salida hacia el '+heading+'.');break
            if door_between(current,nxt) and st['door']['state'] in ('cerrada','trabada'):notes.append('La puerta está '+st['door']['state']+'. Tenés que abrirla primero.');break
            if action=='run' and nxt not in st['known']:notes.append('Para correr, primero conocé esa habitación caminando.');break
            if action=='run' and any(e['hp']>0 and e['room']==nxt for e in st['enemies']):notes.append('No corrés hacia una amenaza visible.');break
            current=nxt;st['room']=current;st['path'].append(current);accepted=True
            if current not in st['known']:st['known'].append(current)
            if any(e['hp']>0 and e['room']==current for e in st['enemies']):st['revealed']=True;break
        if accepted:notes.insert(0,('Corrés' if action=='run' else 'Retrocedés' if action=='back' else 'Caminás')+' hasta '+ROOMS[st['room']]['name']+'.')
    elif action in ('open','close','bar'):
        if st['room'] not in ('salon','cocina'):notes.append('Desde la entrada no alcanzás la puerta del salón.')
        elif st['door']['state']=='rota':notes.append('La puerta está rota. El paso queda libre.')
        elif action=='open':
            if st['door']['state']=='abierta':notes.append('La puerta ya está abierta.')
            else:st['door']['state']='abierta';st['revealed']=True;notes.append('Accionás el picaporte y abrís la puerta.');accepted=True
        elif action=='close':
            if st['door']['state']!='abierta':notes.append('La puerta ya está cerrada.')
            else:st['door'].update(state='cerrada',hp=min(4,st['door']['hp']),max=4);notes.append('Cerrás la puerta.');accepted=True
        elif st['door']['state']=='abierta':notes.append('Cerrá la puerta antes de trabarla.')
        elif st['door']['state']=='trabada':notes.append('Ya está trabada. Repetir no la repara.')
        else:st['door'].update(state='trabada',hp=6,max=6);notes.append('Trabás la puerta. Resistencia seis. Trabajar la puerta también deja avanzar a los enemigos.');accepted=True
    elif action.startswith('attack_'):
        eid=action.removeprefix('attack_');enemy=next((e for e in st['enemies'] if e['id']==eid and e['hp']>0 and e['room']==st['room']),None)
        if enemy:
            enemy['hp']-=1
            if enemy['hp']==0:
                if enemy.get('boss'):st['boss_beaten']=True
                else:st['kills']+=1
            if st['room']=='patio':
                st['pool_effect']={'kind':'fall','enemy':enemy['id'],'defeated':enemy['hp']==0}
                notes.append(enemy['name']+' cae en la pileta con un chapoteo. '+('Queda fuera de combate.' if enemy['hp']==0 else 'Vuelve a salir del agua; todavía resiste.'))
            notes.append('Ataque con '+st['weapon']+' arcade a '+enemy['name']+'. '+('Queda fuera de combate.' if enemy['hp']==0 else 'Resistencia restante '+str(enemy['hp'])+'.'));accepted=True
        else:notes.append('Ese enemigo no está a tu alcance en esta habitación.')
    else:notes.append('Acción no disponible.')
    if accepted:
        st['step']+=1
        if advance:notes+=advance_enemies(st)
        if spawn and all(e['hp']<=0 for e in st['enemies']):
            if st['kills']<10:
                first=st['next_enemy'];st['enemies']=[make_enemy(first),make_enemy(first+1)];st['next_enemy']+=2
                st['revealed']=True;st['pool_effect']={**(st['pool_effect'] or {}),'kind':'both' if st['pool_effect'] else 'emerge','enemies':[e['id'] for e in st['enemies']]}
                notes.append('Dos figuras salen de la pileta del patio con agua celeste. Nueva pareja anunciada: '+st['enemies'][0]['name']+' y '+st['enemies'][1]['name']+'. No atacan al aparecer. Primero escuchá y elegí.')
            elif not st['boss_spawned']:
                st['enemies']=[make_enemy(11,True)];st['boss_spawned']=True;st['revealed']=True;st['pool_effect']={**(st['pool_effect'] or {}),'kind':'both' if st['pool_effect'] else 'emerge','enemies':['jefe']}
                notes.append('Derrotaste a los diez. Sale de la pileta el jefe final, Guardián del patio, en el patio. Camina, resistencia cuatro. No ataca al aparecer.')
            elif st['boss_beaten']:
                st['cleared']=True;notes.append('Casa despejada: diez zombis y jefe final vencidos. Podés recorrer las cuatro áreas sin enemigos.')
        st['event']+=1
    st['_notes']=' '.join(notes)
    st['last']=' '.join(notes)+' '+orientation(st)
    return st
