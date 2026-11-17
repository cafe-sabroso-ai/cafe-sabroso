from ruleta_cafe.app import app as ruleta_app

def install(app):
    app.mount("/ruleta-cafe", ruleta_app, name="ruleta-cafe")
