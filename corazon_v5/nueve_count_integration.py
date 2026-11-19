"""Additive, separately namespaced card and counting games."""
from pathlib import Path
from fastapi.staticfiles import StaticFiles

def install(app):
 import webapp
 import nueve_routes
 from count_routes import install as install_count
 app.include_router(nueve_routes.router)
 install_count(app,nueve_routes.audio,nueve_routes.gate)
 app.mount('/nueve-assets',StaticFiles(directory=Path(__file__).parent/'nueve_static'),name='nueve-assets')
 needle='<button id="btn-modo-veintiuno"'
 idx=webapp.PAGE.find(needle)
 if idx<0:raise RuntimeError('Expected card selector missing')
 end=webapp.PAGE.index('</button>',idx)+len('</button>')
 menu='<section aria-label="No digas 21, contar y ruleta"><h2>No digas 21, contar y ruleta</h2><p>Decí de uno a tres números por turno. Quien dice veintiuno gira reto o pregunta. De dos a cuatro lugares, con bots opcionales identificados. No es el Veintiuno de cartas.</p><a href="/no-digas-21">Abrir No digas 21</a></section>'
 webapp.PAGE=webapp.PAGE[:end]+menu+webapp.PAGE[end:]
 import hashlib
 old=webapp.CLIENT_BUILD;webapp.CLIENT_BUILD=hashlib.sha256(webapp.PAGE.encode()).hexdigest()[:16];webapp.PAGE=webapp.PAGE.replace(old,webapp.CLIENT_BUILD)
