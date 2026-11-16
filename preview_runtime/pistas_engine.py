"""Adiviná con Pistas: original word bank and public-clue-only bot inference."""
import random,re,unicodedata
BANK={
'animales':[
 ('gato',['Es un animal doméstico.','Tiene bigotes y suele cazar ratones.','Maúlla y puede ronronear.']),
 ('perro',['Es un animal doméstico.','Suele salir a pasear con correa.','Ladra y mueve la cola.']),
 ('elefante',['Es un animal grande.','Tiene grandes orejas y colmillos.','Usa una trompa larga para tomar agua.']),
 ('jirafa',['Es un animal herbívoro.','Su pelaje tiene manchas.','Su cuello es muy largo.']),
 ('pingüino',['Es un ave que no vuela.','Nada muy bien y tiene alas como aletas.','Suele verse con el cuerpo blanco y negro, caminando erguido.']),
 ('abeja',['Es un insecto.','Visita flores y transporta polen.','Produce miel en la colmena.'])],
'comidas':[
 ('pizza',['Es una comida que suele compartirse.','Lleva una base de masa y puede tener tomate.','Se corta en porciones triangulares con queso encima.']),
 ('helado',['Es un postre.','Puede tener sabor a chocolate o vainilla.','Se sirve muy frío en un cucurucho o en un vasito.']),
 ('empanada',['Es una comida con relleno.','Se cierra doblando la masa.','Tiene repulgue y puede cocinarse al horno o frita.']),
 ('pan',['Se hace con harina.','La masa puede llevar levadura.','Se hornea y se corta en rebanadas para hacer tostadas.']),
 ('banana',['Es una fruta.','Suele tener una cáscara amarilla.','Es alargada, curva y se pela antes de comer.']),
 ('zanahoria',['Es un vegetal.','La parte que comemos crece bajo tierra.','Es una raíz generalmente naranja, larga y crujiente.'])],
'objetos':[
 ('reloj',['Es un objeto que usamos todos los días.','Puede tener agujas o una pantalla con números.','Sirve para saber la hora.']),
 ('paraguas',['Se lleva en la mano cuando hace falta.','Tiene una tela que se abre sobre varillas.','Te cubre de la lluvia.']),
 ('llave',['Es un objeto pequeño.','Puede tener dientes y suele ser de metal.','Se mete en una cerradura para abrir una puerta.']),
 ('almohada',['Es un objeto blando.','Suele estar sobre la cama.','Apoyás la cabeza sobre ella para dormir.']),
 ('linterna',['Es un objeto portátil.','Suele usar pilas o una batería.','La llevás en la mano para alumbrar en la oscuridad.']),
 ('tijera',['Es una herramienta.','Tiene dos hojas unidas que se abren y cierran.','La usamos para cortar papel o tela.'])],
'transportes':[
 ('tren',['Es un medio de transporte.','Puede llevar muchos pasajeros en vagones.','Circula sobre rieles.']),
 ('avión',['Es un medio de transporte.','Lleva pasajeros por el cielo.','Tiene alas y despega desde una pista.']),
 ('barco',['Es un medio de transporte.','Puede transportar personas o carga.','Navega por el agua y puede atracar en un puerto.']),
 ('bicicleta',['Es un medio de transporte.','Tiene dos ruedas y manubrio.','La movés pedaleando.']),
 ('subte',['Es un transporte de la ciudad.','Tiene estaciones y vagones.','Viaja por túneles debajo de las calles.']),
 ('helicóptero',['Es un transporte aéreo.','Puede quedarse suspendido en el aire.','Se eleva con grandes palas que giran sobre el techo.'])],
'naturaleza':[
 ('luna',['Se ve en el cielo.','Su forma aparente cambia a lo largo del mes.','Es el satélite natural de la Tierra.']),
 ('arcoíris',['Aparece en el cielo.','Puede verse cuando hay sol y gotas de agua.','Es un arco de varios colores.']),
 ('volcán',['Es una formación de la Tierra.','Puede tener un cráter.','Cuando entra en erupción expulsa lava.']),
 ('nieve',['Es agua en estado sólido.','Cae del cielo cuando hace mucho frío.','Sus copos blancos pueden cubrir el suelo.']),
 ('isla',['Es una porción de terreno.','Puede estar en un río o en el mar.','Está rodeada de agua por todos lados.']),
 ('cascada',['Tiene que ver con el agua.','Suele formar espuma y un sonido continuo.','Es una caída de agua desde cierta altura.'])]
}
STOP={'es','un','una','de','la','el','los','las','y','o','en','se','que','con','por','para','su','sus','tiene','puede','suele','muy','lo','del','al','a','como','ser','le','antes','sobre','tus','te','hace','lleva'}

