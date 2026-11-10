"""Amor con aroma a café: the shared web ruleta.

A real-time multiplayer wheel for Rocky and his friends: one opens a room,
shares the link, everyone plays the SAME wheel in the browser. No Telegram,
no login, no ads, no redirects. One tap to enter unlocks sound; from then on
the server's voices (the same catalog as the Telegram bot) narrate every
event to ALL players at once: nobody can lie about what the wheel said.

Design spec (Rocky, 2026-11-10): black background, colorful wheel, joined
hearts in the title, coffee/mate/pastelito/hearts icons, a Retos o Verdad
section with harmless dares ("no locuras"), fully screen-reader accessible.
"""

import asyncio
import hashlib
import json
import logging
import random
import string
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response

log = logging.getLogger("telegram-voice-bot")

router = APIRouter()

# ---------------------------------------------------------------------------
# Retos o Verdad: curated, harmless, doable dares and questions. "No locuras."
# ---------------------------------------------------------------------------
RETOS = [
    "Imitá a un animal hasta que alguien adivine cuál es.",
    "Cantá el estribillo de una canción que te guste.",
    "Contá un chiste corto, aunque sea malo.",
    "Hablá con acento de otro país por dos turnos.",
    "Decí un trabalenguas tres veces seguidas.",
    "Describí tu comida favorita sin nombrarla; los demás adivinan.",
    "Hacé el brindis más exagerado que puedas por el grupo.",
    "Tarareá una canción conocida hasta que la adivinen.",
    "Decí 5 cosas que te pongan contento, sin parar.",
    "Hablá como locutor de radio por un minuto.",
    "Contá tu mejor anécdota de la escuela.",
    "Hacé una publicidad inventada del mate o del café.",
    "Decí el abecedario lo más rápido que puedas.",
    "Imitá a un personaje famoso; los demás adivinan quién es.",
    "Nombrá 10 frutas en 15 segundos.",
    "Contá qué harías con un millón de pesos, en 30 segundos.",
    "Hacé una rima con el nombre de cada jugador.",
    "Describí tu película favorita en tres frases, sin decir el título.",
    "Saludá a cada jugador con un apodo cariñoso inventado.",
    "Contá un recuerdo feliz de cuando eras chico.",
    "Hablá en verso durante un turno completo.",
    "Hacé el sonido de 3 animales; el grupo puntúa el mejor.",
    "Decí una palabra bonita para cada letra de tu nombre.",
    "Contá qué superpoder tendrías y por qué.",
    "Hacé una entrevista de 3 preguntas al jugador de tu derecha.",
    "Inventá el nombre y el lema de una banda con otro jugador.",
    "Describí el plan perfecto de un domingo, con detalle.",
    "Hablá como si fueras el clima del noticiero.",
    "Decí 3 cosas buenas del jugador que giró antes que vos.",
    "Cantá el feliz cumpleaños al que cumpla más cerca de hoy.",
]
VERDADES = [
    "¿Cuál es tu comida favorita de todos los tiempos?",
    "¿A qué edad diste tu primer beso, más o menos?",
    "¿Qué canción cantás cuando nadie te escucha?",
    "¿Cuál fue tu momento más vergonzoso que hoy te da risa?",
    "¿Qué es lo que más te gusta de este grupo?",
    "¿Qué harías si fueras invisible por un día?",
    "¿Cuál es tu recuerdo favorito del año pasado?",
    "¿Qué comida odiabas de chico y ahora te encanta?",
    "¿Quién fue tu primer amor platónico?",
    "¿Qué es lo más loco que hiciste por un amigo?",
    "¿Qué programa o serie ves a escondidas?",
    "¿Qué te da un poco de miedo pero querés intentar?",
    "¿Cuál es tu lugar feliz?",
    "¿Qué mentira chiquita dijiste esta semana?",
    "¿A quién del grupo llamarías a las 3 de la mañana?",
    "¿Qué es lo primero que harías si ganaras la lotería?",
    "¿Cuál fue el mejor regalo que te hicieron?",
    "¿Qué apodo tuviste y cómo lo ganaste?",
    "¿Qué es algo que todos aman y a vos no te convence?",
    "¿Cuál es tu talento secreto?",
    "¿Qué te gustaría que el grupo haga más seguido?",
    "¿Qué película podés ver mil veces?",
    "¿Qué es lo más amable que hicieron por vos?",
    "¿Qué te pone de buen humor al instante?",
    "¿Si pudieras cenar con cualquier persona, con quién?",
    "¿Qué costumbre tuya hace reír a los demás?",
    "¿Cuál es tu olor favorito?",
    "¿Qué edad te gustaría tener para siempre y por qué?",
    "¿Qué es lo más valiente que hiciste?",
    "¿Qué querías ser de grande cuando tenías 10 años?",
]

