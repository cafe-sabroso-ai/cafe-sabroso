import asyncio,json,re,time
from pathlib import Path
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,Request
from fastapi.responses import HTMLResponse,Response
if __package__:
    from .engine import Room,GameError
else:
    from engine import Room,GameError
app=FastAPI(title='La bomba - borrador local')
rooms={};connections={};created={}
@app.get('/')
async def home():return HTMLResponse(Path(__file__).with_name('index.html').read_text())
@app.get('/health')
async def health():return {'ok':True,'draft':True,'production':False}
@app.post('/rooms')
async def create():
    for code,ts in list(created.items()):
        if time.monotonic()-ts>21600 and not connections.get(code):rooms.pop(code,None);created.pop(code,None)
    if len(rooms)>=100:raise HTTPException(503,'El borrador llegó a cien salas. Reinicialo para seguir probando.')
    import secrets
    code=secrets.token_hex(4).upper();rooms[code]=Room();created[code]=time.monotonic();connections[code]={};return {'code':code}
async def broadcast(code):
    room=rooms[code]
    async def one(key,sock):
        try:await asyncio.wait_for(sock.send_json({'event':'state',**room.view(key)}),3)
        except Exception:
            if connections[code].get(key)is sock:connections[code].pop(key,None)
    await asyncio.gather(*(one(k,s) for k,s in list(connections[code].items())))
@app.websocket('/ws/{code}')
async def socket(ws:WebSocket,code:str):
    await ws.accept();key=None
    if code not in rooms:await ws.send_json({'event':'error','text':'Esa sala no existe o se reinició.'});await ws.close();return
    room=rooms[code]
    try:
        hello=await asyncio.wait_for(ws.receive_json(),30)
        key=room.join(hello.get('name',''),hello.get('key'))
        ensure_ticker(code)
        previous=connections[code].get(key);connections[code][key]=ws
        if previous and previous is not ws:await previous.close(code=4001,reason='Asiento abierto en otra pestaña')
        await ws.send_json({'event':'joined','key':key});await broadcast(code)
        while True:
            raw=await ws.receive_text()
            if len(raw)>2048:raise GameError('Mensaje demasiado largo.')
            try:
                if connections[code].get(key)is not ws:break
                msg=json.loads(raw)
                if not isinstance(msg,dict):raise GameError('Mensaje inválido.')
                action=msg.get('action')
                if action=='start':room.start(key,msg.get('mode','tranquila'))
                elif action=='next':room.next_round(key)
                elif action=='answer':room.answer(key,msg.get('token'),msg.get('choice'))
                elif action=='ready':room.ready(key,msg.get('token'))
                elif action=='refresh':pass
                else:raise GameError('Acción no disponible.')
                ensure_ticker(code);await broadcast(code)
            except (GameError,json.JSONDecodeError) as e:await ws.send_json({'event':'error','text':str(e)})
    except (WebSocketDisconnect,asyncio.TimeoutError):pass
    except (GameError,AttributeError,TypeError,ValueError):
        try:await ws.send_json({'event':'error','text':'No se pudo entrar. Revisá el nombre y la sala.'})
        except Exception:pass
    finally:
        if key and connections[code].get(key)is ws:connections[code].pop(key,None)

# Bounded text-to-speech cache. No user audio is uploaded here.
from collections import OrderedDict
voice_cache=OrderedDict();voice_lock=asyncio.Semaphore(1)
@app.post('/voice')
async def voice(request:Request):
    data=await request.json()
    if not isinstance(data,dict):raise HTTPException(400,'Pedido inválido')
    code=data.get('code');key=data.get('key')
    if not isinstance(code,str)or not isinstance(key,str)or code not in rooms or key not in rooms[code].players:raise HTTPException(403,'Asiento no válido')
    state=rooms[code].view(key);q=state['question']
    kind=data.get('kind','question')
    if kind not in ('question','status','heat'):raise HTTPException(400,'Lectura no válida')
    if kind=='heat':text=state['heat_text']+' La lectura sigue en pausa.'
    elif kind=='status':
        p=state['me'];text=state['message']+f" Tenés {p['lives']} vidas y {p['score']} aciertos. "+('La bomba la tiene '+str(state['holder'])+'. ' if state['holder'] else '')+state['feedback']
    else:
        if not q:raise HTTPException(409,'Todavía no hay pregunta')
        text=state['heat_text']+f" Ronda {state['round']}. La bomba la tiene {state['holder']}. "+q['question']+' '+'. '.join(f'Opción {i+1}: {v}'for i,v in enumerate(q['options']))
    async with voice_lock:
        if text in voice_cache:
            voice_cache.move_to_end(text);audio=voice_cache[text]
        else:
            import edge_tts
            async def synth():
                pieces=[];size=0
                async for part in edge_tts.Communicate(text,'es-AR-ElenaNeural').stream():
                    if part['type']=='audio':
                        size+=len(part['data'])
                        if size>600000:raise ValueError('Audio demasiado grande')
                        pieces.append(part['data'])
                if not pieces:raise ValueError('Audio vacío')
                return b''.join(pieces)
            try:audio=await asyncio.wait_for(synth(),25)
            except Exception:raise HTTPException(503,'Voz no disponible; usá la voz del navegador o tu lector')
            voice_cache[text]=audio
            while len(voice_cache)>8:voice_cache.popitem(last=False)
    return Response(audio,media_type='audio/mpeg',headers={'Cache-Control':'no-store'})

# One timer per active room, never one timer per player.
tickers={}
def ensure_ticker(code):
    if code in tickers and not tickers[code].done():return
    async def run():
        try:
            while code in rooms:
                room=rooms[code]
                changed=room.tick()
                if changed:await broadcast(code)
                if room.phase=='finished':break
                if not connections.get(code):
                    # No connection does not pause a fuse that already started.
                    if room.phase!='answering':break
                await asyncio.sleep(.15)
        finally:tickers.pop(code,None)
    tickers[code]=asyncio.create_task(run())
