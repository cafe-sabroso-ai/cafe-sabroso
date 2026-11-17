from colina.app import app as colina_app
def install(app):
    app.mount("/colina", colina_app)
