from numero_escondido.app import app as numero_app

def install(app):
    app.mount("/numero-escondido", numero_app, name="numero-escondido")