SEGMENTS = ["reto", "verdad"]  # the wheel alternates these
SEGMENT_LABELS = {"reto": "RETO", "verdad": "VERDAD"}
SEGMENT_COLORS = {"reto": "#e53935", "verdad": "#1e88e5"}

# ---------------------------------------------------------------------------
# Rooms: everything in memory (party games; a restart ends the sala).
# ---------------------------------------------------------------------------
rooms = {}
audio_cache = {}  # key -> (mp3 bytes, timestamp)


def new_room_code() -> str:
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in rooms:
            return code


def room_state(room) -> dict:
    players = room["players"]
    current = players[room["turn"] % len(players)]["name"] if players else None
    return {
        "event": "state",
        "players": [p["name"] for p in players],
        "turn": current,
        "spinning": room["spinning"],
    }


async def broadcast(room, message: dict):
    data = json.dumps(message, ensure_ascii=False)
    stale = []
    for player in room["players"]:
        try:
            await player["ws"].send_text(data)
        except Exception:
            stale.append(player)
    for player in stale:
        room["players"].remove(player)


async def ogg_to_mp3(ogg: bytes) -> bytes:
    """Safari can't play ogg/opus; every phone plays mp3."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "in.ogg"
        target = Path(directory) / "out.mp3"
        source.write_bytes(ogg)
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source), "-c:a", "libmp3lame", "-b:a", "64k", str(target),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError(f"ffmpeg mp3 failed: {stderr.decode()[:300]}")
        return target.read_bytes()


async def narrate(room, text: str):
    """Synthesize the announcement ONCE server-side; everyone plays the same mp3."""
    from app import synthesize  # local import: app.py mounts this router

    voice = room.get("voice") or "es-AR-ElenaNeural"
    try:
        mp3 = await ogg_to_mp3(await synthesize(text, voice))
    except Exception:
        log.exception("Web sala: synthesis failed; broadcasting text only")
        await broadcast(room, {"event": "say", "text": text, "audio": None})
        return
    key = hashlib.sha256(mp3).hexdigest()[:24]
    audio_cache[key] = (mp3, time.time())
    # Trim clips older than an hour so the cache stays small.
    for old_key, (_, ts) in list(audio_cache.items()):
        if time.time() - ts > 3600:
            audio_cache.pop(old_key, None)
    await broadcast(
        room,
        {"event": "say", "text": text, "audio": f"/amor-con-aroma-a-cafe/audio/{key}.mp3"},
    )


async def do_spin(room, player_name: str):
    room["spinning"] = True
    segment = random.choice(SEGMENTS)
    bank, used = (RETOS, room["used_retos"]) if segment == "reto" else (VERDADES, room["used_verdades"])
    available = [item for item in bank if item not in used]
    if not available:
        used.clear()
        available = list(bank)
    pick = random.choice(available)
    used.add(pick)
    angle = random.randint(0, 359)
    await broadcast(
        room,
        {
            "event": "spin_start",
            "player": player_name,
            "angle": angle,
            "segment": segment,
            "colors": [SEGMENT_COLORS[s] for s in SEGMENTS],
            "labels": [SEGMENT_LABELS[s] for s in SEGMENTS],
        },
    )
    label = SEGMENT_LABELS[segment]
    announce = (
        f"¡Giramos la ruleta! Gira, gira... ¡paró! ¡{player_name}, te salió {label}! "
        f"{label} para {player_name}: {pick}"
    )
    # The wheel spins ~4s on screen; the voice lands right as it stops.
    await asyncio.sleep(3.5)
    await narrate(room, announce)
    room["players_turn_done"] = True
    room["turn"] += 1
    room["spinning"] = False
    await broadcast(room, room_state(room))


@router.websocket("/amor-con-aroma-a-cafe/ws/{code}")
async def sala_ws(websocket: WebSocket, code: str, name: str = ""):
    code = code.upper()
    room = rooms.get(code)
    if room is None:
        await websocket.close(code=4004)
        return
    name = (name or "").strip()[:24] or f"Jugador {len(room['players']) + 1}"
    await websocket.accept()
    player = {"name": name, "ws": websocket}
    room["players"].append(player)
    log.info("Web sala %s: %s joined (%s players)", code, name, len(room["players"]))
    await websocket.send_text(json.dumps(
        {"event": "welcome", "name": name}, ensure_ascii=False
    ))
    if len(room["players"]) == 1:
        await narrate(
            room,
            f"¡Listo, {name}! Ya estás en la mesa. No hace falta escribir nada. "
            "Pasales el link a tus amigos con el botón Copiar el link. "
            "Cuando te toque, se activa el botón Girar la ruleta.",
        )
    else:
        await narrate(room, f"¡{name} se sumó a la mesa! Ya son {len(room['players'])}.")
    await broadcast(room, room_state(room))
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            action = message.get("action")
            if action == "spin":
                players = room["players"]
                if not players or room["spinning"]:
                    continue
                current = players[room["turn"] % len(players)]
                if current is not player:
                    await websocket.send_text(json.dumps(
                        {"event": "say", "text": "Todavía no es tu turno.", "audio": None},
                        ensure_ascii=False,
                    ))
                    continue
                asyncio.create_task(do_spin(room, player["name"]))
            elif action == "rename":
                new_name = (message.get("name") or "").strip()[:24]
                if new_name:
                    player["name"] = new_name
                    await broadcast(room, room_state(room))
    except WebSocketDisconnect:
        pass
    finally:
        if player in room["players"]:
            room["players"].remove(player)
            log.info("Web sala %s: %s left", code, name)
            if room["players"]:
                await narrate(room, f"{name} se fue de la mesa.")
                await broadcast(room, room_state(room))
            else:
                rooms.pop(code, None)


@router.post("/amor-con-aroma-a-cafe/api/salas")
async def crear_sala():
    code = new_room_code()
    rooms[code] = {
        "players": [],
        "turn": 0,
        "spinning": False,
        "used_retos": set(),
        "used_verdades": set(),
        "voice": random.choice(
            ["es-AR-ElenaNeural", "es-AR-TomasNeural", "es-UY-ValentinaNeural"]
        ),
    }
    return {"code": code}


@router.get("/amor-con-aroma-a-cafe/audio/{key}.mp3")
async def sala_audio(key: str):
    entry = audio_cache.get(key)
    if not entry:
        return Response(status_code=404)
    return Response(content=entry[0], media_type="audio/mpeg")


# ---------------------------------------------------------------------------
# The page: one HTML file, no build step, screen-reader first.
# ---------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>💕 Amor con aroma a café 💕</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: #000; color: #fff; min-height: 100vh;
    font-family: system-ui, sans-serif; text-align: center;
    display: flex; flex-direction: column; align-items: center;
    padding: 1rem;
  }
  h1 { font-size: 1.9rem; margin: 0.5rem 0 0; color: #ffb6c1; }
  .icons { font-size: 1.6rem; margin: 0.4rem 0 1rem; letter-spacing: 0.6rem; }
  button {
    font-size: 1.5rem; padding: 1rem 2rem; border-radius: 1rem; border: none;
    background: #d81b60; color: #fff; cursor: pointer; margin: 0.5rem;
    min-width: 14rem; min-height: 3.5rem;
  }
  button.secondary { background: #3949ab; }
  button:disabled { background: #555; color: #aaa; }
  button:focus-visible, input:focus-visible { outline: 4px solid #fdd835; outline-offset: 2px; }
  #wheel { width: min(80vw, 320px); height: min(80vw, 320px); margin: 1rem; }
  #estado {
    font-size: 1.4rem; min-height: 2.2rem; margin: 0.5rem; color: #fdd835;
  }
  #jugadores { font-size: 1.1rem; color: #b2dfdb; margin: 0.5rem; }
  #compartir {
    background: #101418; border: 2px dashed #8e24aa; border-radius: 0.8rem;
    padding: 0.8rem; margin: 0.5rem; font-size: 1.1rem; word-break: break-all;
    max-width: 34rem;
  }
  .visually-hidden {
    position: absolute; width: 1px; height: 1px; overflow: hidden;
    clip: rect(0 0 0 0); white-space: nowrap;
  }
</style>
</head>
<body>
  <header>
    <h1>💕 Amor con aroma a café 💕</h1>
    <div class="icons" aria-hidden="true">☕ 🧉 🧁 💗</div>
  </header>

  <main>
    <p class="visually-hidden">
      Juego de la ruleta de retos y verdades para jugar con amigos.
      No hace falta escribir nada: todo se hace con botones
      y cada jugada se anuncia en voz alta.
    </p>
    <p id="estado" role="status" tabindex="-1">Bienvenido a la mesa.</p>

    <div id="entrada">
      <button id="btn-crear" aria-label="Crear una mesa nueva"><span aria-hidden="true">☕ </span>Crear una mesa nueva</button>
      <button id="btn-entrar" class="secondary" hidden aria-label="Entrar a jugar"><span aria-hidden="true">💗 </span>Entrar a jugar</button>
    </div>

    <div id="sala" hidden>
      <div id="compartir" hidden>
        Pasá este link a tus amigos:<br><strong id="link"></strong><br>
        <button id="btn-copiar" class="secondary" aria-label="Copiar el link para invitar a tus amigos"><span aria-hidden="true">📤 </span>Copiar el link</button>
      </div>
      <canvas id="wheel" width="640" height="640" aria-hidden="true"></canvas>
      <p id="jugadores" role="status"></p>
      <button id="btn-girar" disabled><span aria-hidden="true">🎡 </span><span id="btn-girar-text">Girar la ruleta</span></button>
      <p id="resultado" role="status" aria-live="polite"></p>
    </div>

    <div id="voz" class="visually-hidden" aria-live="assertive"></div>
    <audio id="player"></audio>
  </main>

<script>
"use strict";
const $ = (id) => document.getElementById(id);
const estado = $("estado"), voz = $("voz"), player = $("player");
const salaDiv = $("sala"), entrada = $("entrada");
const btnGirar = $("btn-girar");
let ws = null, audioUnlocked = false;
// Mismo nombre en cada visita: el servidor lo asigna una vez y lo guardamos.
let myName = localStorage.getItem("cafe_nombre") || null;

function announce(text) {
  estado.textContent = text;
  voz.textContent = "";
  setTimeout(() => { voz.textContent = text; }, 60);
}

function playClip(url) {
  if (!url || !audioUnlocked) return;
  player.src = url;
  player.play().catch(() => {});
}

function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  player.play().then(() => player.pause()).catch(() => {});
}

// --- La ruleta ---
const canvas = $("wheel"), ctx = canvas.getContext("2d");
const LABELS = ["RETO", "VERDAD"];
const COLORS = ["#e53935", "#1e88e5"];
let rotation = 0;

function drawWheel(rot) {
  const c = canvas.width / 2, r = c - 10;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const n = 8;
  for (let i = 0; i < n; i++) {
    const start = rot + (i * 2 * Math.PI) / n, end = rot + ((i + 1) * 2 * Math.PI) / n;
    ctx.beginPath(); ctx.moveTo(c, c); ctx.arc(c, c, r, start, end); ctx.closePath();
    ctx.fillStyle = COLORS[i % 2]; ctx.fill();
    ctx.strokeStyle = "#000"; ctx.lineWidth = 4; ctx.stroke();
    ctx.save();
    ctx.translate(c, c); ctx.rotate(start + Math.PI / n);
    ctx.fillStyle = "#fff"; ctx.font = "bold 34px system-ui";
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    ctx.fillText(LABELS[i % 2], r - 24, 0);
    ctx.restore();
  }
  ctx.beginPath(); ctx.arc(c, c, 26, 0, 2 * Math.PI);
  ctx.fillStyle = "#fdd835"; ctx.fill();
  // Pointer
  ctx.beginPath(); ctx.moveTo(c - 18, 8); ctx.lineTo(c + 18, 8); ctx.lineTo(c, 44);
  ctx.closePath(); ctx.fillStyle = "#fdd835"; ctx.fill();
}
drawWheel(0);

let animId = null;
function spinAnimation(finalAngle, done) {
  const start = rotation, giros = 5 * 2 * Math.PI;
  const target = giros + ((360 - finalAngle) * Math.PI) / 180;
  const dur = 3600, t0 = performance.now();
  cancelAnimationFrame(animId);
  function frame(t) {
    const k = Math.min(1, (t - t0) / dur);
    const ease = 1 - Math.pow(1 - k, 3);
    rotation = start + (target - start) * ease;
    drawWheel(rotation % (2 * Math.PI));
    if (k < 1) animId = requestAnimationFrame(frame); else if (done) done();
  }
  animId = requestAnimationFrame(frame);
}

// --- Entrada ---
const parts = location.pathname.split("/");
const salaCode = parts[2] === "sala" ? (parts[3] || "").toUpperCase() : null;
const btnCrear = $("btn-crear"), btnEntrar = $("btn-entrar");
let announcedTurn = false;

function setGirar(text) { $("btn-girar-text").textContent = text; }

function enterSala(code) {
  entrada.hidden = true;
  salaDiv.hidden = false;
  $("compartir").hidden = false;
  $("link").textContent = location.origin + "/amor-con-aroma-a-cafe/sala/" + code;
  estado.focus();
  connect(code);
}

if (salaCode) {
  btnEntrar.hidden = false;
  announce("Te invitaron a una mesa. Tocá el botón Entrar a jugar. No hace falta escribir nada.");
} else {
  announce("Bienvenido. Tocá el botón Crear una mesa nueva para empezar. No hace falta escribir nada.");
}

btnCrear.addEventListener("click", async () => {
  unlockAudio();  // EL ÚNICO TOQUE: desde acá las voces suenan solas.
  btnCrear.disabled = true;
  announce("Creando la mesa...");
  try {
    const res = await fetch("/amor-con-aroma-a-cafe/api/salas", {method: "POST"});
    const data = await res.json();
    // Sin recargar la página: la recarga puede robar el foco y abrir el teclado.
    history.pushState(null, "", "/amor-con-aroma-a-cafe/sala/" + data.code);
    enterSala(data.code);
  } catch (err) {
    btnCrear.disabled = false;
    announce("No pude crear la mesa. Tocá el botón Crear una mesa nueva otra vez.");
  }
});

btnEntrar.addEventListener("click", () => {
  unlockAudio();  // EL ÚNICO TOQUE: desde acá las voces suenan solas.
  enterSala(salaCode);
});

$("btn-copiar").addEventListener("click", async () => {
  const link = $("link").textContent;
  try {
    await navigator.clipboard.writeText(link);
    announce("Link copiado. Pegalo en un mensaje para invitar a tus amigos.");
  } catch (err) {
    announce("No pude copiarlo. El link está escrito arriba.");
  }
});

function connect(code) {
  ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://")
    + location.host + "/amor-con-aroma-a-cafe/ws/" + code
    + (myName ? "?name=" + encodeURIComponent(myName) : ""));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.event === "welcome") {
      myName = msg.name;
      localStorage.setItem("cafe_nombre", myName);
      const codeSpelled = code.split("").join(" ");
      announce("Estás en la mesa " + codeSpelled + " como " + myName + ". Cuando te toque, se activa el botón Girar la ruleta.");
    } else if (msg.event === "state") {
      $("jugadores").textContent =
        "En la mesa: " + msg.players.join(", ")
        + (msg.turn ? ". Le toca a " + msg.turn + "." : "");
      const mine = msg.turn && msg.turn === myName;
      btnGirar.disabled = msg.spinning || !mine;
      setGirar(msg.spinning
        ? "Girando..."
        : (mine ? "Girar la ruleta" : "Esperando el turno de " + (msg.turn || "alguien")));
      if (mine && !msg.spinning && !announcedTurn) {
        announcedTurn = true;
        announce("Es tu turno. Tocá el botón Girar la ruleta.");
      } else if (!mine) {
        announcedTurn = false;
      }
    } else if (msg.event === "spin_start") {
      btnGirar.disabled = true;
      setGirar("Girando...");
      announce("Gira la ruleta de " + msg.player + "...");
      spinAnimation(msg.angle, () => {});
    } else if (msg.event === "say") {
      $("resultado").textContent = msg.text;
      announce(msg.text);
      playClip(msg.audio);
    }
  };
  ws.onclose = (ev) => {
    if (ev.code === 4004) announce("Esa mesa ya no existe. Creá una nueva.");
    else {
      announce("Se cortó la conexión. Reintentando...");
      setTimeout(() => connect(code), 2000);
    }
  };
}

btnGirar.addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "spin"}));
});
</script>
</body>
</html>
"""


@router.get("/amor-con-aroma-a-cafe", response_class=HTMLResponse)
@router.get("/amor-con-aroma-a-cafe/sala/{code}", response_class=HTMLResponse)
async def page(code: str = ""):
    return HTMLResponse(PAGE)
