from numeros_cafe.app import app as numeros_app

def install(app):
    app.mount("/numeros-cafe", numeros_app, name="numeros-cafe")
