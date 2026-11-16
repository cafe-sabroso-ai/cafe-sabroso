"""Local integration candidate. Not published. No Telegram access or deployment."""
import os
from urllib.parse import urlsplit
from pathlib import Path
from fastapi.responses import HTMLResponse
PREFIX='/arena-voces'
ENTRY='''<aside id="cafe-arena-entry" aria-labelledby="cafe-arena-title" style="border:2px solid #ffd18d;border-radius:14px;padding:16px;margin:16px 0;background:#211a29"><h2 id="cafe-arena-title">Arena de Voces</h2><p>Jugá solo con bots o creá una sala entre amigos. Retos y Verdad o Reto, con vidas y votación humana.</p><p>Modo experimental. Sala y puntajes propios: no cambia tus otras ruletas. Los Reyes es un ensayo corto.</p><a href="/arena-voces/" style="display:block;background:#ffe0ad;color:#201326;padding:14px;border-radius:10px;font-weight:bold;text-align:center">Entrar a Arena de Voces</a></aside>'''
def install(app,webapp,*,origin=None):
    origin=origin or os.getenv('CAFE_ARENA_ORIGIN','http://127.0.0.1:8895')
    u=urlsplit(origin)
    if not u.hostname or u.username or u.password or u.path or u.query or u.fragment or origin.endswith('/') or not (u.scheme=='https' or (u.scheme=='http' and u.hostname in ('127.0.0.1','localhost','testserver'))):
        raise RuntimeError('Exact HTTPS origin required outside local testing.')
    from arena_integrated import local_api
    local_api.ALLOWED_HOSTS={u.netloc};local_api.ALLOWED_ORIGINS={origin};local_api.COOKIE_SECURE=u.scheme=='https'
    sub=local_api.app
    for route in list(sub.routes):
        if getattr(route,'path',None) in ('/','/friends-rehearsal','/friends-state','/friends-action'):sub.routes.remove(route)
    @sub.get('/',response_class=HTMLResponse)
    async def entry():return HTMLResponse((Path(local_api.__file__).parent/'preview_landing.html').read_text())
    sub.add_api_route('/solo',local_api.home,methods=['GET'],response_class=HTMLResponse)
    @sub.middleware('http')
    async def arena_headers(request,call_next):
        response=await call_next(request)
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['X-Frame-Options']='DENY';response.headers['X-Robots-Tag']='noindex, nofollow, noarchive';response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        response.raw_headers=[(k,v.replace(b'Path=/',b'Path=/arena-voces')) if k==b'set-cookie' else (k,v) for k,v in response.raw_headers]
        return response
    marker='<section id="pantalla-inicio" aria-label="Pantalla de inicio">'
    assert webapp.PAGE.count(marker)==1 and 'id="cafe-arena-entry"' not in webapp.PAGE
    # Entry lives only on the start screen, never inside an active room/panel.
    webapp.PAGE=webapp.PAGE.replace(marker,marker+ENTRY,1)
    app.mount(PREFIX,sub,name='arena-voces')
    return sub
