"""Isolated static adventure integration. No API, cloud saves or accounts."""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
PREFIX='/leyenda-cafe'
ENTRY='''<aside id="cafe-leyenda-entry" aria-labelledby="cafe-leyenda-title" style="border:2px solid #ffd18d;border-radius:14px;padding:16px;margin:16px 0;background:#10202f"><h2 id="cafe-leyenda-title">Leyenda del Café Perdido</h2><p>Una aventura original: siete personajes, catorce capítulos cortos, decisiones e imágenes.</p><p>Jugá solo o compartí este dispositivo. Narración y sonidos opcionales. Sin dinero real.</p><a href="/leyenda-cafe/" style="display:block;background:#ffe0ad;color:#201326;padding:14px;border-radius:10px;font-weight:bold;text-align:center">Entrar a Leyenda del Café Perdido</a></aside>'''
def install(app,webapp):
    root=Path(__file__).parent/'leyenda_static'
    allowed={'index.html':'text/html','style.css':'text/css','engine.js':'text/javascript','art.js':'text/javascript','ui.js':'text/javascript'}
    router=APIRouter(prefix=PREFIX)
    def response(name):
        if name not in allowed:raise HTTPException(status_code=404)
        return FileResponse(root/name,media_type=allowed[name],headers={
          'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
          'X-Frame-Options':'DENY','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
          'Permissions-Policy':'camera=(), microphone=(), geolocation=()', 'X-Robots-Tag':'noindex, nofollow, noarchive'})
    @router.get('/')
    async def home():return response('index.html')
    @router.get('/{name}')
    async def asset(name:str):return response(name)
    marker='<section id="pantalla-inicio" aria-label="Pantalla de inicio">'
    assert webapp.PAGE.count(marker)==1 and 'id="cafe-leyenda-entry"' not in webapp.PAGE
    webapp.PAGE=webapp.PAGE.replace(marker,marker+ENTRY,1)
    app.include_router(router)
