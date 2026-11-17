"""Isolated test entry point. No Telegram, keys, database or production connection."""
import asyncio,io,sys,types
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import edge_tts
import rehearsal_words
async def synthesize(text,voice=None):
    allowed=('es-AR-ElenaNeural','es-AR-TomasNeural','es-MX-DaliaNeural','es-MX-JorgeNeural','es-CL-CatalinaNeural','es-CL-LorenzoNeural')
    voice=voice if voice in allowed else allowed[0]
    chunks=[]
    async for item in edge_tts.Communicate(text,voice).stream():
        if item['type']=='audio':chunks.append(item['data'])
    if not chunks:raise RuntimeError('No voice audio')
    return b''.join(chunks)
rehearsal_words.synthesize=synthesize
sys.modules['app']=rehearsal_words
import webapp
import mystery_race,hangman_campaign
mystery_race.install(webapp)
hangman_campaign.install(webapp)
# Keep live descriptions aligned with the rehearsal rules.
for _game,_description in {
 'ahorcado':'Ensayo largo de Ahorcado: cien palabras distintas por persona, sin repetir y sin pistas de significado. Cada letra acertada se anuncia con sus casilleros y grupos formados. Podés recorrer los casilleros con tu lector o pedir Escuchar mi palabra formada. Cada desafío termina al acertar o agotar intentos; el marcador cuenta solo aciertos. La palabra y sus intentos se conservan al pasar el turno. El recorrido termina sin reiniciarse solo. Son cinco tramos por longitud, no cien dificultades medidas. Solo o carrera de progreso individual, sin puntaje de equipo en este ensayo.',
 'misterio':'Misterio: diez, veinticinco o cincuenta casos originales de lógica y observación, en cinco apartados para revisar con Rocky. Carrera individual: el mismo orden sorteado para todos, cada persona avanza al acertar y gana quien complete la meta elegida primero. Lecturas, respuestas y pistas privadas; solo nombres y cantidad resuelta se comparten. Una frase no revisada no se penaliza ni se acepta automáticamente. Todos disponen de ciento cincuenta segundos por intento; la dificultad no está medida. Sin rival máquina ni equipos en esta carrera. Cada caso empieza con el botón Girar mi ruleta, su apartado se muestra y se anuncia sin adelantar el caso siguiente. El reloj personal espera el giro y la lectura y puede iniciarse con un botón.'
}.items():
 webapp.PAGE=webapp.PAGE.replace(webapp.GAME_DESCRIPTIONS[_game],_description)
 webapp.GAME_DESCRIPTIONS[_game]=_description
app=FastAPI(title='Ensayo de mejoras de Corazón')
app.include_router(webapp.router)
@app.get('/')
async def root():return RedirectResponse('/amor-con-aroma-a-cafe')
@app.get('/health')
async def health():return {'ok':True,'trial':True,'production':False}
# Only these modes are exposed by the rehearsal entry point. Source game logic is unchanged.
webapp.PAGE=webapp.PAGE.replace('</body>', '''<script>
(()=>{
 const chosen=new Set(['ahorcado','bomba','misterio']);
 for(const prefix of ['modo','juego'])for(const b of document.querySelectorAll('[id^="btn-'+prefix+'-"]')){
  const key=b.id.slice(('btn-'+prefix+'-').length);
  if(!chosen.has(key)){b.disabled=true;const card=b.closest('.cm-card');if(card)card.hidden=true;}
 }
 const note=document.getElementById('corazon-trial-note');
 note.querySelector('p').textContent='Borrador local para revisión, no aprobado ni publicado. Ahorcado: cien palabras únicas por persona, cien desafíos, aciertos por separado. Misterio: carrera individual de 10, 25 o 50 casos de lógica y observación en cinco apartados; teorías y pistas privadas, solo marcador compartido. Equipos y rival máquina no están incluidos en esta carrera. Las partidas se pierden si se reinicia el servidor. Bomba conserva sus tiempos.';
 document.querySelector('main').prepend(note);
 const actions=document.createElement('div');
 for(const [key,label] of [['ahorcado','Probar El ahorcado'],['bomba','Probar La bomba'],['misterio','Probar Resolver el misterio']]){
  const b=document.createElement('button');b.textContent=label;b.onclick=()=>{pendingMode='solo';unlockAudio();document.getElementById('btn-modo-'+key).click();};actions.appendChild(b);
 }
 note.appendChild(actions);
 const privacy=document.createElement('p');privacy.textContent='La privacidad es entre dispositivos: si están en el mismo lugar, usen auriculares. El chat general comparte lo que mandes allí. Los casos no se envían al chat. Banco de lógica inicial, dificultad no medida y formas de respuesta por revisar.';note.appendChild(privacy);
 const label=document.createElement('label');label.textContent='Cómo querés que te despidamos: ';
 const select=document.createElement('select');select.setAttribute('aria-label','Trato en las despedidas');
 for(const [value,text] of [['neutral','Con mi nombre, sin género'],['femenino','Amiga'],['masculino','Amigo']]){const option=document.createElement('option');option.value=value;option.textContent=text;select.appendChild(option);}
 select.value=localStorage.getItem('cafe_trato')||'neutral';select.onchange=()=>localStorage.setItem('cafe_trato',select.value);label.appendChild(select);note.appendChild(label);

})();
</script></body>''',1)

# Colina stays a separate application and room bank, rehearsal only.
from colina.app import app as colina_app
app.mount("/colina", colina_app)

# New Bomba trial has its own rooms and clock; legacy Bomba is unchanged.
from bomba_nueva.app import app as bomba_nueva_app
app.mount("/bomba-nueva", bomba_nueva_app)
