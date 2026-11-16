"""Rosco compartido, definiciones originales y respuestas sin marcas."""
import unicodedata,random,re
LETTERS=list('ABCDEFGHIJKLMNÑOPQRSTUVWXYZ')
# Definitions are authored for this game. A contains clue is explicit, never inferred by the player.
BANK={
'A':[('avión','Transporte con alas que lleva pasajeros por el cielo.'),('almohada','Apoyás la cabeza sobre ella para dormir.'),('acertijo','Enigma que se propone para encontrar su solución.')],
'B':[('barco','Transporte que navega por el agua.'),('biblioteca','Lugar donde se guardan y prestan libros.'),('brújula','Instrumento con una aguja que señala el norte.')],
'C':[('casa','Edificio que usamos para vivir.'),('campana','Objeto hueco de metal que suena al golpearlo.'),('calendario','Organiza los días, semanas y meses del año.')],
'D':[('dado','Cubo con puntos que tiramos en muchos juegos.'),('desierto','Región muy seca, con poca lluvia.'),('diccionario','Libro o recurso que explica palabras en orden alfabético.')],
'E':[('estrella','Punto luminoso del cielo nocturno que tiene luz propia.'),('espejo','Superficie donde podés ver tu reflejo.'),('equilibrio','Lo mantenés para no caerte al caminar por una línea estrecha.')],
'F':[('flor','Parte de una planta que puede tener pétalos de colores.'),('faro','Torre cuya luz orienta a los barcos.'),('frontera','Límite que separa territorios o países.')],
'G':[('gato','Animal doméstico que maúlla.'),('guitarra','Instrumento de cuerdas que se toca con los dedos o una púa.'),('glaciar','Gran masa de hielo que se desplaza lentamente.')],
'H':[('helado','Postre muy frío que puede servirse en un cucurucho.'),('horno','Aparato cerrado que usamos para cocinar con calor.'),('horizonte','Línea aparente donde parecen encontrarse la tierra y el cielo.')],
'I':[('isla','Porción de tierra rodeada de agua.'),('imán','Objeto que atrae ciertos metales, como el hierro.'),('incógnito','De identidad desconocida o que se mantiene oculta.')],
'J':[('jabon','Lo usamos con agua para lavarnos las manos.'),('jardin','Espacio donde se cultivan flores y otras plantas.'),('jeroglífico','Escritura que representa palabras o ideas con figuras y signos.')],
'K':[('kilo','Nombre corto que le damos a la unidad de mil gramos.'),('koala','Animal australiano que suele comer hojas de eucalipto.'),('kayak','Embarcación estrecha que se impulsa con una pala de dos hojas.')],
'L':[('luna','Satélite natural de la Tierra.'),('linterna','Luz portátil que llevás en la mano para alumbrar.'),('laberinto','Lugar de caminos enredados donde cuesta encontrar la salida.')],
'M':[('mesa','Mueble con una superficie elevada donde podemos comer.'),('montaña','Gran elevación natural del terreno.'),('metáfora','Recurso que llama a una cosa con el nombre de otra por su semejanza.')],
'N':[('nube','Masa visible de pequeñas gotas o cristales de hielo en el cielo.'),('nido','Refugio que muchas aves construyen para sus huevos.'),('nostalgia','Tristeza o añoranza al recordar algo querido que quedó atrás.')],
'Ñ':[('ñandú','Ave sudamericana grande que corre y no vuela.'),('ñoqui','Pequeña pieza de pasta que suele hacerse con papa y harina.'),('ñato','Dicho de alguien con nariz corta o poco saliente.')],
'O':[('ojo','Órgano con el que vemos.'),('orquesta','Conjunto de músicos que tocan distintos instrumentos juntos.'),('oasis','Lugar con agua y vegetación en medio de un desierto.')],
'P':[('pan','Alimento que suele hacerse con harina, agua y levadura y se cocina al horno.'),('puente','Construcción que permite cruzar por encima de un río o de un obstáculo.'),('paradoja','Idea que parece contradictoria y hace pensar.')],
'Q':[('queso','Alimento que se elabora a partir de leche cuajada.'),('química','Ciencia que estudia la composición y transformación de la materia.'),('quiosco','Pequeño comercio donde podés comprar golosinas o diarios.')],
'R':[('río','Corriente natural de agua que fluye por un cauce.'),('reloj','Objeto que usamos para saber la hora.'),('rompecabezas','Juego de piezas que se unen para formar una imagen.')],
'S':[('sol','Estrella que ilumina la Tierra durante el día.'),('semilla','Parte de una planta que puede dar origen a otra.'),('silencio','Ausencia de sonidos perceptibles.')],
'T':[('tren','Transporte formado por vagones que circula sobre rieles.'),('telescopio','Instrumento que permite observar objetos lejanos del cielo.'),('termómetro','Instrumento que mide la temperatura.')],
'U':[('uva','Fruta que crece en racimos y se usa para hacer vino.'),('universo','Conjunto de todo lo que existe: espacio, tiempo y materia.'),('utopía','Proyecto o sociedad ideal que parece difícil de realizar.')],
'V':[('vaca','Animal de granja que muge y del que obtenemos leche.'),('ventana','Abertura en una pared que deja entrar luz y aire.'),('vocabulario','Conjunto de palabras que conoce o usa una persona.')],
'W':[('web','Empieza con W: red de páginas que consultamos con un navegador.'),('kiwi','Contiene W: fruta de piel marrón y pulpa generalmente verde.'),('sándwich','Contiene W: comida que pone un relleno entre dos rebanadas de pan.')],
'X':[('xilófono','Empieza con X: instrumento de láminas que se golpean con pequeñas mazas.'),('examen','Contiene X: prueba que evalúa lo que sabés de una materia.'),('hexágono','Contiene X: polígono de seis lados.')],
'Y':[('yate','Embarcación que se usa para pasear o practicar deporte.'),('yema','Parte amarilla del interior de un huevo.'),('yunque','Bloque metálico sobre el que se trabaja el metal a martillazos.')],
'Z':[('zapato','Calzado que cubre el pie sin llegar a ser bota.'),('zanahoria','Raíz comestible que suele ser de color naranja.'),('zumbido','Sonido continuo, como el que hace un mosquito al volar.')]
}


