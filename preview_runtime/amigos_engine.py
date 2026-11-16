"""Buscando amigos: 300 generated, validated combinations, not 300 hand-drawn scenes."""
import random
from amigos_objects import OBJECTS, GROUPS, SOUNDS
from copy import deepcopy
CHARACTERS={
 'osito':('gruñidito amistoso','Estoy cerca, seguí buscando.','¡Abrazo de osito, me encontraste!'),
 'perrito':('guau guau','Guau, buscame, estoy cerquita.','¡Guau guau! Salto de alegría.'),
 'muñeca':('campanitas','Seguí intentando, estoy cerca.','¡Qué alegría! Bailo un poquito.'),
 'muñequito':('pasitos de juguete','Buscá con calma, por acá estoy.','¡Me encontraste! Hago una reverencia.'),
 'payasito':('bocina suave','Pista, pistita, estoy cerquita.','¡Ja, ja! Aplaudo de alegría.'),
 'gatito':('miau','Miau, seguí intentando.','¡Miau, ronroneo contento!'),
 'conejito':('saltitos','Estoy cerca, mirá otra pista.','¡Dos saltitos de alegría!'),
 'dinosaurio de juguete':('rugido de juguete','Rrr suavecito, estoy cerca.','¡Rrr! Muevo mi cola de juguete.'),
 'robot':('bip bip','Bip, buscame con otra pista.','Bip bip, ¡amigo encontrado!'),
 'monito':('uh uh alegre','Uh uh, estoy cerquita.','¡Uh uh! Aplaudo y salto.'),
 'pajarito':('pío pío','Pío, mirá otra pista.','¡Pío pío! Aleteo de alegría.'),
 'lorito':('prr, hola hola','Cerca, cerca, buscame, buscame.','¡Me encontraste, encontraste! Hola, hola.')}
for _obj in OBJECTS:
 CHARACTERS[_obj]=(SOUNDS[_obj],'Guía automático: seguí las pistas con calma.','Guía automático: bien, encontraste '+_obj+'.')

SCENES={
 'casa':('sofá','cortina','mesa','armario','cama','alfombra','estante','baúl','sillón','almohadón','biombo','caja'),
 'parque':('banco','árbol','hamaca','fuente','tobogán','arbusto','puente','quiosco','roca','cantero','cartel','pérgola'),
 'escuela':('pupitre','biblioteca','pizarrón','armario','banco','escenario','maceta','estante','mochila','caja','mesa','atril'),
 'feria':('puesto','carrito','banderín','mesa','caja','banco','mostrador','carpa','rueda','cajón','escenario','farol'),
 'jardín':('maceta','cantero','árbol','regadera','banco','arbusto','fuente','cajón','carretilla','mesa','roca','pérgola'),
 'biblioteca':('estante','mesa','sillón','atril','caja','mostrador','biombo','banco','carrito','maceta','alfombra','escalera de juguete'),
 'plaza de juegos':('tobogán','hamaca','subibaja','banco','casita','túnel','puente','árbol','cartel','caja','roca','cantero'),
 'taller de juguetes':('mesa','estante','caja','armario','banco','carrito','cajón','atril','baúl','alfombra','biombo','mostrador'),
 'campamento de juguete':('carpa','mochila','tronco','linterna','mesa','roca','cajón','canoa de juguete','hamaca','banco','cartel','puente'),
 'teatro de títeres':('telón','escenario','baúl','butaca','mesa','biombo','caja','farol','atril','estante','banco','carrito')}
COLORS=('azul','dorado','violeta','verde','coral','celeste')
SYMBOLS=('estrella','círculo','triángulo','flor')
ZONES=('izquierda','centro','derecha')

