"""One approved Zombi bundle, additive mounts and a single bounded real-time clock."""
import asyncio
from pathlib import Path
from fastapi.staticfiles import StaticFiles

def install(app):
    import webapp
    from house_pilot import router as solo_router
    from coop_pilot import router as coop_router
    from realtime_pilot import router as rt_router,clock_loop
    root=Path(__file__).parent
    app.include_router(solo_router)
    app.include_router(coop_router)
    app.include_router(rt_router)
    for name in ('house-assets','character-assets','coop-assets','realtime-assets'):
        app.mount('/'+name,StaticFiles(directory=root/name),name=name)
    # The existing Zombi optional mando is replaced, not duplicated. Other mandos stay intact.
    app.mount('/zombi-atmosfera',StaticFiles(directory=root/'mando-assets'),name='zombi-atmosfera')
    webapp.PAGE=webapp.PAGE.replace('</body>','<script src="/character-assets/characters.js?v=zombi041"></script><script src="/zombi-atmosfera/zombi-weather.js?v=zombi041"></script></body>')
    menu='''<section id="zombi-casa-menu" aria-label="Casa Zombi, modos nuevos beta"><h2>Casa Zombi, modos beta</h2><p>Individual, cooperativo por turnos o supervivencia simultánea. Los datos de estas salas se pierden si el servidor reinicia. Tiempo real sigue durante la voz. La comodidad con TalkBack y el juego entre amigos todavía necesitan pruebas.</p><p><a href="/zombi-casa">Casa individual, diez y jefe</a></p><p><a href="/zombi-casa-coop">Casa cooperativa, por turnos</a></p><p><a href="/zombi-casa-tiempo-real">Supervivencia, todos al mismo tiempo</a></p></section>'''
    needle='<button id="btn-modo-zombi"'
    index=webapp.PAGE.find(needle)
    if index<0:raise RuntimeError('Zombi selector not found; refusing partial installation')
    end=webapp.PAGE.index('</button>',index)+len('</button>')
    webapp.PAGE=webapp.PAGE[:end]+menu+webapp.PAGE[end:]
    import hashlib
    previous=webapp.CLIENT_BUILD
    webapp.CLIENT_BUILD=hashlib.sha256(webapp.PAGE.encode()).hexdigest()[:16]
    webapp.PAGE=webapp.PAGE.replace(previous,webapp.CLIENT_BUILD).replace('zombi.js?v=010','zombi.js?v=zombi041').replace('zombi.css?v=010','zombi.css?v=zombi041')
    async def start_clock():
        if getattr(app.state,'zombi_clock',None) is None:
            app.state.zombi_clock=asyncio.create_task(clock_loop())
    async def stop_clock():
        task=getattr(app.state,'zombi_clock',None)
        if task:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
            app.state.zombi_clock=None
    app.add_event_handler('startup',start_clock)
    app.add_event_handler('shutdown',stop_clock)
