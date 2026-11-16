"""Five original haunted-park routes, generated safe logic challenges, no factual bank."""
import random
ROUTES=('Galería de espejos','Jardín de faroles','Taller de nubes','Pasillo de cortinas','Biblioteca del viento')
SIDES=('extremo izquierdo','izquierda','centro','derecha','extremo derecho')
ENCOUNTERS=('fantasma de luz','bruja de burbujas','trampa de hojas')
CATEGORIES=('Secuencia','Memoria','Cuenta','Orden','Código')

def challenge(kind,level=2,rng=None):
    rng=rng or random;top=5+max(0,min(5,level))*3
    if kind=='Secuencia':
        start=rng.randint(1,top);step=rng.randint(1,3);answer=str(start+3*step);text='Completá la secuencia: '+', '.join(str(start+i*step) for i in range(3))+'. ¿Qué sigue?';wrong=[str(start+3*step+1),str(start+3*step+2)]
    elif kind=='Memoria':
        words=rng.sample(['vela','luna','hoja','nube','llave','flor'],3);answer=words[1];text='Escuchá las tres palabras: '+', '.join(words)+'. ¿Cuál está en el medio?';wrong=[words[0],words[2]]
    elif kind=='Cuenta':
        a=rng.randint(1,top);b=rng.randint(1,top);answer=str(a+b);text='Una caja tiene '+str(a)+' luces y otra '+str(b)+'. ¿Cuántas luces hay en total?';wrong=[str(a+b+1),str(a+b+2)]
    elif kind=='Orden':
        nums=rng.sample(list(range(1,top+4)),3);answer=str(max(nums));text='Elegí el número mayor entre '+', '.join(map(str,nums))+'.';wrong=[str(n) for n in nums if n!=max(nums)]
    elif kind=='Código':
        nums=rng.sample(list(range(1,10)),3);answer=str(nums[-1]);text='El código es '+', '.join(map(str,nums))+'. ¿Cuál es el último número?';wrong=[str(nums[0]),str(nums[1])]
    else:raise ValueError('Reto desconocido')
    options=[answer]+wrong;rng.shuffle(options);return {'category':kind,'text':text,'options':options,'answer':options.index(answer)}

def new_game(seats,seed=None):
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
    return {'seats':list(seats),'seed':random.randrange(1<<30) if seed is None else seed,'boards':{q:{'visited':[],'score':0,'lives':3,'done':False,'log':[]} for q in seats},'turn':seats[0],'stage':'door','challenge':None,'door':None,'encounter':None,'country':None,'winner':None,'seq':0,'result':''}

def doors(st,pid):
    b=st['boards'].get(pid)
    return [n for n in range(1,6) if n not in b['visited']] if b and not b['done'] and st['stage']=='door' and st['turn']==pid and st['winner'] is None else []

def choose_door(st,pid,door,country,level=2):
    if type(door) is not int or door not in doors(st,pid):raise ValueError('Puerta inválida o fuera de turno')
    b=st['boards'][pid];rng=random.Random(st['seed']+st['seats'].index(pid)*65537+len(b['visited'])*997+door*31)
    kind=rng.choice(CATEGORIES);st.update(door=door,country=country,encounter=rng.choice(ENCOUNTERS),challenge=challenge(kind,level,rng),stage='challenge');return st['challenge']

def resolve(st,pid,answer):
    if st['stage']!='challenge' or st['turn']!=pid or st['winner'] is not None or not st['challenge'] or not (answer is None or type(answer) is int and answer in (0,1,2)):raise ValueError('Respuesta inválida o fuera de turno')
    b=st['boards'][pid];right=answer==st['challenge']['answer'];door=st['door']
    if right:b['score']+=1
    else:b['lives']-=1
    b['visited'].append(door);b['log'].append({'door':door,'country':st['country'],'category':st['challenge']['category'],'encounter':st['encounter'],'correct':right});b['done']=not b['lives'] or len(b['visited'])==5
    st['seq']+=1;st['last_correct']=right;st['revealed']=st['challenge']['options'][st['challenge']['answer']];st['stage']='door';st['challenge']=None
    active=[q for q in st['seats'] if not st['boards'][q]['done']]
    if not active:
        best=max(st['boards'][q]['score'] for q in st['seats']);st['winner']=[q for q in st['seats'] if st['boards'][q]['score']==best]
    else:
        i=st['seats'].index(pid);st['turn']=next(st['seats'][(i+j)%len(st['seats'])] for j in range(1,len(st['seats'])+1) if st['seats'][(i+j)%len(st['seats'])] in active)
    return right

def door_timeout(st,pid):
    available=doors(st,pid)
    if not available:raise ValueError('No hay puertas')
    # No decision hidden on timeout: enter lowest available door, then lose challenge by timeout.
    return min(available)

def bot_answer(st,level=2,rng=None):
    rng=rng or random;answer=st['challenge']['answer'];chance=(.4,.55,.7,.8,.9,.97)[max(0,min(5,level))]
    return answer if rng.random()<chance else rng.choice([i for i in range(3) if i!=answer])

def clues(st,pid):
    b=st['boards'][pid];available=[n for n in range(1,6) if n not in b['visited']]
    return 'Puertas disponibles: '+('; '.join(str(n)+', '+SIDES[n-1]+', '+ROUTES[n-1] for n in available) or 'ninguna')+'. '+str(b['score'])+' capturas y '+str(b['lives'])+' vidas. Cada puerta es una ruta independiente desde el vestíbulo.'
