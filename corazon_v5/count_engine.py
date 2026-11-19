"""No digas 21, local turn-taking game. No hidden bots, timer, money or penalties."""
import secrets
DARES=['Inventá un saludo para un extraterrestre que llega al Café.','Decí una frase como un robot que acaba de aprender a bailar.','Poné título a una película sobre una tostada valiente.','Vendé una nube imaginaria con una frase divertida.','Inventá el nombre de un superhéroe que siempre pierde las llaves.','Contá un microcuento con café, luna y paraguas.','Presentá a un pingüino como conductor de radio.','Imitá, solo con la voz y si querés, una puerta que bosteza.','Inventá un eslogan para una heladería en Marte.','Anunciá un partido entre almohadones y peluches.','Decí una rima sencilla con la palabra canción.','Explicá para qué sirve una cuchara a un marciano.']
QUESTIONS=['¿Qué comida te gustaría inventar?','¿Qué superpoder cotidiano elegirías?','¿A qué lugar imaginario irías por un día?','¿Qué nombre le pondrías a un dragón amistoso?','¿Qué canción pondrías para abrir una fiesta?','¿Qué objeto cotidiano convertirías en personaje?','¿Qué sabor de helado falta inventar?','¿Qué animal podría ser un gran detective?','¿Qué harías si la luna te invitara a merendar?','¿Qué título tendría una película sobre una cafetera?','¿Cuál sería el mejor trabajo para un fantasma amable?','¿Qué llevarías a un picnic en otro planeta?']
RULES='No digas 21 es un juego de contar, no de cartas. De dos a cuatro lugares. Personas reales y, solo si quien crea la sala lo elige, bots identificados para completar. Comienza en uno. Por turnos elegís decir uno, dos o tres números consecutivos a partir del último. La app anuncia los números. Quien incluye el veintiuno pierde esa ronda, aunque lo incluya junto con otros números. Nunca se salta ni se repite un número. No hay reloj. Los bots eligen una cantidad válida al azar cuando quien creó la sala pulsa su botón. No se hacen pasar por personas. La persona que perdió puede girar una ruleta de reto o pregunta; puede pasar sin castigo. Si pierde un bot también gira la ruleta, con una respuesta ficticia y graciosa de la app; no transfiere su reto a ninguna persona. Cada persona puede elegir cualquier tema o todos al azar antes de girar. Los temas no se separan por género. No se graban respuestas humanas ni se juzga si cumplió. Cada ronda gira la primera persona en el orden. Sin dinero, apuestas, eliminación ni puntos negativos.'
BOT_DARES=['¡Saludos terrícolas! ¿El café viene con antenas?', 'Bip, bip. Mis pasos de baile necesitan una actualización.', 'La tostada que saltó del plato.', 'Esta nube da sombra y combina con cualquier cielo.', 'Capitán ¿Dónde Dejé las Llaves?', 'La luna abrió su paraguas y se tomó un café bajo la lluvia de estrellas.', 'Buenas noches, les habla Pingüino FM desde un hielo muy cómodo.', 'Ñiii... ¡aaah! Hasta las puertas necesitan una siesta.', 'Marte Helado: un planeta de sabor.', '¡Almohadones al ataque! Los peluches responden con un abrazo.', 'Con esta canción me alegro el corazón.', 'Es una palita para llevar sopa del plato a la boca.']
BOT_ANSWERS=['Pizza con forma de estrella.', 'Encontrar siempre la media que falta.', 'Un bosque de bibliotecas parlantes.', 'Don Fuego Suave.', 'Una canción alegre para que cada quien baile a su modo.', 'Una taza con vocación de detective.', 'Helado de galletita lunar.', 'Un gato con lupa y mucha paciencia.', 'Llevaría medialunas espaciales.', 'Café con destino a las estrellas.', 'Guía de castillos abandonados.', 'Un mantel que no flote y una merienda para compartir.']
from count_content import CATEGORIES
CATEGORIES={'general':('Imaginación y humor',list(zip(DARES,BOT_DARES)),list(zip(QUESTIONS,BOT_ANSWERS))),**CATEGORIES}
def fresh(names,bots=None):
 if not 2<=len(names)<=4:raise ValueError('Se necesitan de dos a cuatro personas.')
 return dict(names=list(names),bots=list(bots or [False]*len(names)),last=0,turn=0,starter=0,round=1,phase='play',loser=None,result=None,text='Empieza '+names[0]+'. Elegí decir uno, dos o tres números.',revision=0)
def act(old,pid,action,count=0,category="random"):
 import copy
 s=copy.deepcopy(old)
 if action=='say':
  if s['phase']!='play' or pid!=s['turn']:raise ValueError('Esperá tu turno.')
  if type(count)is not int or count not in (1,2,3)or s['last']+count>21:raise ValueError('Elegí entre uno y tres números, sin superar el veintiuno.')
  nums=list(range(s['last']+1,s['last']+count+1));s['last']=nums[-1];s['text']=s['names'][pid]+' dice '+', '.join(map(str,nums))+'.'
  if s['last']==21:s['phase']='wheel';s['loser']=pid;s['text']+=' Dijo veintiuno y perdió esta ronda. Puede girar reto o pregunta, o pasar sin castigo.'
  else:s['turn']=(pid+1)%len(s['names']);s['text']+=' Sigue '+s['names'][s['turn']]+'.'
 elif action in ('spin','skip'):
  if s['phase']!='wheel'or pid!=s['loser']:raise ValueError('La ruleta es para la persona que dijo veintiuno.')
  if action=='skip':s['result']={'kind':'Paso libre','text':'Pasaste sin castigo.'}
  else:
   if category!='random' and category not in CATEGORIES:raise ValueError('Elegí un tema de la lista o todos al azar.')
   chosen=secrets.choice(tuple(CATEGORIES))if category=='random'else category
   label,dares,questions=CATEGORIES[chosen];kind=secrets.choice(('Reto','Pregunta'));prompt,answer=secrets.choice(dares if kind=='Reto'else questions);s['result']={'kind':kind,'category':chosen,'category_label':label,'text':prompt}
   if s['bots'][pid]:s['result']['text']+=' Respuesta ficticia del bot: '+answer
  s['phase']='result';s['text']=s['result'].get('category_label','Paso libre')+'. '+s['result']['kind']+'. '+s['result']['text']+' Podés pasar; no se guarda ninguna respuesta.'
 elif action=='next':
  if pid!=0 or s['phase']not in ('wheel','result'):raise ValueError('Quien creó la sala abre la ronda siguiente al terminar esta.')
  if s['phase']=='wheel':raise ValueError('La persona que perdió debe girar o pasar primero.')
  s['starter']=(s['starter']+1)%len(s['names']);s['turn']=s['starter'];s['round']+=1;s.update(last=0,phase='play',loser=None,result=None,text='Ronda nueva. Empieza '+s['names'][s['turn']]+'.')
 else:raise ValueError('Acción no disponible.')
 s['revision']+=1;return s
