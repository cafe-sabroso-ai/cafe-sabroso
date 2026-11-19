"""In-memory cooperative beta API, single-instance hosting."""
import asyncio,secrets,time
from pathlib import Path
from fastapi import APIRouter,HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field
import coop_engine as rules
from characters import CHARACTERS,own_audio,action_line
import webapp
router=APIRouter();rooms={};TIMEOUT=18;TTL=7200
class Create(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    character:str='tomas'
class Join(Create):code:str
class Seat(BaseModel):
    code:str
    token:str
class Command(Seat):
    action:str
    revision:int
    target:str=''
class Voice(Seat):
    event:int=-1
class Preview(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    character:str

def clean_rooms():
    for code,r in list(rooms.items()):
        if time.monotonic()-r['time']>TTL:rooms.pop(code,None)
    if len(rooms)>=8:raise HTTPException(429,'El servidor alcanzó el límite de salas. Volvé a intentar después.')

def event(r,text,actor=None,action=None):
    r['seq']+=1
    r['events'].append({'id':r['seq'],'text':text,'actor':actor,'action':action,'round':r['state']['round']})
    # Bounded log. Client receives an explicit gap notice if older history was discarded.
    r['events']=r['events'][-160:]

def credentials(body):
    r=rooms.get(body.code.upper().strip())
    if not r:raise HTTPException(404,'La sala no existe o venció. No se guarda después de reiniciar el servidor.')
    if time.monotonic()-r['time']>TTL:
        rooms.pop(body.code.upper().strip(),None)
        raise HTTPException(404,'La sala venció después de dos horas sin uso. No se recuperó otra partida.')
    pid=r['tokens'].get(body.token)
    if not pid:raise HTTPException(403,'Tu acceso no corresponde a esa sala.')
    p=rules.find(r['state'],pid)
    if p['removed']:raise HTTPException(403,'Tu lugar fue retirado de esta prueba. No controlás otro personaje.')
    return r,pid

def sweep(r,pid):
    now=time.monotonic();st=r['state'];r['time']=now;r['seen'][pid]=now
    changed=False
    for p in st['players']:
        if p['removed']:continue
        connected=now-r['seen'].get(p['id'],0)<TIMEOUT
        if p['connected']!=connected:
            p['connected']=connected;changed=True
            if connected:event(r,p['name']+' volvió. Conserva su personaje, posición, vidas y turno. La pausa no se levanta sola.')
            elif st['phase']=='play':st['paused']=True;st['pause_reason']='Falta '+p['name'];event(r,p['name']+' se desconectó. Pausa del equipo. No hay relevo automático por un bot.')
    if changed:r['revision']+=1

def view(r,pid):
    return {'code':r['code'],'state':r['state'],'revision':r['revision'],'me':pid,'host':r['host'],'events':r['events'],'summary':rules.orientation(r['state'],pid),'suggestions':rules.SUGGESTIONS,'characters':list(CHARACTERS.values()),'oldest_event':r['events'][0]['id'] if r['events'] else 0}

def add_player(r,name,character):
    try:name=rules.nickname(name,[p['name'] for p in r['state']['players']]);pid='p'+str(len(r['state']['players'])+1);p=rules.player(pid,name,character)
    except ValueError as e:raise HTTPException(400,str(e))
    token=secrets.token_urlsafe(28);r['tokens'][token]=pid;r['state']['players'].append(p);r['seen'][pid]=time.monotonic();r['revision']+=1
    event(r,name+' se suma a la sala. Cuerpo y voz: '+CHARACTERS[character]['name']+'.',pid,'intro')
    return pid,token

@router.get('/zombi-casa-coop',response_class=HTMLResponse)
async def page():return Path(__file__).with_name('coop-assets').joinpath('index.html').read_text()
@router.get('/zombi-casa-coop/options')
async def options():return {'characters':list(CHARACTERS.values()),'suggestions':rules.SUGGESTIONS}
@router.post('/zombi-casa-coop/create')
async def create(body:Create):
    clean_rooms();code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
    while code in rooms:code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
    r={'code':code,'state':rules.new_game(),'tokens':{},'seen':{},'events':[],'seq':0,'revision':0,'host':'p1','time':time.monotonic(),'lock':asyncio.Lock()}
    pid,token=add_player(r,body.name,body.character);rooms[code]=r;return view(r,pid)|{'token':token}
@router.post('/zombi-casa-coop/join')
async def join(body:Join):
    r=rooms.get(body.code.upper().strip())
    if not r:raise HTTPException(404,'Código de sala no encontrado.')
    async with r['lock']:
        if r['state']['phase']!='lobby':raise HTTPException(409,'La partida ya empezó. No hay ingreso a mitad de partida.')
        if len(r['state']['players'])>=4:raise HTTPException(409,'La sala tiene cuatro lugares. No se cambia a nadie por otro jugador.')
        pid,token=add_player(r,body.name,body.character);r['time']=time.monotonic();return view(r,pid)|{'token':token}
@router.post('/zombi-casa-coop/view')
async def poll(body:Seat):
    r,pid=credentials(body)
    async with r['lock']:sweep(r,pid);return view(r,pid)
@router.post('/zombi-casa-coop/command')
async def command(body:Command):
    r,pid=credentials(body)
    async with r['lock']:
        sweep(r,pid);st=r['state']
        if body.revision!=r['revision']:return view(r,pid)|{'reconciled':True,'notice':'El estado cambió. Revisá el turno; tu acción no se aplicó.'}
        try:
            if body.action=='start':
                if pid!=r['host']:raise ValueError('Solo quien creó la sala puede empezar.')
                text=rules.start(st);event(r,text)
            elif body.action=='pause':
                if st['phase']!='play':raise ValueError('La casa todavía no está en juego.')
                st['paused']=True;st['pause_reason']='Pausa pedida por '+rules.find(st,pid)['name'];event(r,st['pause_reason']+'. No se gasta turno.')
            elif body.action=='resume':
                if pid!=r['host']:raise ValueError('Quien creó la sala puede seguir cuando estén todos conectados.')
                if st['phase']!='play':raise ValueError('La partida no está en juego.')
                if any(not p['connected'] for p in rules.active(st)):raise ValueError('Falta alguien. Esperá su regreso o confirmá retirar su lugar.')
                st['paused']=False;st['pause_reason']=''
                notes=[]
                if st.pop('round_pending',False):rules.next_turn(st,notes)
                event(r,'El equipo sigue. '+' '.join(notes)+' '+rules.orientation(st))
            elif body.action=='remove':
                if pid!=r['host'] or body.target==r['host']:raise ValueError('Solo quien creó la sala puede retirar otro lugar desconectado.')
                p=rules.find(st,body.target)
                if p['connected'] or p['removed']:raise ValueError('Solo se retira un lugar desconectado, después de confirmar.')
                p['removed']=True;event(r,p['name']+' fue retirado de esta prueba. No lo reemplaza un bot.')
                if st['phase']=='play' and st['turn']==p['id']:
                    remaining=[q for q in rules.active(st) if q['id'] not in st['acted']]
                    st['turn']=remaining[0]['id'] if remaining else None
                    st['round_pending']=not bool(remaining)
                st['paused']=st['phase']=='play';st['pause_reason']='Revisá el equipo y elegí seguir' if st['paused'] else ''
            else:
                new,text,accepted=rules.act(st,pid,body.action);r['state']=new
                current=rules.find(new,new['turn'])['name'] if new['turn'] else 'nadie'
                text+=' Ronda '+str(new['round'])+'. '+('Casa despejada. Ganó el equipo.' if new['cleared'] else 'Terminó la prueba, nadie tiene vidas.' if new['finished'] else 'Turno de '+current+'.')
                # Always announce the predicted targets without repeating the full map and roster.
                for enemy in new['enemies']:
                    if enemy['hp']<=0:continue
                    target,steps,blocked=rules.target(new,enemy)
                    if target:text+=' '+enemy['name']+' en '+rules.solo.ROOMS[enemy['room']]['name']+', resistencia '+str(enemy['hp'])+', objetivo previsto '+target['name']+('. Debe superar la puerta.' if blocked else '.')
                event(r,text,pid,body.action if accepted else None)
            r['revision']+=1
        except (ValueError,StopIteration) as e:raise HTTPException(400,str(e) or 'Lugar inválido.')
        return view(r,pid)

def url(data):return '/amor-con-aroma-a-cafe/audio/'+webapp.cache_audio(data)+'.mp3' if data else None
async def build_voice(r,pid,e):
    text=e['text'] if e else rules.orientation(r['state'],pid)
    line='';character=None
    if e and e['actor'] and e['action']:
        p=rules.find(r['state'],e['actor']);character=p['character'];name=p['name']
        if e['action']=='intro':line='Soy '+name+'. Equipo, vamos con cuidado.'
        else:
            kind='attack' if e['action'].startswith('attack') else e['action']
            line=action_line(character,kind)
    own=None;narration=None
    try:
        if line:own=url(await own_audio(character,line))
        narration=url(await webapp.bounded_voice_mp3(text,'es-AR-ElenaNeural'))
    except Exception:pass
    return {'text':text,'character_text':line,'character_audio':own,'audio':narration,'audio_error':not bool(narration),'character_audio_error':bool(line and not own)}
@router.post('/zombi-casa-coop/voice')
async def voice(body:Voice):
    r,pid=credentials(body)
    e=next((e for e in r['events'] if e['id']==body.event),None)
    if not e:return await build_voice(r,pid,None)
    cache=r.setdefault('audio_tasks',{})
    key=e['id']
    if key not in cache:
        cache[key]=asyncio.create_task(build_voice(r,pid,e))
        for old in list(cache):
            if len(cache)<=16:break
            if old!=key and cache[old].done():cache.pop(old,None)
    return await asyncio.shield(cache[key])
@router.post('/zombi-casa-coop/preview')
async def preview(body:Preview):
    try:name=rules.nickname(body.name)
    except ValueError as e:raise HTTPException(400,str(e))
    if body.character not in CHARACTERS:raise HTTPException(400,'Cuerpo inválido.')
    text='Soy '+name+'. Equipo, vamos con cuidado.'
    return {'text':text,'audio':url(await own_audio(body.character,text))}
