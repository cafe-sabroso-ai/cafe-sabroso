def install(app):
    from bomba_nueva.app import app as bomba_app
    app.mount("/bomba-nueva", bomba_app)
