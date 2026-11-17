from pathlib import Path
from fastapi.staticfiles import StaticFiles

def install(app):
    app.mount("/constelaciones", StaticFiles(directory=Path(__file__).with_name("constelaciones_static"), html=True), name="constelaciones")
