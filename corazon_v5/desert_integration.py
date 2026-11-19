"""Arena0.8, separate namespace and clock. No scene preparation endpoints."""
import asyncio,hashlib
from pathlib import Path
from fastapi.staticfiles import StaticFiles

def install(app):
 import webapp
 from desert_pilot import router,clock_loop
 app.include_router(router)
 app.mount('/desierto-assets',StaticFiles(directory=Path(__file__).parent/'desierto-assets'),name='desierto-assets')
 menu='<section id="arena-desierto-menu" aria-label="Arena del Desierto"><h2>Arena del Desierto</h2><p>Supervivencia en tiempo real para dos a cuatro personas, zombis y momias, tres rondas, armas por puntos ficticios, caminos con riesgo y vista de primera persona simulada. Sin dinero real. Beta: las salas se pierden si el servidor reinicia y falta probar comodidad con lector.</p><p><a href="/arena-del-desierto">Abrir Arena del Desierto</a></p></section>'
 needle='<button id="btn-modo-zombi"'
 index=webapp.PAGE.find(needle)
 if index<0:raise RuntimeError('Expected menu marker missing')
 end=webapp.PAGE.index('</button>',index)+len('</button>')
 webapp.PAGE=webapp.PAGE[:end]+menu+webapp.PAGE[end:]
 old=webapp.CLIENT_BUILD;webapp.CLIENT_BUILD=hashlib.sha256(webapp.PAGE.encode()).hexdigest()[:16];webapp.PAGE=webapp.PAGE.replace(old,webapp.CLIENT_BUILD)
 async def start():
  if getattr(app.state,'desert_clock',None) is None:app.state.desert_clock=asyncio.create_task(clock_loop())
 async def stop():
  task=getattr(app.state,'desert_clock',None)
  if task:
   task.cancel()
   try:await task
   except asyncio.CancelledError:pass
   app.state.desert_clock=None
 app.add_event_handler('startup',start)
 app.add_event_handler('shutdown',stop)
