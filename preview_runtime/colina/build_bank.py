"""Original prompts. Arithmetic/text answers computed; general facts in SOURCES.md."""
import json,unicodedata
items=[]
def add(cat,level,q,answer,wrong,explanation,source,proof=None):
 opts=[str(answer),*(str(x)for x in wrong)]
 assert len(opts)==3 and len(set(opts))==3,(q,opts)
 items.append(dict(id=f'{cat}-{level}-{sum(x["category_key"]==cat and x["level"]==level for x in items)+1}',category_key=cat,category={'palabras':'Palabras y lenguaje','logica':'Lógica y números','mundo':'Mundo y cultura'}[cat],level=level,question=q,options=opts,correct=0,explanation=explanation,source=source,proof=proof))
def norm(w):return ''.join(c for c in unicodedata.normalize('NFD',w.lower())if unicodedata.category(c)!='Mn')
words=['casa','pelota','camino','mariposa','ventana','caracol','biblioteca','murciélago','paraguas','calendario']
for n,w in enumerate(words):
 a=len(w);add('palabras',1,f'¿Cuántas letras tiene la palabra {w}?',a,[a+1,a+2],f'{w} tiene {a} letras.','Cálculo sobre el texto de la pregunta',dict(kind='length',word=w))
for w in ['almohada','enciclopedia','electricidad','aeropuerto','extraordinario','heladería','ferrocarril','panadería','imaginación','universidad']:
 a=sum(c in 'aeiou' for c in norm(w));add('palabras',2,f'Contando también las vocales con tilde, ¿cuántas vocales tiene {w}?',a,[a+1,a+2],f'Las vocales de {w} son: '+', '.join(c for c in w if norm(c)in'aeiou')+f'. En total, {a}.','Conteo de vocales con normalización de tildes',dict(kind='vowels',word=w))
for sentence in ['La casa de la esquina tiene una ventana','El camino largo llega hasta la plaza','Una pequeña mariposa vuela sobre la mesa','Las personas escuchan todas las opciones con calma','La biblioteca guarda libros para cada visitante','El caracol camina sobre una hoja verde','Hoy caminamos lentamente por el parque cercano','La ventana abierta deja pasar aire fresco','Una persona prepara pan para la merienda','El calendario nuevo cuelga sobre la pared']:
 a=sum(len(w)>=5 for w in sentence.split());add('palabras',3,f'En esta frase, ¿cuántas palabras tienen cinco letras o más? Frase: {sentence}.',a,[a+1,a+2],f'Las palabras de cinco letras o más son: '+', '.join(w for w in sentence.split()if len(w)>=5)+f'. Son {a}.','Conteo explícito de letras y palabras',dict(kind='long_words',sentence=sentence))
for a,b in [(7,8),(14,9),(23,18),(32,19),(45,28)]:
 r=a+b;add('logica',1,f'¿Cuánto es {a} más {b}?',r,[r+2,r-2],f'{a} más {b} es {r}.','Operación entera verificada por Python',dict(kind='sum',a=a,b=b))
for a,b in [(18,7),(35,16),(42,18),(57,29),(64,37)]:
 r=a-b;add('logica',1,f'Tenés {a} fichas y entregás {b}. ¿Cuántas te quedan?',r,[r+2,r-2],f'{a} menos {b} es {r}.','Operación entera verificada por Python',dict(kind='subtract',a=a,b=b))
for a,b in [(4,6),(7,8),(9,6),(8,11),(12,7)]:
 r=a*b;add('logica',2,f'Hay {a} bolsas con {b} fichas en cada una. ¿Cuántas fichas hay en total?',r,[r+a,r-a],f'{a} por {b} es {r}.','Operación entera verificada por Python',dict(kind='multiply',a=a,b=b))
for a,step in [(3,4),(7,5),(12,6),(21,7),(33,8)]:
 seq=[a+i*step for i in range(4)];r=a+4*step;add('logica',2,'La regla es sumar siempre la misma cantidad. ¿Qué sigue después de '+', '.join(map(str,seq))+'?',r,[r+step,r-1],f'En cada paso se suman {step}. El siguiente es {r}.','Sucesión aritmética con regla explícita',dict(kind='sequence',a=a,step=step))
