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
 document.querySelector('main').prepend(note);
 const actions=document.createElement('div');
 for(const [key,label] of [['ahorcado','Probar El ahorcado'],['bomba','Probar La bomba'],['misterio','Probar Resolver el misterio']]){
  const b=document.createElement('button');b.textContent=label;b.onclick=()=>{pendingMode='solo';unlockAudio();document.getElementById('btn-modo-'+key).click();};actions.appendChild(b);
 }
 note.appendChild(actions);
 const label=document.createElement('label');label.textContent='Cómo querés que te despidamos: ';
 const select=document.createElement('select');select.setAttribute('aria-label','Trato en las despedidas');
 for(const [value,text] of [['neutral','Con mi nombre, sin género'],['femenino','Amiga'],['masculino','Amigo']]){const option=document.createElement('option');option.value=value;option.textContent=text;select.appendChild(option);}
 select.value=localStorage.getItem('cafe_trato')||'neutral';select.onchange=()=>localStorage.setItem('cafe_trato',select.value);label.appendChild(select);note.appendChild(label);

})();
</script></body>''',1)