def clean(text):
    t=unicodedata.normalize('NFD',str(text).lower().strip());t=''.join(c for c in t if unicodedata.category(c)!='Mn')
    return re.sub(r'[^a-z0-9 ]','',t).strip()


def new_game(seats,bank=None,rng=None):
    if len(seats)<2 or len(set(seats))!=len(seats):raise ValueError('Necesitamos dos asientos distintos')
    rng=rng or random;bank=bank or BANK
    return {'seats':list(seats),'turn':seats[0],'index':0,'cards':{l:rng.choice(bank[l]) for l in LETTERS},'status':{l:'pending' for l in LETTERS},'scores':{p:0 for p in seats},'answers':{},'passes':0,'winner':None,'done':False,'seq':0,'result':''}


def current(st):return LETTERS[st['index']]


def next_pending(st):
    for offset in range(1,len(LETTERS)+1):
        i=(st['index']+offset)%len(LETTERS)
        if st['status'][LETTERS[i]]=='pending':st['index']=i;return True
    return False


def finish(st):
    st['done']=True;top=max(st['scores'].values());st['winner']=[p for p in st['seats'] if st['scores'][p]==top]


def respond(st,pid,text,passing=False):
    if st['done'] or st['turn']!=pid:raise ValueError('No es tu turno')
    letter=current(st);answer,hint=st['cards'][letter];st['seq']+=1
    if passing:
        st['passes']+=1;event='pass'
    else:
        st['passes']=0;correct=clean(text)==clean(answer);st['status'][letter]='correct' if correct else 'wrong';st['answers'][letter]=answer
        if correct:st['scores'][pid]+=1
        event='correct' if correct else 'wrong'
    # Two complete passes per pending letter by every seat end a stalled room.
    if not next_pending(st) or st['passes']>=2*len(st['seats'])*sum(v=='pending' for v in st['status'].values()):finish(st)
    elif event!='correct':st['turn']=st['seats'][(st['seats'].index(pid)+1)%len(st['seats'])]
    return event
