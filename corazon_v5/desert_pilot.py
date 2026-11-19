"""Local real-time server. One ticker per app, room locks and idempotent input sequences."""
import asyncio,secrets,time,logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import APIRouter,HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field
import desert_engine as rules
from characters import CHARACTERS
import coop_pilot
rooms={};TICK=.1;HEARTBEAT=3.0;TTL=7200
router=APIRouter()
class Create(BaseModel):
 name:str=Field(min_length=1,max_length=100)
 character:str='tomas'
 speed:str='lenta'
 audio_mode:str='cached'
 timed:bool=False
class Join(Create):code:str
class Access(BaseModel):
 code:str
 token:str
 visible:bool=True
class Command(Access):
 action:str
 sequence:int=Field(ge=1)
 target:str=''

def credentials(body):
 r=rooms.get(body.code.upper().strip())
 if not r:raise HTTPException(404,'Sala local no encontrada. No hay guardado persistente.')
 if time.monotonic()-r['used']>TTL:rooms.pop(r['code'],None);raise HTTPException(404,'Sala vencida por inactividad.')
 pid=r['tokens'].get(body.token)
 if not pid:raise HTTPException(403,'Acceso incorrecto para esta sala.')
 p=rules.find(r['state'],pid)
 if p['removed']:raise HTTPException(403,'Este lugar fue retirado. No controlás a otra persona.')
 return r,pid

def add(r,body):
 st=r['state']
 if body.audio_mode not in ('cached','text'):raise HTTPException(400,'Elegí avisos cargados o práctica de texto explícita.')
 try:
  name=rules.common.nickname(body.name,[p['name'] for p in st['players']]);pid='p'+str(len(st['players'])+1);p=rules.add_player(st,pid,name,body.character)
 except ValueError as e:raise HTTPException(400,str(e))
 p['audio_mode']=body.audio_mode;token=secrets.token_urlsafe(28);r['tokens'][token]=pid;r['seen'][pid]=time.monotonic();r['sequences'][pid]=0
 rules.emit(st,name+' se suma con cuerpo y voz '+CHARACTERS[body.character]['name']+'.'+(' Práctica de texto sin avisos naturales.' if body.audio_mode=='text' else ''),None,0)
 return pid,token

def presence(r,pid,visible):
 now=time.monotonic();r['seen'][pid]=now;r['used']=now;p=rules.find(r['state'],pid);back=not p['connected'];p['connected']=True;p['visible']=visible
 if not visible and p['lives']>0:rules.pause(r['state'],'Una ventana pasó a segundo plano. Revisen antes de seguir.')
 if back:rules.emit(r['state'],p['name']+' volvió. Conserva su lugar. Marquen Listo para seguir.',None,2)

def check_missing(r,now):
 st=r['state']
 for p in st['players']:
  if p['removed']:continue
  if now-r['seen'].get(p['id'],0)>HEARTBEAT:
   if p['connected']:
    p['connected']=False
    if p['lives']>0:rules.pause(st,'Falta conexión de '+p['name']+'. No hay reemplazo por bot.')

def view(r,pid):
 st=r['state'];r['snapshot']=r.get('snapshot',0)+1
 # No tokens, raw wall-clock timestamps or input sequence state are exposed to other seats.
 return {'snapshot':r['snapshot'],'code':r['code'],'me':pid,'host':r['host'],'state':st,'summary':rules.orientation(st,pid),'characters':list(CHARACTERS.values()),'last_sequence':r['sequences'][pid],'server_heartbeat_seconds':HEARTBEAT}

async def clock_loop():
 previous=time.monotonic()
 while True:
  await asyncio.sleep(TICK);now=time.monotonic();dt=now-previous;previous=now
  for r in list(rooms.values()):
   async with r['lock']:
    check_missing(r,now)
    if dt>.6:rules.pause(r['state'],'Levantamos pausa por demora del servidor. No se acumulan golpes atrasados.')
    else:rules.tick(r['state'],dt)
    if now-r['used']>TTL:rooms.pop(r['code'],None)

@asynccontextmanager
async def lifespan(app):
 task=asyncio.create_task(clock_loop())
 try:yield
 finally:
  task.cancel()
  try:await task
  except asyncio.CancelledError:pass

