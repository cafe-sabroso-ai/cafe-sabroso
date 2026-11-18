"""Local preview only. No account, database, payments or production writes."""
import asyncio,json,hashlib,time
from collections import OrderedDict
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
ROOT=Path(__file__).parent
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
VOICES={'es-AR-ElenaNeural','es-AR-TomasNeural','es-UY-ValentinaNeural','es-MX-DaliaNeural','es-MX-JorgeNeural','es-CO-GonzaloNeural','es-CL-CatalinaNeural'}
cache=OrderedDict();lock=asyncio.Semaphore(1)
@app.post('/voice')
async def voice(request:Request):
 origin=request.headers.get('origin')
 if origin and origin not in ('http://'+request.headers.get('host',''),'https://'+request.headers.get('host','')):raise HTTPException(403,'Origen no permitido')
 raw=await request.body()
 if len(raw)>8000:raise HTTPException(400,'Texto demasiado largo')
 try:d=json.loads(raw)
 except Exception:raise HTTPException(400,'Pedido inválido')
 if not isinstance(d,dict)or not isinstance(d.get('text'),str)or not 1<=len(d['text'])<=1200 or not isinstance(d.get('voice'),str)or d['voice']not in VOICES:raise HTTPException(400,'Texto o voz inválidos')
 key=(d['text'],d['voice'])
 if key in cache:cache.move_to_end(key);return Response(cache[key],media_type='audio/mpeg',headers={'Cache-Control':'no-store'})
 try:await asyncio.wait_for(lock.acquire(),2)
 except asyncio.TimeoutError:raise HTTPException(503,'Voz ocupada. La carrera no avanza mientras escuchás.')
 try:
  if key in cache:audio=cache[key]
  else:
   import edge_tts
   async def synth():
    parts=[];size=0
    async for part in edge_tts.Communicate(d['text'],d['voice']).stream():
     if part['type']=='audio':
      size+=len(part['data'])
      if size>700000:raise ValueError('Audio demasiado grande')
      parts.append(part['data'])
    if not parts:raise ValueError('Audio vacío')
    return b''.join(parts)
   try:audio=await asyncio.wait_for(synth(),25)
   except Exception:raise HTTPException(503,'Voz no disponible. Seguí con texto o lector de pantalla.')
   cache[key]=audio
   while len(cache)>24 or sum(map(len,cache.values()))>8000000:cache.popitem(last=False)
  return Response(audio,media_type='audio/mpeg',headers={'Cache-Control':'no-store'})
 finally:lock.release()
app.mount('/',StaticFiles(directory=ROOT/'turbo_cafe_static',html=True),name='turbo-cafe-local')

def install(parent):
 parent.mount("/turbo-cafe",app,name="turbo-cafe")
