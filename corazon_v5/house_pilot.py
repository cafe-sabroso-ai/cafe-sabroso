"""Optional house/character beta, isolated from existing games."""
import asyncio,secrets,time,logging
from pathlib import Path
from fastapi import APIRouter,HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import house_engine as rules
from characters import CHARACTERS,own_audio,action_line
import webapp
router=APIRouter();sessions={}
class Start(BaseModel):
    character:str='tomas'
class Action(BaseModel):
    session:str
    action:str
    revision:int
ALLOWED={'read','pause','resume','restart','left','right','walk','back','run','open','close','bar','retry_audio','weapon_cuchillo','weapon_disparo'}|{'attack_z'+str(i) for i in range(1,11)}|{'attack_jefe'}
def audio_url(data):
    return '/amor-con-aroma-a-cafe/audio/'+webapp.cache_audio(data)+'.mp3' if data else None
async def payload(record):
    st=record['state'];cid=st['character'];c=CHARACTERS[cid]
    intro='Casa para explorar. Casa individual beta. Elegiste a '+c['name']+'. Cuatro áreas: Entrada, Salón, Cocina y Patio, con una pileta de agua celeste. Diez zombis en cinco parejas y, después, un jefe final. Nunca aparecen once a la vez. Los nuevos enemigos se anuncian y no atacan al aparecer. Caminás o corrés una habitación por acción. Correr anima más rápido, sin castigo ni ventaja táctica adicional. Girar, escuchar y pausa no gastan acciones. Corredor dos pasos, caminante uno. No hay reloj en tiempo real. '
    text=st.get('last') or (intro+rules.orientation(st));url=None
    try:url=audio_url(await webapp.bounded_voice_mp3(text,'es-AR-ElenaNeural'))
    except Exception as error:logging.getLogger('house-preview').warning('House narration unavailable reason=%s',type(error).__name__)
    action=st['last_action'];kind='start' if action in ('inicio','restart') else 'attack' if action.startswith('attack') else action
    # Own voice adds short action lines only after accepted actions, never fake an action on a failed move.
    line=action_line(cid,kind) if not st.get('last') or record.get('changed') else ''
    char_audio=audio_url(await own_audio(cid,line)) if line else None
    return {'state':st,'character':c,'revision':record['revision'],'text':text,'audio':url,'audio_error':not bool(url),'character_text':line,'character_audio':char_audio,'character_audio_error':bool(line and not char_audio)}
@router.get('/zombi-casa',response_class=HTMLResponse)
async def page():return Path(__file__).with_name('house-assets').joinpath('index.html').read_text()
@router.get('/zombi-personajes/roster')
async def roster():return {'characters':list(CHARACTERS.values())}
@router.get('/zombi-personajes/voice/{character}')
async def preview(character:str):
    if character not in CHARACTERS:raise HTTPException(404,'Personaje inválido')
    c=CHARACTERS[character];return {'character':c,'text':c['line'],'audio':audio_url(await own_audio(character,c['line']))}
@router.post('/zombi-casa/start')
async def start(body:Start):
    if body.character not in CHARACTERS:raise HTTPException(400,'Personaje inválido')
    for key,record in list(sessions.items()):
        if time.monotonic()-record['time']>7200:sessions.pop(key,None)
    if len(sessions)>=24:raise HTTPException(429,'El servidor alcanzó el límite de pruebas. Volvé a intentar después.')
    token=secrets.token_urlsafe(24);record={'state':rules.new_game(body.character),'revision':0,'time':time.monotonic(),'lock':asyncio.Lock(),'changed':True};sessions[token]=record
    result=await payload(record);result['session']=token;return result
@router.post('/zombi-casa/action')
async def action(body:Action):
    if body.action not in ALLOWED:raise HTTPException(400,'Acción no disponible.')
    record=sessions.get(body.session)
    if not record:raise HTTPException(404,'La partida venció. Volvé a empezar.')
    async with record['lock']:
        if body.revision!=record['revision']:
            result=await payload(record);result['reconciled']=True;return result
        if body.action!='retry_audio':
            previous=record['state'];record['state']=rules.act(previous,body.action);record['revision']+=1
            record['changed']=record['state']['step']!=previous['step'] or body.action=='restart'
        record['time']=time.monotonic();return await payload(record)