@router.get('/arena-del-desierto',response_class=HTMLResponse)
async def page():return Path(__file__).with_name('desierto-assets').joinpath('index.html').read_text()
@router.get('/arena-del-desierto/options')
async def options():
 files=Path(__file__).with_name('desierto-assets').joinpath('audio')
 return {'characters':list(CHARACTERS.values()),'suggestions':rules.common.SUGGESTIONS,'weapons':rules.WEAPONS,'speeds':list(rules.SPEEDS),'cues':{key:{'text':text,'url':'/desierto-assets/audio/'+key+'.mp3' if (files/(key+'.mp3')).exists() else None} for key,text in rules.CUES.items()}}
@router.post('/arena-del-desierto/create')
async def create(body:Create):
 if len(rooms)>=32:raise HTTPException(429,'Demasiadas pruebas locales abiertas.')
 try:st=rules.new_game(body.speed,body.timed)
 except ValueError as e:raise HTTPException(400,str(e))
 code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
 while code in rooms:code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
 r={'code':code,'state':st,'host':'p1','tokens':{},'seen':{},'sequences':{},'used':time.monotonic(),'lock':asyncio.Lock()};pid,token=add(r,body);rooms[code]=r
 return view(r,pid)|{'token':token}
@router.post('/arena-del-desierto/join')
async def join(body:Join):
 r=rooms.get(body.code.upper().strip())
 if not r:raise HTTPException(404,'Sala no encontrada.')
 async with r['lock']:
  if r['state']['phase']!='lobby':raise HTTPException(409,'No hay ingreso a mitad de supervivencia.')
  if len(r['state']['players'])>=4:raise HTTPException(409,'Máximo cuatro personas.')
  pid,token=add(r,body);return view(r,pid)|{'token':token}
@router.post('/arena-del-desierto/view')
async def poll(body:Access):
 r,pid=credentials(body)
 async with r['lock']:presence(r,pid,body.visible);return view(r,pid)
@router.post('/arena-del-desierto/command')
async def command(body:Command):
 r,pid=credentials(body)
 async with r['lock']:
  presence(r,pid,body.visible);st=r['state']
  if body.sequence<=r['sequences'][pid]:return view(r,pid)|{'reconciled':True,'notice':'Esta orden ya se revisó. No se repitió.'}
  r['sequences'][pid]=body.sequence
  try:
   if body.action=='start':
    if pid!=r['host']:raise ValueError('Solo quien creó la sala inicia.')
    rules.start(st);result={'accepted':True}
   elif body.action=='next_level':
    if pid!=r['host']:raise ValueError('Solo la persona anfitriona prepara el siguiente nivel.')
    rules.next_level(st);result={'accepted':True}
   elif body.action=='pause':rules.pause(st,'Pausa pedida por '+rules.find(st,pid)['name']+'.');result={'accepted':True}
   elif body.action=='ready':
    if st['phase']!='play' or not st['paused']:raise ValueError('La partida no está esperando una pausa.')
    if pid not in st['ready']:st['ready'].append(pid)
    needed=rules.living(st)
    if any(not p['connected'] or not p['visible'] for p in needed):result={'notice':'Todavía falta una persona activa. La pausa sigue.'}
    elif all(p['id'] in st['ready'] for p in needed):
     st['paused']=False;st['pause_reason']='';st['ready']=[];rules.emit(st,'Todos los jugadores vivos marcaron Listo. Seguimos.','resume',4);result={'accepted':True}
    else:result={'notice':'Marcaste Listo. Falta el resto del equipo vivo.'}
   elif body.action=='remove':
    if pid!=r['host'] or body.target==r['host']:raise ValueError('Solo quien creó la sala retira otro lugar desconectado.')
    p=rules.find(st,body.target)
    if p['connected'] or p['removed']:raise ValueError('Solo se retira un lugar desconectado, después de confirmar.')
    p['removed']=True;rules.pause(st,'Se retiró un lugar. El equipo vivo debe marcar Listo otra vez.');rules.emit(st,p['name']+' fue retirado. No lo reemplaza un bot.',None,2);result={'accepted':True}
    if not rules.living(st):st['phase']='lost';rules.emit(st,'No quedan personas con vidas.','win_none',5)
   else:result=rules.action(st,pid,body.action,body.target)
  except (ValueError,StopIteration) as e:raise HTTPException(400,str(e) or 'Lugar inválido.')
  return view(r,pid)|result
@router.post('/arena-del-desierto/preview')
async def preview(body:coop_pilot.Preview):return await coop_pilot.preview(body)
