import asyncio,json,time,secrets
from pathlib import Path
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,Request
from fastapi.responses import HTMLResponse,Response
try:
 from .engine import Room,GameError,CATEGORIES
except ImportError:
 from engine import Room,GameError,CATEGORIES

app=FastAPI(title='Números al Café')
ROOT=Path(__file__).parent
rooms={};connections={};created={};tickers={}
HEADERS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'}
@app.get('/')
async def home():return HTMLResponse((ROOT/'index.html').read_text(),headers=HEADERS)
@app.get('/health')
async def health():return {'ok':True,'local':False,'version':'1.0.0','categories':len(CATEGORIES),'exercises':2500,'levels':10}
@app.get('/{asset}')
async def asset(asset:str):
 if asset not in ('app.js','style.css'):raise HTTPException(404)
 return Response((ROOT/asset).read_bytes(),media_type='text/javascript' if asset.endswith('.js') else 'text/css',headers=HEADERS)
@app.post('/rooms')
async def create(request:Request):
 raw=await request.body()
 if len(raw)>1024:raise HTTPException(413,'Pedido demasiado grande.')
 try:payload=json.loads(raw)
 except Exception:raise HTTPException(400,'Pedido inválido.')
 if not isinstance(payload,dict) or payload.get('mode') not in ('solo','friends'):raise HTTPException(400,'Elegí modo individual o con amigos.')
 if 'start_level' in payload:raise HTTPException(400,'La dificultad sube sola, no se elige al empezar.')
 for code,ts in list(created.items()):
  if time.monotonic()-ts>21600 and not connections.get(code):
   rooms.pop(code,None);created.pop(code,None);connections.pop(code,None)
   task=tickers.pop(code,None)
   if task:task.cancel()
 if len(rooms)>=100:raise HTTPException(503,'Se alcanzó el límite de salas. Intentá más tarde.')
 code=secrets.token_hex(4).upper();rooms[code]=Room(payload['mode']);connections[code]={};created[code]=time.monotonic()
 return {'code':code}
async def broadcast(code):
 room=rooms.get(code)
 if room is None:return
 async def one(key,sock):
  try:await asyncio.wait_for(sock.send_json({'event':'state',**room.view(key)}),3)
  except Exception:
   if connections.get(code,{}).get(key)is sock:connections[code].pop(key,None);room.leave(key)
 await asyncio.gather(*(one(k,s)for k,s in list(connections[code].items())))
async def ticker(code):
 try:
  while code in rooms:
   await asyncio.sleep(.25)
   room=rooms[code];was=room.started is not None;changed=room.tick()
   # Broadcast a running timer once a second, plus immediate timeout.
   if changed or was and int(room.remaining*4)%4==0:await broadcast(code)
 except asyncio.CancelledError:pass
@app.websocket('/ws/{code}')
async def socket(ws:WebSocket,code:str):
 await ws.accept();key=None
 if code not in rooms:await ws.send_json({'event':'error','text':'Esa sala no existe o el servicio se reinició. Creá una partida nueva.'});await ws.close();return
 room=rooms[code]
 try:
  raw=await asyncio.wait_for(ws.receive_text(),30)
  if len(raw)>4096:raise GameError('Mensaje demasiado largo.')
  hello=json.loads(raw)
  if not isinstance(hello,dict):raise GameError('Entrada inválida.')
  key=room.join(hello.get('name',''),hello.get('key'));created[code]=time.monotonic()
  previous=connections[code].get(key);connections[code][key]=ws
  if previous and previous is not ws:await previous.close(code=4001,reason='Tu asiento se abrió en otra pestaña.')
  if code not in tickers or tickers[code].done():tickers[code]=asyncio.create_task(ticker(code))
  await ws.send_json({'event':'joined','key':key,'name':room.players[key]['name']});await broadcast(code)
  while True:
   raw=await ws.receive_text()
   if len(raw)>4096:raise GameError('Mensaje demasiado largo.')
   try:
    if connections[code].get(key)is not ws:break
    created[code]=time.monotonic()
    msg=json.loads(raw)
    if not isinstance(msg,dict):raise GameError('Acción inválida.')
    action=msg.get('action');token=msg.get('token')
    if action=='start':room.start(key)
    elif action=='spin':room.spin(key,token)
    elif action=='ready':room.ready(key,token)
    elif action=='pause':room.pause(key,token)
    elif action=='answer':room.answer(key,token,msg.get('choice'))
    elif action=='next':room.next(key,token)
    elif action=='refresh':pass
    else:raise GameError('Esa acción no existe.')
    await broadcast(code)
   except (GameError,json.JSONDecodeError)as e:await ws.send_json({'event':'error','text':str(e)})
 except (WebSocketDisconnect,asyncio.TimeoutError):pass
 except (GameError,json.JSONDecodeError,TypeError,AttributeError,ValueError)as e:
  try:await ws.send_json({'event':'error','text':str(e) if isinstance(e,GameError)else'No se pudo entrar. Revisá el nombre y el código.'})
  except Exception:pass
 finally:
  if key and connections.get(code,{}).get(key)is ws:
   connections[code].pop(key,None);room.leave(key);created[code]=time.monotonic();await broadcast(code)
@app.on_event('shutdown')
async def shutdown():
 for task in tickers.values():task.cancel()