def spec_for(level,seed=0):
 if type(level) is not int or not 1<=level<=300:raise ValueError('Nivel inválido')
 rng=random.Random(f"friends:{seed}:{level}");stage=min(4,(level-1)//60);count=(4,6,8,10,12)[stage];scene=tuple(SCENES)[(level-1)%10];tuples=[(c,s,z) for c in COLORS for s in SYMBOLS for z in ZONES];rng.shuffle(tuples);spots=[dict(id=i,name=SCENES[scene][i],color=c,symbol=s,zone=z) for i,(c,s,z) in enumerate(tuples[:count])];chars=[c for c in CHARACTERS if c not in OBJECTS];rng.shuffle(chars);total=1 if level<=100 else 2 if level<=200 else 3;hidden=rng.sample(range(count),total)
 return dict(level=level,scene=scene,spots=spots,characters=chars[:total],hidden=hidden,initial_clues=3 if level<=60 else 2 if level<=180 else 1,stage=stage,total=total)

DIFFICULTIES={
 'muyfacil':dict(label='Muy fácil',sizes=(4,4,6,6,8),clues=(3,3,3,3,2),seconds=(75,70,65,60,55),urge=16),
 'facil':dict(label='Fácil',sizes=(4,6,6,8,10),clues=(3,3,2,2,2),seconds=(60,55,50,45,40),urge=12),
 'normal':dict(label='Normal',sizes=(4,6,8,10,12),clues=(3,2,2,1,1),seconds=(45,42,39,36,33),urge=8),
 'dificil':dict(label='Difícil',sizes=(6,8,10,12,12),clues=(2,2,1,1,1),seconds=(35,32,29,26,23),urge=7),
 'muydificil':dict(label='Muy difícil',sizes=(8,10,12,12,12),clues=(1,1,1,1,1),seconds=(25,23,21,19,17),urge=6),
 'mundial':dict(label='Mundial',sizes=(10,12,12,12,12),clues=(1,1,1,1,1),seconds=(18,16,14,12,10),urge=5)}

def object_profile(st):
 d=DIFFICULTIES[st['difficulty']];stage=min(4,(st['level']-1)//60)
 return dict(label=d['label'],spots=d['sizes'][stage],clues=d['clues'][stage],seconds=d['seconds'][stage],urge=d['urge'])

def new_game(seats,seed=None,mode='personajes',object_name='bastón',difficulty='normal'):
 if difficulty not in DIFFICULTIES:raise ValueError('Dificultad inválida')
 if mode not in ('personajes','objetos') or object_name not in OBJECTS:raise ValueError('Modo u objeto inválido')
 if not 1<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Participantes inválidos')
 st=dict(mode=mode,difficulty=difficulty,object_name=object_name,seats=list(seats),seed=random.randrange(1<<30) if seed is None else seed,turn=seats[0],level=1,phase='search',players={p:dict(score=0,found=0) for p in seats},lives=3,found=0,target_index=0,spec=None,shown=3,checked=[],seq=0,result='Buscando mis cosas. Elegí tu objeto. El guía automático te acompaña.' if mode=='objetos' else 'Buscando amigos. Trescientas combinaciones generadas de lugar, personaje y pistas coherentes.',last_found=None,challenge_used=False,challenge=None,bonus=None,winner=None)
 setup_level(st);return st

def setup_level(st):
 st['spec']=spec_for(st['level'],st['seed'])
 if st['mode']=='objetos':
  profile=object_profile(st);count=profile['spots'];rng=random.Random(f"objects:{st['seed']}:{st['level']}:{st['difficulty']}")
  tuples=[(c,s,z) for c in COLORS for s in SYMBOLS for z in ZONES];rng.shuffle(tuples)
  st['spec'].update(scene='casa',characters=[st['object_name']],total=1,hidden=[rng.randrange(count)],initial_clues=profile['clues'],spots=[dict(id=i,name=SCENES['casa'][i],color=c,symbol=s,zone=z) for i,(c,s,z) in enumerate(tuples[:count])])
 st.update(target_index=0,shown=st['spec']['initial_clues'],checked=[],last_found=None,challenge_used=False,challenge=None,bonus=None,phase='search')

def target(st):return st['spec']['characters'][st['target_index']]
def target_spot(st):return st['spec']['spots'][st['spec']['hidden'][st['target_index']]]
def clues(st):
 t=target_spot(st);all_clues=['Estoy junto al color '+t['color']+'.','Veo el símbolo '+t['symbol']+'.','Mi zona es '+t['zone']+'.']
 if st.get('mode')=='objetos':all_clues=['Guía automático: el objeto está junto al color '+t['color']+'.','Guía automático: buscá el símbolo '+t['symbol']+'.','Guía automático: está en la zona '+t['zone']+'.']
 return all_clues[:st['shown']]

def check(st,pid):
 if st['turn']!=pid or st['phase']!='search' or st['winner'] is not None:raise ValueError('Fuera de turno')

def rotate_turn(st):
 i=st['seats'].index(st['turn']);st['turn']=st['seats'][(i+1)%len(st['seats'])]

def hint(st,pid):
 check(st,pid)
 if st['shown']>=3:raise ValueError('Ya están las tres pistas')
 st['shown']+=1;st['seq']+=1;st['result']=('Otra pista del guía: ' if st['mode']=='objetos' else 'Otra pista de '+target(st)+': ')+clues(st)[-1]

def finish(st,reason):
 st['phase']='done';st['winner']=list(st['seats']) if st['level']==300 and st['target_index']==st['spec']['total'] else [];st['result']+=reason

def search(st,pid,spot,timeout=False):
 check(st,pid)
 if not timeout and (type(spot) is not int or not 0<=spot<len(st['spec']['spots']) or spot in st['checked']):raise ValueError('Lugar inválido o ya revisado')
 char=target(st);t=target_spot(st);correct=not timeout and spot==t['id'];st['seq']+=1
 if correct:
  st['players'][pid]['score']+=25+st['spec']['stage']*5;st['players'][pid]['found']+=1;st['found']+=1;st['last_found']=dict(character=char,spot=t['id'],seq=st['seq']);st['result']=('Guía automático: bien, encontraste '+char+'. Pasás al próximo nivel.' if st['mode']=='objetos' else CHARACTERS[char][2])+' Estaba junto a '+t['name']+'.';st['target_index']+=1
  if st['target_index']==st['spec']['total']:st['phase']='bonus';st['result']+=' Nivel completo. Girá la ruleta virtual.'
  else:st.update(shown=st['spec']['initial_clues'],checked=[])
 else:
  if not timeout:st['checked'].append(spot)
  st['lives']-=1;st['result']=(('Guía automático: intentá otra vez, ¡ese objeto juega muy bien a las escondidas!','Guía automático: está difícil, pero vos podés. ¡Probá otra vez!','Guía automático: ¡dale, detective! Otra pista y seguimos.','Guía automático: esta ronda salió escurridiza. ¡A probar de nuevo!')[st['seq']%4] if st['mode']=='objetos' else CHARACTERS[char][1])+' '+('La ventana terminó.' if timeout else 'Ese lugar no era.')+' Quedan '+str(st['lives'])+' vidas compartidas.'
  if st['lives']==0:
   if st['mode']=='objetos':finish(st,' Se terminaron las tres vidas. Guía automático: ¡buen intento! Podés empezar otra búsqueda cuando quieras.')
   elif st['challenge_used']:finish(st,' No queda un desafío de rescate en este nivel. Fin amable, podés empezar otra vez.')
   else:st['phase']='rescue';st['result']+=' Podés resolver el desafío para recuperar una vida.'
 if st['phase']=='search':rotate_turn(st)
 return dict(correct=correct,character=char)

def challenge_question(st):
 color=COLORS[(st['level']-1)%len(COLORS)];return dict(text='Contá los lugares de color '+color+'. ¿Cuántos hay?',answer=sum(s['color']==color for s in st['spec']['spots']),color=color)

def answer_challenge(st,pid,answer):
 if st['mode']=='objetos' or st['turn']!=pid or st['phase'] not in ('search','rescue') or st['winner'] is not None or st['challenge_used']:raise ValueError('Desafío no disponible')
 if type(answer) is not int or not 0<=answer<=12:raise ValueError('Respuesta inválida')
 st['challenge_used']=True;correct=answer==challenge_question(st)['answer'];st['seq']+=1
 if correct:st['lives']=min(5,st['lives']+1);st['phase']='search';st['result']='¡Desafío correcto! Regalo de una vida virtual compartida. Ahora '+str(st['lives'])+'.'
 else:
  st['result']='El conteo no coincidía. No se gastan vidas extra.'
  if st['lives']==0:finish(st,' Sin vidas. Podés volver a empezar, sin castigos reales.')
 return correct

def spin(st,pid):
 if st['turn']!=pid or st['phase']!='bonus' or st['winner'] is not None:raise ValueError('No se puede girar')
 rng=random.Random(f"bonus:{st['seed']}:{st['level']}");name,points=rng.choice((('Estrella amiga',30),('Abrazo virtual',50),('Ronda de aplausos',70)));st['bonus']=dict(name=name,points=points);st['players'][pid]['score']+=points;st['result']='Ruleta: '+name+', '+str(points)+' puntos virtuales. No es un premio real.';st['phase']='between';st['seq']+=1
 if st['level']==300:finish(st,' ¡Encontraron amigos en las trescientas combinaciones!')
 return deepcopy(st['bonus'])

def next_level(st):
 if st['phase']!='between' or st['winner'] is not None:raise ValueError('Nivel no terminado')
 st['level']+=1;setup_level(st);rotate_turn(st);st['seq']+=1;st['result']='Nivel '+str(st['level'])+', '+st['spec']['scene']+'.'

def public_state(st):
 spec=st['spec'];playing=st['phase'] in ('search','rescue');char=target(st) if playing else None
 return deepcopy({k:st[k] for k in ('mode','difficulty','object_name','turn','level','phase','players','lives','found','target_index','checked','seq','result','last_found','challenge_used','bonus','winner')})|dict(difficulty_options={k:d['label'] for k,d in DIFFICULTIES.items()},object_profile=object_profile(st),object_groups=deepcopy(GROUPS),object_count=len(OBJECTS),scene=spec['scene'],spots=deepcopy(spec['spots']),character=char,sound=CHARACTERS[char][0] if char else None,clues=clues(st) if playing else [],shown=st['shown'],total_hidden=spec['total'],total_levels=300,generated=True,challenge_text=challenge_question(st)['text'],max_lives=3 if st['mode']=='objetos' else 5)

def bot(st,pid):
 if st['turn']!=pid:raise ValueError('Fuera de turno')
 if st['phase']=='bonus':return spin(st,pid)
 if st['phase']=='rescue':return answer_challenge(st,pid,challenge_question(st)['answer'])
 check(st,pid)
 if st['shown']<3:return hint(st,pid)
 public=public_state(st);words=' '.join(public['clues']);choices=[x for x in public['spots'] if x['color'] in words and x['symbol'] in words and x['zone'] in words];return search(st,pid,choices[0]['id'])
