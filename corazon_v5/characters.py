"""Original cosmetic characters. Equal rules, native natural voice per character."""
import asyncio,logging
import edge_tts
CHARACTERS={
 'tomas':{'id':'tomas','name':'Tomás','gender':'hombre','voice':'es-AR-TomasNeural','coat':'#9c937a','skin':'#c5b396','hair':'#38505a','gesture':'paso firme y saludo corto','line':'Soy Tomás. Voy con paso firme. Si hace falta, corro. Primero escucho el camino.'},
 'mateo':{'id':'mateo','name':'Mateo','gender':'hombre','voice':'es-UY-MateoNeural','coat':'#71969e','skin':'#ae8d72','hair':'#253d45','gesture':'paso inclinado y brazo de señal','line':'Soy Mateo. Miro las salidas, marco el rumbo y corro cuando el paso está libre.'},
 'elena':{'id':'elena','name':'Elena','gender':'mujer','voice':'es-AR-ElenaNeural','coat':'#a58983','skin':'#d0b397','hair':'#59473b','gesture':'paso decidido y saludo de mano','line':'Soy Elena. Recorro la casa, escucho los pasos y elijo cuándo avanzar o correr.'},
 'valentina':{'id':'valentina','name':'Valentina','gender':'mujer','voice':'es-UY-ValentinaNeural','coat':'#859c73','skin':'#ae8d73','hair':'#332f35','gesture':'paso ligero y gesto de orientación','line':'Soy Valentina. Camino con cuidado y corro si el camino es seguro. Vamos a explorar.'}
}
_cache={}
async def own_audio(cid,text):
 c=CHARACTERS[cid];key=(cid,text)
 if key in _cache:return _cache[key]
 async def build():
  data=bytearray()
  async for chunk in edge_tts.Communicate(text,c['voice']).stream():
   if chunk['type']=='audio':data.extend(chunk['data'])
  if not data:raise RuntimeError('Character audio empty')
  return bytes(data)
 try:
  data=await asyncio.wait_for(build(),max(25,min(60,20+len(text)/40)))
  _cache[key]=data
  while len(_cache)>48:_cache.pop(next(iter(_cache)))
  return data
 except Exception as error:
  logging.getLogger('characters').warning('Character voice unavailable id=%s reason=%s',cid,type(error).__name__)
  return None

def action_line(cid,action):
 c=CHARACTERS[cid];name=c['name']
 return {'start':c['line'],'walk':{'tomas':'Avanzo con cuidado.','mateo':'Camino y miro la salida.','elena':'Voy hacia la otra habitación.','valentina':'Un paso a la vez.'}[cid],'run':{'tomas':'Camino conocido. ¡Corro!','mateo':'Paso libre, voy corriendo.','elena':'Ahora corro hasta la otra habitación.','valentina':'¡Voy corriendo por el paso libre!'}[cid],'open':'Abro la puerta y escucho antes de seguir.','bar':'Dejo la puerta trabada.','attack':'Mantengo la posición.'}.get(action,'')
