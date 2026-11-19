"""Local preview server. Not imported into production. No bot credentials required."""
import asyncio,secrets,time
from pathlib import Path
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse,Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
import edge_tts
import nueve_engine as rules
ROOT=Path(__file__).parent
app=APIRouter()
sessions={};audio={};gate=asyncio.Semaphore(2)
class Move(BaseModel):
 token:str
 revision:int=Field(ge=0)
 action:str
class Speech(BaseModel):
 token:str
 revision:int=Field(ge=0)
def record(token):
 r=sessions.get(token)
 if not r:raise HTTPException(404,'La partida venció. Empezá otra partida.')
 r['used']=time.monotonic();return r
@app.get('/nueve-y-media/api/rules')
async def rules_text():return {'text':rules.RULES}
@app.post('/nueve-y-media/api/new')
async def new():
 for key,r in list(sessions.items()):
  if time.monotonic()-r['used']>7200:sessions.pop(key,None)
 if len(sessions)>=24:raise HTTPException(429,'El servidor alcanzó el límite de partidas. Probá de nuevo más tarde.')
 token=secrets.token_urlsafe(24);sessions[token]={'state':rules.fresh(),'used':time.monotonic(),'lock':asyncio.Lock()}
 return {'token':token,'state':rules.view(sessions[token]['state'])}
@app.post('/nueve-y-media/api/view')
async def view(body:Speech):return {'state':rules.view(record(body.token)['state'])}
@app.post('/nueve-y-media/api/move')
async def move(body:Move):
 r=record(body.token)
 async with r['lock']:
  if r['state']['revision']!=body.revision:return {'state':rules.view(r['state']),'reconciled':True}
  try:
   revision=r['state']['revision'];r['state']=rules.act(r['state'],body.action)
   if body.action=='restart':r['state']['revision']=revision+1
  except ValueError as e:raise HTTPException(400,str(e))
  return {'state':rules.view(r['state'])}
@app.post('/nueve-y-media/api/speech')
async def speech(body:Speech):
 r=record(body.token);st=r['state'];text=st['text']+' Puntaje: '+str(st['score'])+' de cinco. Vidas: '+str(st['lives'])+'.'
 if body.revision!=st['revision']:raise HTTPException(409,'La mano cambió. Leé el estado actual.')
 key=secrets.token_urlsafe(18)
 try:
  async with gate:
   data=bytearray()
   async def build():
    async for chunk in edge_tts.Communicate(text,'es-AR-ElenaNeural').stream():
     if chunk['type']=='audio':
      data.extend(chunk['data'])
      if len(data)>3*1024*1024:raise ValueError('Audio demasiado grande')
   await asyncio.wait_for(build(),40)
   if not data:raise ValueError('Sin audio')
  audio[key]=bytes(data)
  while len(audio)>24:audio.pop(next(iter(audio)))
  return {'text':text,'url':'/nueve-y-media/api/audio/'+key+'.mp3','revision':body.revision}
 except Exception:raise HTTPException(503,'No se pudo cargar la voz natural. El texto y los botones siguen disponibles; podés reintentar.')
@app.get('/nueve-y-media/api/audio/{key}.mp3')
async def play(key:str):
 if key not in audio:raise HTTPException(404,'Audio vencido')
 return Response(audio[key],media_type='audio/mpeg',headers={'Cache-Control':'no-store'})

router=app
