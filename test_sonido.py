"""Checks for the Adivina el sonido static integration (run inside the built image)."""
import hashlib
import os
import sys

sys.path.insert(0, "/app")
os.chdir("/app")

import webapp  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

app = FastAPI()
app.include_router(webapp.router)
import arena_integration  # noqa: E402
import leyenda_integration  # noqa: E402
import sonido_integration  # noqa: E402

arena_integration.install(app, webapp, origin="https://cafe-sabroso.onrender.com")
leyenda_integration.install(app, webapp)
sonido_integration.install(app, webapp)
client = TestClient(app)


def test_home_has_entry_before_leyenda():
    r = client.get("/amor-con-aroma-a-cafe")
    assert r.status_code == 200
    assert 'id="cafe-sonido-entry"' in r.text
    assert 'id="cafe-leyenda-entry"' in r.text
    assert r.text.index("cafe-sonido-entry") < r.text.index("cafe-leyenda-entry")


def test_game_index_served():
    r = client.get("/adivina-el-sonido/")
    assert r.status_code == 200
    assert "Adiviná el sonido" in r.text
    assert r.headers["content-type"].startswith("text/html")
    assert "connect-src 'self'" in r.headers["content-security-policy"]
    assert "noindex" in r.headers["x-robots-tag"]


def test_credits_and_manifest():
    r = client.get("/adivina-el-sonido/creditos.html")
    assert r.status_code == 200 and "CC BY" in r.text
    assert r.text.count("<tr") == 301  # header + 300 sounds
    r = client.get("/adivina-el-sonido/manifest.js")
    assert r.status_code == 200
    assert r.text.count('"file": "audio/') == 300


def test_audio_bytes_and_cache():
    r = client.get("/adivina-el-sonido/audio/abeja.mp3")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert "immutable" in r.headers["cache-control"]
    disk = open("/app/sonido_static/audio/abeja.mp3", "rb").read()
    assert hashlib.sha256(r.content).digest() == hashlib.sha256(disk).digest()


def test_traversal_and_unknown_blocked():
    for bad in ["../webapp.py", "..%2f..%2fwebapp.py", "audio/../../webapp.py",
                "style.css%00.html", "nonexistent.mp3", "audio"]:
        r = client.get("/adivina-el-sonido/" + bad)
        assert r.status_code in (400, 404, 405), bad


def test_leyenda_regression():
    assert client.get("/leyenda-cafe/").status_code == 200
