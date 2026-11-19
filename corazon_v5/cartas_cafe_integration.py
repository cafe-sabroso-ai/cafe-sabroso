"""Local room server. Memory only, explicit bot turns, private hands."""
import asyncio,secrets,string,time
from pathlib import Path
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import cartas_cafe_engine as E
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
rooms={};ROOT=Path(__file__).parent;PREFIX='/cartas-del-cafe'

def trim():
 for code,r in list(rooms.items()):
  if time.monotonic()-r['updated']>86400 and not any(r['ws'].values()):rooms.pop(code,None)

def meta(r):return dict(game=r['game'],code=r['code'],capacity=r['capacity'],host=r['host'],players=[dict(id=p['id'],name=p['name'],bot=p['bot'],connected=p['bot']or p['id']in r['ws'])for p in r['players']])
def packet(r,p):return dict(event='state',**meta(r),you=p,revision=r['revision'],state=E.view(r['state'],p)if r['state']else None)
async def broadcast(r):
 for p,ws in list(r['ws'].items()):
  try:await ws.send_json(packet(r,p))
  except Exception:
   if r['ws'].get(p)is ws:r['ws'].pop(p,None)

def authorized_origin(ws):
 origin=ws.headers.get('origin');host=ws.headers.get('host')
 return origin in ('http://'+host,'https://'+host)

async def body(request):
 if request.headers.get('origin') and not authorized_origin(request):raise HTTPException(403,'Origen no permitido.')
 try:
  raw=await request.body()
  if len(raw)>4096:raise ValueError()
  import json
  d=json.loads(raw)
  if not isinstance(d,dict):raise ValueError()
  return d
 except Exception:raise HTTPException(400,'Solicitud inválida.')

@app.post(PREFIX+'/api/rooms')
async def create(request:Request):
 trim()
 if len(rooms)>=200:raise HTTPException(503,'Hay demasiadas mesas. Probá más tarde.')
 d=await body(request);game=d.get('game');cap=d.get('capacity')
 if not isinstance(game,str)or game not in E.TITLES or type(cap)is not int or cap not in ((2,4)if game=='brisca'else (2,)if game=='guerra'else (2,3,4,5)):raise HTTPException(400,'Configuración inválida.')
 name=str(d.get('name','')).strip()[:24]
 if not name:raise HTTPException(400,'Escribí un nombre o apodo.')
 code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')for _ in range(7))
 while code in rooms:code=''.join(secrets.choice(string.ascii_uppercase)for _ in range(7))
 token=secrets.token_urlsafe(32);r=dict(code=code,game=game,capacity=cap,host='p1',players=[dict(id='p1',name=name,bot=False)],tokens={token:'p1'},ws={},state=None,revision=0,lock=asyncio.Lock(),updated=time.monotonic());rooms[code]=r
 return dict(code=code,token=token,you='p1')

@app.post(PREFIX+'/api/rooms/{code}/join')
async def join(code:str,request:Request):
 r=rooms.get(code.upper())
 if not r:raise HTTPException(404,'La mesa ya no existe.')
 d=await body(request);name=str(d.get('name','')).strip()[:24]
 async with r['lock']:
  if r['state']:raise HTTPException(409,'La partida ya empezó. Abrí otra mesa para jugar.')
  if len(r['players'])>=r['capacity']:raise HTTPException(409,'La mesa está completa.')
  if not name:raise HTTPException(400,'Escribí tu nombre o apodo.')
  pid='p'+str(len(r['players'])+1);token=secrets.token_urlsafe(32);r['players'].append(dict(id=pid,name=name,bot=False));r['tokens'][token]=pid;r['revision']+=1;r['updated']=time.monotonic()
 await broadcast(r)
 return dict(code=r['code'],token=token,you=pid)

@app.websocket(PREFIX+'/ws/{code}')
async def socket(ws:WebSocket,code:str):
 if not authorized_origin(ws):await ws.close(code=4003);return
 r=rooms.get(code.upper())
 if not r:await ws.close(code=4004);return
 await ws.accept();pid=None
 try:
  raw=await asyncio.wait_for(ws.receive_text(),15)
  import json
  try:d=json.loads(raw)if len(raw)<=4096 else None
  except Exception:d=None
  if not isinstance(d,dict)or not isinstance(d.get('token'),str):await ws.close(code=4003);return
  pid=r['tokens'].get(d['token'])
  if not pid:await ws.close(code=4003);return
  old=r['ws'].get(pid);r['ws'][pid]=ws
  if old and old is not ws:await old.close(code=4001)
  await broadcast(r)
  while True:
   raw=await ws.receive_text()
   if len(raw)>4096:await ws.send_json(dict(event='error',message='Jugada demasiado larga.'));continue
   import json
   try:d=json.loads(raw)
   except Exception:await ws.send_json(dict(event='error',message='Mensaje inválido.'));continue
   async with r['lock']:
    if r['ws'].get(pid)is not ws:break
    try:
     if not isinstance(d,dict):raise ValueError('Jugada inválida.')
     if d.get('revision')!=r['revision']:raise ValueError('La mesa cambió. Revisá el turno y elegí de nuevo.')
     kind=d.get('kind')
     if kind in ('start','replay'):
      if pid!=r['host']:raise ValueError('Solo quien creó la mesa puede empezar.')
      if kind=='start'and r['state']or kind=='replay'and (not r['state']or r['state']['phase']!='done'):raise ValueError('No es momento de empezar otra partida.')
      if any(not p['bot']and p['id']not in r['ws']for p in r['players']):raise ValueError('Falta reconectar una persona de la mesa.')
      while len(r['players'])<r['capacity']:
       n=len(r['players'])+1;r['players'].append(dict(id='p'+str(n),name='Bot '+str(n),bot=True))
      r['state']=E.fresh(r['game'],[p['id']for p in r['players']])
     elif kind in ('move','bot'):
      st=r['state']
      if not st:raise ValueError('Primero hay que empezar.')
      if any(not p['bot']and p['id']not in r['ws']for p in r['players']):raise ValueError('Partida en espera: falta reconectar una persona. No se pierden cartas ni turnos.')
      active=next(p for p in r['players']if p['id']==st['turn'])
      if kind=='bot':
       if pid!=r['host']or not active['bot']:raise ValueError('No corresponde un turno de bot.')
       E.act(st,st['turn'],E.bot_move(E.view(st,st['turn'])))
      else:
       if active['bot']:raise ValueError('Es el turno de un bot.')
       E.act(st,pid,d.get('action'))
     else:raise ValueError('Acción desconocida.')
     r['revision']+=1;r['updated']=time.monotonic()
    except (ValueError,KeyError,TypeError)as e:await ws.send_json(dict(event='error',message=str(e)))
   await broadcast(r)
 except (WebSocketDisconnect,asyncio.TimeoutError):pass
 finally:
  if pid and r['ws'].get(pid)is ws:r['ws'].pop(pid,None);await broadcast(r)

def install(parent):
 parent.router.routes.extend(app.router.routes)
 from fastapi.responses import FileResponse
 @parent.get(PREFIX+'/nueve-y-media')
 async def nine_table():return FileResponse(ROOT/'nueve_static/index.html')
 parent.mount(PREFIX,StaticFiles(directory=ROOT/'cartas_cafe_static',html=True),name='cartas-cafe')
