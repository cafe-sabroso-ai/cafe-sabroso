import asyncio,secrets,time,re
from pathlib import Path
from pydantic import BaseModel,Field
from fastapi import HTTPException
from fastapi.responses import FileResponse
import edge_tts
import count_engine as E
rooms={}
class Create(BaseModel):
 name:str=Field(min_length=1,max_length=24)
 capacity:int=Field(default=4,ge=2,le=4)
 fill_bots:bool=False
class Join(Create):code:str
class Access(BaseModel):code:str;token:str
class Move(Access):action:str;count:int=0;revision:int=Field(ge=0);category:str='random'
def name(s):
 s=' '.join(s.split())
 if not s or not all(c.isalnum()or c in ' áéíóúÁÉÍÓÚñÑüÜ-_' for c in s):raise HTTPException(400,'Usá un apodo de letras y números, hasta veinticuatro caracteres.')
 return s
def auth(b):
 r=rooms.get(b.code.upper().strip())
 if not r:raise HTTPException(404,'La sala ya no existe.')
 if b.token not in r['tokens']:raise HTTPException(403,'Acceso incorrecto.')
 pid=r['tokens'][b.token];r['seen'][pid]=time.monotonic();r['used']=time.monotonic();return r,pid
def packet(r,pid):
 return {'code':r['code'],'me':pid,'players':[{'name':n,'connected':r['bots'][i]or time.monotonic()-r['seen'].get(i,0)<12,'bot':r['bots'][i]}for i,n in enumerate(r['names'])],'state':r['state'],'revision':r['revision'],'capacity':r['capacity'],'fill_bots':r['fill_bots'],'solo':r.get('solo',False)}
def install(app,audio,gate):
 root=Path(__file__).parent
 @app.get('/no-digas-21')
 async def page():return FileResponse(root/'nueve_static/count.html')
 @app.get('/no-digas-21/rules')
 async def rules():return {'text':E.RULES,'categories':[{'id':k,'label':v[0],'retos':len(v[1]),'preguntas':len(v[2])}for k,v in E.CATEGORIES.items()]}
 @app.post('/no-digas-21/create')
 async def create(b:Create):
  for code,r in list(rooms.items()):
   if time.monotonic()-r['used']>7200:rooms.pop(code,None)
  if len(rooms)>=16:raise HTTPException(429,'Límite de salas alcanzado.')
  code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')for _ in range(6))
  while code in rooms:code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')for _ in range(6))
  token=secrets.token_urlsafe(24);r=dict(code=code,names=[name(b.name)],bots=[False],capacity=b.capacity,fill_bots=b.fill_bots,tokens={token:0},state=None,revision=0,lock=asyncio.Lock(),seen={0:time.monotonic()},used=time.monotonic());rooms[code]=r
  return packet(r,0)|{'token':token}
 @app.post('/no-digas-21/solo')
 async def solo(b:Create):
  result=await create(Create(name=b.name,capacity=b.capacity,fill_bots=True))
  r=rooms[result['code']];r['solo']=True
  while len(r['names'])<r['capacity']:
   r['names'].append('Bot Café '+str(len(r['names'])+1));r['bots'].append(True)
  r['state']=E.fresh(r['names'],r['bots']);r['revision']+=1
  return packet(r,0)|{'token':result['token']}
 @app.post('/no-digas-21/join')
 async def join(b:Join):
  r=rooms.get(b.code.upper().strip())
  if not r or r.get('solo'):raise HTTPException(404,'No existe una sala compartida con ese código.')
  async with r['lock']:
   if r['state']:raise HTTPException(409,'La ronda ya empezó. Abrí otra sala.')
   if len(r['names'])>=r['capacity']:raise HTTPException(409,'La partida ya está completa: '+str(r['capacity'])+' lugares.')
   n=name(b.name)
   if n.casefold()in [n.casefold()for n in r['names']]:raise HTTPException(400,'Ese apodo ya está en la sala.')
   pid=len(r['names']);r['names'].append(n);r['bots'].append(False);token=secrets.token_urlsafe(24);r['tokens'][token]=pid;r['seen'][pid]=time.monotonic();r['used']=time.monotonic();r['revision']+=1
   return packet(r,pid)|{'token':token}
 @app.post('/no-digas-21/view')
 async def view(b:Access):
  r,pid=auth(b);return packet(r,pid)
 @app.post('/no-digas-21/move')
 async def move(b:Move):
  r,pid=auth(b)
  async with r['lock']:
   if b.revision!=r['revision']:return packet(r,pid)|{'reconciled':True}
   if any(not r['bots'][i] and time.monotonic()-r['seen'].get(i,0)>12 for i in range(len(r['names']))):raise HTTPException(409,'Falta una persona conectada. La mesa espera, sin perder el turno ni reemplazarla.')
   try:
    if b.action=='start':
     if pid!=0 or r['state']:raise ValueError('Solo quien creó la sala puede empezar, una vez.')
     if r['fill_bots']:
      while len(r['names'])<r['capacity']:
       r['names'].append('Bot Café '+str(len(r['names'])+1));r['bots'].append(True)
     r['state']=E.fresh(r['names'],r['bots'])
    else:
     if not r['state']:raise ValueError('Primero hay que empezar.')
     actor=pid;action=b.action;count=b.count
     if b.action=='bot':
      actor=r['state']['turn'] if r['state']['phase']=='play'else r['state']['loser']
      if pid!=0 or actor is None or not r['bots'][actor]:raise ValueError('Solo quien creó la sala avanza un bot identificado.')
      action='say'if r['state']['phase']=='play'else 'spin'
      count=secrets.randbelow(min(3,21-r['state']['last']))+1 if action=='say'else 0
     r['state']=E.act(r['state'],actor,action,count,b.category)
   except ValueError as e:raise HTTPException(400,str(e))
   r['revision']+=1;return packet(r,pid)
 @app.post('/no-digas-21/speech')
 async def speech(b:Access):
  r,pid=auth(b);s=r['state'];text=s['text']if s else 'Sala '+r['code']+'. '+str(len(r['names']))+' personas. Esperando que empiece quien creó la sala.'
  try:
   async with gate:
    data=bytearray()
    async def build():
     async for chunk in edge_tts.Communicate(text,'es-AR-ElenaNeural').stream():
      if chunk['type']=='audio':
       data.extend(chunk['data'])
       if len(data)>3*1024*1024:raise ValueError('Audio demasiado grande')
    await asyncio.wait_for(build(),40)
    if not data:raise ValueError()
   key=secrets.token_urlsafe(18);audio[key]=bytes(data)
   while len(audio)>24:audio.pop(next(iter(audio)))
   return {'url':'/nueve-y-media/api/audio/'+key+'.mp3','revision':r['revision'],'capacity':r['capacity'],'fill_bots':r['fill_bots'],'solo':r.get('solo',False)}
  except Exception:raise HTTPException(503,'Voz natural no disponible. El texto y los botones siguen disponibles.')