for a,b,c in [(6,8,11),(7,9,14),(8,12,17),(9,11,23),(12,13,29)]:
 r=a*b-c;add('logica',3,f'Tenés {a} cajas de {b} fichas. Regalás {c} fichas en total. ¿Cuántas conservás?',r,[r+2,r-2],f'Primero, {a} por {b} da {a*b}. Restando {c}, quedan {r}.','Dos operaciones enteras verificadas por Python',dict(kind='multi',a=a,b=b,c=c))
for a,b in [(5,8),(7,12),(9,14),(11,16),(13,18)]:
 total=a*b;r=total//2;add('logica',3,f'Hay {a} bolsas con {b} fichas cada una. Se reparte la mitad de todas las fichas. ¿Cuántas se reparten?',r,[r+a,r-a],f'Hay {total} fichas en total; su mitad es {r}.','Producto y división exacta verificados por Python',dict(kind='half',a=a,b=b))
P='https://science.nasa.gov/solar-system/planets/';M='https://science.nasa.gov/moon/facts/';S='https://science.nasa.gov/solar-system/solar-system-facts/';G='https://kids.britannica.com/students/article/geography/274524';O='https://kids.britannica.com/kids/article/ocean/346185';U='https://kids.britannica.com/kids/article/music/399978';R='https://kids.britannica.com/students/article/orchestra/276204';T='https://kids.britannica.com/scholars/article/tempo/636095'
world=[
(1,'¿Cuál es nuestro planeta?','La Tierra',['Marte','Saturno'],'Nuestro planeta es la Tierra.',P),
(1,'¿Qué cuerpo es el satélite natural de la Tierra?','La Luna',['El Sol','Júpiter'],'La Luna es el satélite natural de la Tierra.',M),
(1,'¿Cuántos planetas hay en el sistema solar según la clasificación actual?','Ocho',['Seis','Diez'],'La clasificación actual reconoce ocho planetas en el sistema solar.',P),
(1,'¿Qué planeta es el más cercano al Sol?','Mercurio',['Neptuno','Marte'],'Mercurio ocupa la órbita planetaria más cercana al Sol.',P),
(1,'¿Qué planeta es el mayor del sistema solar?','Júpiter',['Mercurio','La Tierra'],'Júpiter es el planeta de mayor tamaño del sistema solar.',P),
(1,'¿Cuál de estas masas de agua es un océano?','El Pacífico',['El río Paraná','El lago Titicaca'],'El Pacífico es uno de los océanos terrestres.',O),
(1,'¿Cómo es principalmente el agua de los océanos?','Salada',['Dulce','Sin sales'],'Los océanos son grandes masas de agua salada.',O),
(1,'En música, ¿qué marca el tempo?','La velocidad del pulso',['El color de un instrumento','La altura de una persona'],'El tempo indica la velocidad del pulso musical.',U),
(1,'¿Cuál es un instrumento de cuerda de una orquesta?','El violín',['La trompeta','Los platillos'],'El violín pertenece a la familia de las cuerdas.',R),
(1,'¿Cuál de estos instrumentos es de percusión?','Los platillos',['El violín','La flauta'],'Los platillos pertenecen a la percusión.',R),
(2,'¿Qué planeta ocupa el tercer lugar contando desde el Sol?','La Tierra',['Venus','Marte'],'Desde el Sol: Mercurio, Venus y Tierra.',P),
(2,'¿Cuál es el planeta más alejado del Sol entre los ocho planetas?','Neptuno',['Urano','Saturno'],'Neptuno ocupa el octavo lugar desde el Sol.',P),
(2,'¿Cuál es el planeta más pequeño del sistema solar?','Mercurio',['Marte','Venus'],'Mercurio es el menor de los ocho planetas.',P),
(2,'¿En qué galaxia está el sistema solar?','La Vía Láctea',['Andrómeda','La Nube Mayor de Magallanes'],'El sistema solar se encuentra en la Vía Láctea.',S),
(2,'¿Cerca del centro de qué continente está el Polo Sur?','La Antártida',['África','Asia'],'El Polo Sur está en la Antártida.',G),
(2,'¿Qué océano rodea el Polo Norte?','El Ártico',['El Índico','El Pacífico'],'El Polo Norte se encuentra en el océano Ártico.','https://www.pmel.noaa.gov/arctic-zone/faq.html'),
(2,'¿Qué ocupa más superficie de la Tierra?','Los océanos',['Los continentes','Océanos y continentes por igual'],'Los océanos cubren aproximadamente el 71 por ciento de la superficie terrestre.',O),
(2,'¿Qué componente musical organiza los sonidos en el tiempo?','El ritmo',['El material del escenario','El color de la partitura'],'El ritmo organiza la duración y los pulsos de los sonidos.',U),
(2,'En una orquesta, ¿a qué familia pertenece la trompeta?','Viento metal',['Cuerda frotada','Percusión'],'La trompeta se incluye entre los instrumentos de viento metal.',R),
(2,'¿Qué indicación de tempo se asocia con una ejecución rápida?','Allegro',['Lento','Largo'],'Allegro es una indicación de tempo rápido.',T),
(3,'¿Qué par está formado por gigantes de hielo?','Urano y Neptuno',['Júpiter y Saturno','La Tierra y Marte'],'Urano y Neptuno se clasifican como gigantes de hielo.',P),
(3,'¿Qué par está formado por gigantes gaseosos?','Júpiter y Saturno',['Urano y Neptuno','Mercurio y Venus'],'Júpiter y Saturno se clasifican como gigantes gaseosos.',P),
(3,'¿Qué dos planetas del sistema solar no tienen lunas?','Mercurio y Venus',['La Tierra y Marte','Júpiter y Saturno'],'Mercurio y Venus son los dos planetas sin lunas.',S),
(3,'¿Cuál de estos grupos contiene solo planetas rocosos interiores?','Mercurio, Venus y Marte',['Júpiter, Saturno y Neptuno','Urano, Neptuno y Saturno'],'Mercurio, Venus, Tierra y Marte forman el grupo de los planetas rocosos interiores.',P),
(3,'¿Qué planeta queda entre las órbitas de Saturno y Neptuno?','Urano',['Júpiter','Marte'],'El orden es Saturno, Urano y Neptuno.',P),
(3,'¿Por qué desde la Tierra vemos siempre casi la misma cara de la Luna?','Gira sobre sí misma al mismo ritmo que completa su órbita',['La Luna no gira sobre sí misma','La Luna produce luz propia'],'La rotación y la órbita lunar están sincronizadas.',M),
(3,'¿De dónde viene la luz que permite ver la Luna?','Del Sol, que la ilumina',['De fuego en la superficie lunar','De luces eléctricas en la Luna'],'Las fases dependen de qué parte de la Luna está iluminada por el Sol.',M),
(3,'¿Qué explica que en algunos mapas se hable de Eurasia?','Europa y Asia forman una masa terrestre continua',['Europa y África son una isla','Asia y Oceanía tienen un solo gobierno'],'Europa y Asia están unidas y pueden agruparse como Eurasia.','https://kids.britannica.com/students/article/continent/273790'),
(3,'En una orquesta sinfónica, ¿qué suele ocurrir con una misma parte de cuerdas?','La interpretan varios instrumentistas',['Siempre la toca una sola persona','No se usan instrumentos de cuerda'],'En la orquesta, varios músicos suelen interpretar cada parte de cuerdas.',R),
(3,'Además de palabras como allegro, ¿cómo puede indicarse el tempo?','Con una indicación de metrónomo',['Con la cantidad de sillas del público','Con el tamaño de una puerta'],'El tempo puede indicarse con palabras o con una referencia metronómica.',T),
]
for lv,q,a,wrong,e,url in world:add('mundo',lv,q,a,wrong,e,url)
assert len(items)==90
# Eight main and two rescue questions per category and level, no duplicated IDs.
for cat in ['palabras','logica','mundo']:
 for lv in [1,2,3]:
  group=[x for x in items if x['category_key']==cat and x['level']==lv]
  assert len(group)==10
  for i,q in enumerate(group):q['pool']='rescue' if i in (4,9)else 'main'
json.dump(items,open('questions.json','w'),ensure_ascii=False,indent=2)
print('90 original questions; 72 main, 18 rescue; 30 per category')