def clean(text):
    t=''.join(c for c in unicodedata.normalize('NFD',str(text).lower()) if unicodedata.category(c)!='Mn')
    return re.sub('[^a-z0-9 ]',' ',t).strip()

def words(text):return {w for w in clean(text).split() if len(w)>2 and w not in STOP}

def bot_guess(public_clues,category,rng=None):
    """No game state or hidden target enters this function."""
    rng=rng or random;tokens=words(' '.join(public_clues));rank=[]
    for answer,hints in BANK[category]:
        overlap=tokens & words(' '.join(hints));rank.append((len(overlap),answer))
    best=max(score for score,answer in rank)
    return rng.choice([answer for score,answer in rank if score==best]) if best>=1 else None

def new_game(seats,mode='sala'):
    if len(seats)<2 or len(set(seats))!=len(seats):raise ValueError('Se necesitan dos asientos')
    return {'seats':list(seats),'scores':{p:0 for p in seats},'mode':mode,'round':0,'stage':'setup' if mode=='solo' else 'category','turn':seats[0],'giver':seats[0],'giver_index':-1,'target':None,'category':None,'clues':[],'lives':{},'guessers':[],'guess_index':0,'used':set(),'winner':None,'seq':0,'result':''}

def start_round(st,category,rng=None,choices=None):
    rng=rng or random
    if category not in BANK:raise ValueError('Categoría inválida')
    st['round']+=1;st['seq']+=1
    if st['mode']=='guess':giver='narrator'
    elif st['mode']=='describe':giver=st['seats'][0]
    else:
        st['giver_index']=(st['giver_index']+1)%len(st['seats']);giver=st['seats'][st['giver_index']]
    options=[x for x in (choices or BANK[category]) if (category,x[0]) not in st['used']]
    if not options:st['used']={k for k in st['used'] if k[0]!=category};options=BANK[category]
    target=rng.choice(options);st['used'].add((category,target[0]));guessers=[p for p in st['seats'] if p!=giver]
    st.update(giver=giver,target=target,category=category,clues=[],lives={p:3 for p in guessers},guessers=guessers,guess_index=0,stage='clue',turn=giver)

def give_clue(st,pid,text):
    if st['stage']!='clue' or st['giver']!=pid:raise ValueError('No te toca dar pista')
    text=' '.join(str(text).split())[:300]
    if not text:raise ValueError('Falta una pista')
    if clean(st['target'][0]) in clean(text).split():raise ValueError('No digas la palabra secreta')
    st['clues'].append(text);st['stage']='guess';st['turn']=st['guessers'][st['guess_index']];st['seq']+=1

def end_round(st):
    if max(st['scores'].values())>=5 or st['round']>=12:
        top=max(st['scores'].values());st['winner']=[p for p in st['seats'] if st['scores'][p]==top];st['stage']='done'
    else:
        st['stage']='category';st['turn']=st['seats'][(st['giver_index']+1)%len(st['seats'])] if st['mode']=='sala' else st['seats'][0]

def guess(st,pid,text):
    if st['stage']!='guess' or pid!=st['turn']:raise ValueError('No es tu turno')
    st['seq']+=1
    if clean(text)==clean(st['target'][0]):
        if st['mode']!='describe':st['scores'][pid]+=1
        if st['giver'] in st['scores']:st['scores'][st['giver']]+=1
        end_round(st);return True
    st['lives'][pid]-=1
    active=[p for p in st['guessers'] if st['lives'][p]>0]
    if not active:end_round(st);return False
    for offset in range(1,len(st['guessers'])+1):
        idx=(st['guess_index']+offset)%len(st['guessers'])
        if st['lives'][st['guessers'][idx]]>0:st['guess_index']=idx;break
    st['stage']='clue';st['turn']=st['giver'];return False
