from pathlib import Path
from fastapi.staticfiles import StaticFiles

def install(app):
    app.mount("/jardin", StaticFiles(directory=Path(__file__).with_name("jardin_static"), html=True), name="jardin")
