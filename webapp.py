"""Amor con aroma a café: the shared web ruleta, v3.

A real-time multiplayer party room for Rocky and his friends: one opens a
room, shares the link, everyone plays in the browser. No Telegram, no login,
no ads. One tap to enter unlocks sound; from then on the server's voices (the
same catalog as the Telegram bot) narrate every event to ALL players at once.

v3 (Rocky, 2026-11-10): start screen (Jugar solo / Sala de juego 2-20),
joins announced by name, 60-second turn timer with spoken warnings, four
categories (Verdad o Reto, Trivia, Refranes, Países) with local
multiple-choice banks, points and a winner, auto-rematch with a rotating
starter, and in-room chat (text read aloud + recorded voice clips). Fully
screen-reader accessible: real labeled buttons, aria-live on every beat.
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
# Verdad o Reto: curated, harmless, doable dares and questions. "No locuras."
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
# Multiple-choice banks: (pregunta, [opciones...], índice correcto).
# Locales a propósito: sin LLM, sin costo, giro instantáneo.
# ---------------------------------------------------------------------------
TRIVIA_MC = [
    ("¿Cuál es el planeta más grande del sistema solar?", ["Júpiter", "Saturno", "Neptuno"], 0),
    ("¿En qué continente está Egipto?", ["África", "Asia", "Europa"], 0),
    ("¿Cuántos jugadores tiene un equipo de fútbol en la cancha?", ["Once", "Nueve", "Siete"], 0),
    ("¿Qué animal es conocido por cambiar de color?", ["El camaleón", "La iguana", "El sapo"], 0),
    ("¿Qué gas respiramos para vivir?", ["Oxígeno", "Carbono", "Hidrógeno"], 0),
    ("¿Cuál es el océano más grande del mundo?", ["El Pacífico", "El Atlántico", "El Índico"], 0),
    ("¿En qué país nació el tango?", ["Argentina", "Brasil", "España"], 0),
    ("¿Qué instrumento tiene teclas blancas y negras?", ["El piano", "El violín", "La trompeta"], 0),
    ("¿Cuántos colores tiene el arcoíris?", ["Siete", "Cinco", "Nueve"], 0),
    ("¿Qué planeta es conocido como el planeta rojo?", ["Marte", "Venus", "Mercurio"], 0),
    ("¿Qué ave no puede volar y vive en el hielo?", ["El pingüino", "La gaviota", "El cóndor"], 0),
    ("¿Cuál es el metal más liviano usado en aviones?", ["El aluminio", "El plomo", "El oro"], 0),
    ("¿Qué fruta es la estrella de la sidra?", ["La manzana", "La pera", "La uva"], 0),
    ("¿Cuánto es 7 por 8?", ["56", "48", "64"], 0),
    ("¿Qué órgano bombea la sangre?", ["El corazón", "El pulmón", "El hígado"], 0),
    ("¿En qué deporte se usa una raqueta y una pelotita amarilla?", ["Tenis", "Básquet", "Rugby"], 0),
    ("¿Qué país tiene forma de bota?", ["Italia", "Grecia", "Portugal"], 0),
    ("¿Cuál es el animal terrestre más rápido?", ["El guepardo", "El león", "El caballo"], 0),
    ("¿Qué se celebra el 25 de diciembre?", ["Navidad", "Año Nuevo", "Reyes"], 0),
    ("¿Qué ciencia estudia los dinosaurios?", ["La paleontología", "La botánica", "La química"], 0),
    ("¿Cuál es el río más largo de Sudamérica?", ["El Amazonas", "El Paraná", "El Orinoco"], 0),
    ("¿Qué astro nos da luz y calor todos los días?", ["El Sol", "La Luna", "Marte"], 0),
    ("¿Cuántas patas tiene una araña?", ["Ocho", "Seis", "Diez"], 0),
    ("¿Qué dulce se hace con leche y azúcar cocidas?", ["El dulce de leche", "El turrón", "El mazapán"], 0),
    ("¿Qué país ganó el Mundial de Fútbol 2022?", ["Argentina", "Francia", "Brasil"], 0),
    ("¿Qué aparato convierte el viento en electricidad?", ["El molino de viento", "La antena", "La turbina de vapor"], 0),
    ("¿Qué continente es el más poblado?", ["Asia", "África", "Europa"], 0),
    ("¿Qué bebida se hace con granos tostados y molidos?", ["El café", "El mate", "El té"], 0),
    ("¿Qué animal produce la miel?", ["La abeja", "La avispa", "La mariposa"], 0),
    ("¿Cuál es la montaña más alta del mundo?", ["El Everest", "El Aconcagua", "El Kilimanjaro"], 0),
]
REFRANES_MC = [
    ("¿Qué significa 'A caballo regalado no se le miran los dientes'?", ["A lo que te regalan, no le busques defectos", "Los caballos tienen buenos dientes", "No aceptes regalos de desconocidos"], 0),
    ("¿Qué significa 'Más vale pájaro en mano que cien volando'?", ["Mejor lo seguro, aunque sea poco", "Los pájaros son difíciles de cazar", "Hay que soltar lo que uno tiene"], 0),
    ("¿Qué significa 'Camarón que se duerme se lo lleva la corriente'?", ["El que no está atento, pierde", "Los camarones duermen mucho", "La corriente es peligrosa"], 0),
    ("¿Qué significa 'No hay mal que dure cien años'?", ["Todo lo malo termina algún día", "Los males duran muchísimo", "La gente vive cien años"], 0),
    ("¿Qué significa 'A falta de pan, buenas son tortas'?", ["Con lo que hay, uno se arregla", "Las tortas son mejores que el pan", "Hay que cocinar más tortas"], 0),
    ("¿Qué significa 'Perro que ladra no muerde'?", ["El que mucho amenaza, poco hace", "Los perros ladran de noche", "Hay que tenerle miedo a los perros"], 0),
    ("¿Qué significa 'Ojos que no ven, corazón que no siente'?", ["Lo que no sabés, no te duele", "Los ojos engañan siempre", "El corazón es frío"], 0),
    ("¿Qué significa 'Del dicho al hecho hay mucho trecho'?", ["Decir es más fácil que hacer", "Hay que caminar mucho", "Las palabras sobran"], 0),
    ("¿Qué significa 'Quien madruga, Dios lo ayuda'?", ["El esfuerzo temprano da frutos", "Dios se levanta temprano", "Dormir es malo"], 0),
    ("¿Qué significa 'Agua que no has de beber, déjala correr'?", ["No te metas en lo que no te incumbe", "Hay que tomar mucha agua", "El agua corre rápido"], 0),
    ("¿Qué significa 'En boca cerrada no entran moscas'?", ["A veces conviene callarse", "Las moscas molestan", "Hay que hablar despacio"], 0),
    ("¿Qué significa 'Cría cuervos y te sacarán los ojos'?", ["A veces te traiciona a quien ayudaste", "Los cuervos son malas mascotas", "Hay que cuidar los ojos"], 0),
    ("¿Qué significa 'A lo hecho, pecho'?", ["Hay que hacerse cargo de lo hecho", "Hay que pelear siempre", "Lo hecho no se puede nombrar"], 0),
    ("¿Qué significa 'Más sabe el diablo por viejo que por diablo'?", ["La experiencia vale más que la astucia", "El diablo es muy viejo", "Los viejos son diablos"], 0),
    ("¿Qué significa 'El que ríe último, ríe mejor'?", ["La victoria final es la que cuenta", "Reír es sano", "Hay que reírse despacio"], 0),
    ("¿Qué significa 'No por mucho madrugar amanece más temprano'?", ["Las cosas llevan su tiempo", "Hay que madrugar poco", "Amanece muy tarde"], 0),
    ("¿Qué significa 'Un clavo saca otro clavo'?", ["Lo nuevo ayuda a olvidar lo viejo", "Los clavos son útiles", "Hay que usar clavos grandes"], 0),
    ("¿Qué significa 'Piedra que rueda no cría moho'?", ["El que se mueve no se estanca", "Las piedras no tienen moho", "Rodar es peligroso"], 0),
    ("¿Qué significa 'Háblame del cuñado'?", ["No quiero hablar más de eso", "Mi cuñado es simpático", "Hablemos de familia"], 0),
    ("¿Qué significa 'Costó un ojo de la cara'?", ["Fue muy caro", "Se lastimó un ojo", "Fue gratis"], 0),
    ("¿Qué significa 'Estar en el horno'?", ["Estar en un problema", "Hace mucho calor", "Está cocinando"], 0),
    ("¿Qué significa 'No hay tu tía'?", ["No hay solución", "Tu tía no vino", "No hay problema"], 0),
    ("¿Qué significa 'Tirar los tejos'?", ["Coquetear con alguien", "Jugar a un deporte", "Tirar cosas viejas"], 0),
    ("¿Qué significa 'Ser pan comido'?", ["Ser muy fácil", "Ser rico de comer", "Ser poco trabajo"], 0),
    ("¿Qué significa 'Meter la pata'?", ["Equivocarse", "Caminar rápido", "Tropezar"], 0),
]
PAISES_MC = [
    ("¿Cuál es la capital de Argentina?", ["Buenos Aires", "Córdoba", "Rosario"], 0),
    ("¿Cuál es la capital de México?", ["Ciudad de México", "Guadalajara", "Monterrey"], 0),
    ("¿Cuál es la capital de Bolivia?", ["La Paz", "Sucre", "Santa Cruz"], 0),
    ("¿Cuál es la capital de Chile?", ["Santiago", "Valparaíso", "Concepción"], 0),
    ("¿Cuál es la capital de Colombia?", ["Bogotá", "Medellín", "Cali"], 0),
    ("¿Cuál es la capital de Perú?", ["Lima", "Cusco", "Arequipa"], 0),
    ("¿Cuál es la capital de Uruguay?", ["Montevideo", "Punta del Este", "Salto"], 0),
    ("¿Cuál es la capital de Paraguay?", ["Asunción", "Encarnación", "Ciudad del Este"], 0),
    ("¿Cuál es la capital de Brasil?", ["Brasilia", "Río de Janeiro", "San Pablo"], 0),
    ("¿Cuál es la capital de España?", ["Madrid", "Barcelona", "Sevilla"], 0),
    ("¿Cuál es la capital de Venezuela?", ["Caracas", "Maracaibo", "Valencia"], 0),
    ("¿Cuál es la capital de Ecuador?", ["Quito", "Guayaquil", "Cuenca"], 0),
    ("¿En qué continente está Japón?", ["Asia", "Oceanía", "Europa"], 0),
    ("¿En qué continente está Marruecos?", ["África", "Europa", "Asia"], 0),
    ("¿En qué continente está Australia?", ["Oceanía", "Asia", "África"], 0),
    ("¿Qué país es famoso por la Torre Eiffel?", ["Francia", "Italia", "Inglaterra"], 0),
    ("¿Qué país es famoso por el machu picchu?", ["Perú", "Bolivia", "Ecuador"], 0),
    ("¿Qué país es famoso por las pirámides de Giza?", ["Egipto", "México", "Sudán"], 0),
    ("¿Qué idioma se habla en Brasil?", ["Portugués", "Español", "Brasileño"], 0),
    ("¿Cuál es el país más grande de Sudamérica?", ["Brasil", "Argentina", "Perú"], 0),
    ("¿Qué país tiene el Canal de Panamá?", ["Panamá", "Costa Rica", "Colombia"], 0),
    ("¿La Patagonia es de Argentina y de qué otro país?", ["Chile", "Uruguay", "Bolivia"], 0),
    ("¿Qué país es famoso por el carnaval de Río?", ["Brasil", "Argentina", "Uruguay"], 0),
    ("¿Qué moneda se usa en la mayoría de Europa?", ["El euro", "El dólar", "La libra"], 0),
    ("¿Qué país tiene la estatua del Cristo Redentor?", ["Brasil", "Portugal", "Perú"], 0),
]

CATEGORIES = {
    "verdad_reto": "Verdad o Reto",
    "trivia": "Trivia",
    "refranes": "Refranes",
    "países": "Países",
}
MC_BANKS = {"trivia": TRIVIA_MC, "refranes": REFRANES_MC, "países": PAISES_MC}
MC_USED_KEYS = {"trivia": "used_trivia", "refranes": "used_refranes", "países": "used_paises"}

WIN_SCORE = 5
TURN_SECONDS = 60
REMATCH_SECONDS = 10
NARRATOR_VOICES = ["es-AR-ElenaNeural", "es-AR-TomasNeural", "es-UY-ValentinaNeural"]
MAX_PLAYERS = 20

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


def connected(room):
    return [p for p in room["players"] if p["ws"] is not None]


def current_player(room):
    active = [p for p in room["players"] if not p.get("gone")]
    if not active:
        return None
    return active[room["turn"] % len(active)]


def room_state(room) -> dict:
    current = current_player(room)
    return {
        "event": "state",
        "players": [
            {"id": p["id"], "name": p["name"], "score": room["scores"].get(p["id"], 0),
             "connected": p["ws"] is not None}
            for p in room["players"] if not p.get("gone")
        ],
        "turn": current["id"] if current else None,
        "turn_name": current["name"] if current else None,
        "phase": room["phase"],
        "spinning": room["spinning"],
        "capacity": room["capacity"],
        "match": room["match"],
        "goal": WIN_SCORE,
    }


async def tell(player, message: dict):
    if player["ws"] is None:
        return
    try:
        await player["ws"].send_text(json.dumps(message, ensure_ascii=False))
    except Exception:
        player["ws"] = None


async def broadcast(room, message: dict):
    for player in room["players"]:
        if not player.get("gone"):
            await tell(player, message)


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


def cache_audio(mp3: bytes) -> str:
    key = hashlib.sha256(mp3).hexdigest()[:24]
    audio_cache[key] = (mp3, time.time())
    for old_key, (_, ts) in list(audio_cache.items()):
        if time.time() - ts > 3600:
            audio_cache.pop(old_key, None)
    return key


async def say(room, text: str, voice=None, to=None):
    """Synthesize ONCE server-side and send to everyone (or one player)."""
    from app import synthesize  # local import: app.py mounts this router

    voice = voice or room.get("voice") or "es-AR-ElenaNeural"
    try:
        mp3 = await ogg_to_mp3(await synthesize(text, voice))
        url = f"/amor-con-aroma-a-cafe/audio/{cache_audio(mp3)}.mp3"
    except Exception:
        log.exception("Web sala: synthesis failed; sending text only")
        url = None
    message = {"event": "say", "text": text, "audio": url}
    if to is not None:
        await tell(to, message)
    else:
        await broadcast(room, message)


async def narrate(room, text: str, voice=None):
    """Serialized per room so announcements never talk over each other."""
    async with room["audio_lock"]:
        await say(room, text, voice=voice)


def pick_mc(room, category):
    bank = MC_BANKS[category]
    used = room[MC_USED_KEYS[category]]
    available = [item for item in bank if item[0] not in used]
    if not available:
        used.clear()
        available = list(bank)
    pick = random.choice(available)
    used.add(pick[0])
    return pick


def cancel_timer(room):
    task = room.get("timer_task")
    if task and not task.done():
        task.cancel()
    room["timer_task"] = None


async def turn_clock(room, player_id):
    """60s per turn: spoken warnings at 30s and 10s, then the turn passes."""
    try:
        await asyncio.sleep(TURN_SECONDS - 30)
        player = next((p for p in room["players"] if p["id"] == player_id), None)
        if player:
            await narrate(room, f"A {player['name']} le quedan 30 segundos.")
        await asyncio.sleep(20)
        await narrate(room, "¡10 segundos!")
        await asyncio.sleep(10)
        current = current_player(room)
        if current and current["id"] == player_id and room["phase"] not in ("lobby", "gameover"):
            room["turn"] += 1
            nxt = current_player(room)
            await narrate(
                room,
                f"Se acabó el tiempo. Ahora le toca a {nxt['name']}." if nxt else "Se acabó el tiempo.",
            )
            await begin_turn(room)
    except asyncio.CancelledError:
        pass


async def begin_turn(room):
    """Announce the turn and arm the clock; caller advances room['turn']."""
    cancel_timer(room)
    room["spinning"] = False
    room["question"] = None
    player = current_player(room)
    if player is None:
        return
    room["phase"] = "category"
    await broadcast(room, room_state(room))
    await tell(player, {"event": "choose_category", "categories": CATEGORIES})
    room["timer_task"] = asyncio.create_task(turn_clock(room, player["id"]))


async def start_match(room):
    room["scores"] = {p["id"]: 0 for p in room["players"] if not p.get("gone")}
    room["turn"] = room["starter"]
    player = current_player(room)
    if player is None:
        return
    await narrate(room, f"¡Arranca la partida {room['match']}! El primero en llegar a "
                        f"{WIN_SCORE} puntos gana. Empieza {player['name']}.")
    await begin_turn(room)


async def end_turn(room):
    """Resolve the turn: check the winner, else pass to the next player."""
    cancel_timer(room)
    room["question"] = None
    room["spinning"] = False
    winner = next(
        (p for p in room["players"] if not p.get("gone") and room["scores"].get(p["id"], 0) >= WIN_SCORE),
        None,
    )
    if winner is not None:
        await game_over(room, winner)
        return
    room["turn"] += 1
    await begin_turn(room)


async def game_over(room, winner):
    room["phase"] = "gameover"
    await narrate(room, f"¡Ganó {winner['name']} con {room['scores'][winner['id']]} puntos! "
                        f"En {REMATCH_SECONDS} segundos arranca una partida nueva.")
    await broadcast(room, room_state(room))
    await asyncio.sleep(REMATCH_SECONDS)
    active = [p for p in room["players"] if not p.get("gone")]
    if not active:
        return
    # The starter rotates: the winner never starts twice in a row by default.
    room["starter"] = (room["starter"] + 1) % len(active)
    room["match"] += 1
    await start_match(room)


async def do_spin(room, player):
    """Verdad o Reto: the wheel spins, then the card is read aloud."""
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
    await broadcast(room, {
        "event": "spin_start", "player": player["name"], "angle": angle,
        "segment": segment,
        "colors": [SEGMENT_COLORS[s] for s in SEGMENTS],
        "labels": [SEGMENT_LABELS[s] for s in SEGMENTS],
    })
    label = SEGMENT_LABELS[segment]
    announce = (
        f"¡Giramos la ruleta! Gira, gira... ¡paró! ¡{player['name']}, te salió {label}! "
        f"{label} para {player['name']}: {pick}"
    )
    await asyncio.sleep(3.5)  # the wheel spins ~4s; the voice lands as it stops
    await narrate(room, announce)
    room["phase"] = "verdad_reto"
    await tell(player, {"event": "await_done", "card": pick, "label": label})
    await broadcast(room, room_state(room))


async def ask_question(room, player, category):
    pick = pick_mc(room, category)
    question, options, correct = pick
    room["question"] = {"category": category, "q": question, "options": options, "correct": correct}
    room["phase"] = "question"
    letters = ["A", "B", "C"]
    spoken = question + " " + " ".join(f"Opción {letters[i]}: {opt}." for i, opt in enumerate(options))
    await narrate(room, f"{CATEGORIES[category]} para {player['name']}. {spoken}",
                  voice=room["question_voice"])
    await broadcast(room, {
        "event": "question", "category": category, "q": question,
        "options": options, "player": player["id"],
    })
    await broadcast(room, room_state(room))


async def resolve_answer(room, player, idx):
    question = room.get("question")
    if not question:
        return
    correct = idx == question["correct"]
    if correct:
        room["scores"][player["id"]] = room["scores"].get(player["id"], 0) + 1
        await narrate(room, f"¡Correcto! Un punto para {player['name']}. "
                            f"Lleva {room['scores'][player['id']]}.")
    else:
        right = question["options"][question["correct"]]
        await narrate(room, f"No, {player['name']}. La correcta era: {right}.")
    await end_turn(room)


async def complete_verdad_reto(room, player, done):
    if done:
        room["scores"][player["id"]] = room["scores"].get(player["id"], 0) + 1
        await narrate(room, f"¡Muy bien, {player['name']}! Un punto. Lleva {room['scores'][player['id']]}.")
    else:
        await narrate(room, f"{player['name']} pasa. Sin punto esta vez.")
    await end_turn(room)

# ---------------------------------------------------------------------------
# The sala socket.
# ---------------------------------------------------------------------------
@router.websocket("/amor-con-aroma-a-cafe/ws/{code}")
async def sala_ws(websocket: WebSocket, code: str, name: str = ""):
    code = code.upper()
    room = rooms.get(code)
    if room is None:
        await websocket.close(code=4004)
        return
    name = (name or "").strip()[:24]
    await websocket.accept()

    # A comeback with the same name re-takes its seat; nobody loses points.
    seat = next(
        (p for p in room["players"] if not p.get("gone") and p["ws"] is None and p["name"] == name),
        None,
    ) if name else None
    active = [p for p in room["players"] if not p.get("gone")]
    if seat is None and room["capacity"] and len(active) >= room["capacity"]:
        await websocket.send_text(json.dumps(
            {"event": "say", "text": "La sala está llena.", "audio": None}, ensure_ascii=False))
        await websocket.close(code=4009)
        return
    if seat is not None:
        seat["ws"] = websocket
        player = seat
    else:
        if not name:
            name = f"Jugador {len(active) + 1}"
        player = {"id": room["next_id"], "name": name, "ws": websocket}
        room["next_id"] += 1
        room["players"].append(player)
        room["scores"][player["id"]] = 0
    log.info("Web sala %s: %s joined (%s players)", code, player["name"], len(active) + (seat is None))
    await tell(player, {"event": "welcome", "name": player["name"], "id": player["id"],
                        "code": code, "capacity": room["capacity"], "phase": room["phase"]})
    count = len([p for p in room["players"] if not p.get("gone")])
    if seat is not None:
        await narrate(room, f"¡{player['name']} volvió a la mesa!")
    elif count == 1:
        await say(room,
                  f"¡Listo, {player['name']}! Ya estás en la mesa. No hace falta escribir nada. "
                  "Pasales el link a tus amigos con el botón Copiar el link.",
                  to=player)
        await narrate(room, f"Se unió {player['name']}. Ahora son {count} en la sala.")
    else:
        await narrate(room, f"Se unió {player['name']}. Ahora son {count} en la sala.")
    await broadcast(room, room_state(room))
    # Solo starts at once; a sala starts when full or when the host taps Empezar.
    if room["phase"] == "lobby" and room["mode"] == "solo":
        await start_match(room)
    elif room["phase"] == "lobby" and room["capacity"] and count >= room["capacity"]:
        await start_match(room)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            action = message.get("action")
            player["ws"] = websocket
            current = current_player(room)

            if action == "start" and room["phase"] == "lobby" and player == room["players"][0]:
                await start_match(room)
            elif action == "spin":
                if room["spinning"] or room["phase"] != "verdad_reto_ready":
                    continue
                if current is not player:
                    await tell(player, {"event": "say", "text": "Todavía no es tu turno.", "audio": None})
                    continue
                asyncio.create_task(do_spin(room, player))
            elif action == "category":
                if room["phase"] != "category" or current is not player:
                    continue
                cat = message.get("category")
                if cat == "verdad_reto":
                    room["phase"] = "verdad_reto_ready"
                    await narrate(room, f"{player['name']} eligió Verdad o Reto. ¡Que gire la ruleta!")
                    await broadcast(room, room_state(room))
                elif cat in MC_BANKS:
                    await ask_question(room, player, cat)
            elif action == "answer":
                if room["phase"] == "question" and current is player and room.get("question"):
                    await resolve_answer(room, player, int(message.get("idx", -1)))
            elif action == "listo":
                if room["phase"] == "verdad_reto" and current is player:
                    await complete_verdad_reto(room, player, done=True)
            elif action == "pasar":
                if room["phase"] == "verdad_reto" and current is player:
                    await complete_verdad_reto(room, player, done=False)
            elif action == "chat":
                await handle_chat(room, player, message)
            elif action == "rename":
                new_name = (message.get("name") or "").strip()[:24]
                if new_name:
                    player["name"] = new_name
                    await broadcast(room, room_state(room))
    except WebSocketDisconnect:
        pass
    finally:
        if player["ws"] is websocket:
            player["ws"] = None
        log.info("Web sala %s: %s disconnected", code, player["name"])
        remaining = [p for p in room["players"] if not p.get("gone") and p["ws"] is not None]
        if not remaining:
            cancel_timer(room)
            rooms.pop(code, None)
        elif room["phase"] not in ("lobby",):
            await narrate(room, f"{player['name']} se fue de la mesa.")
            current = current_player(room)
            if current is player:
                room["turn"] += 1
                await begin_turn(room)
            else:
                await broadcast(room, room_state(room))


async def handle_chat(room, player, message):
    text = (message.get("text") or "").strip()[:300]
    if not text:
        return
    to_id = message.get("to", "all")
    target = None
    if to_id != "all":
        target = next((p for p in room["players"] if p["id"] == to_id and not p.get("gone")), None)
        if target is None:
            return
    spoken = (f"{player['name']} le dice a {target['name']}: {text}" if target
              else f"{player['name']} dice: {text}")
    from app import synthesize

    try:
        mp3 = await ogg_to_mp3(await synthesize(spoken, room.get("voice") or "es-AR-ElenaNeural"))
        url = f"/amor-con-aroma-a-cafe/audio/{cache_audio(mp3)}.mp3"
    except Exception:
        url = None
    payload = {"event": "chat", "from_id": player["id"], "from_name": player["name"],
               "to": to_id, "text": text, "audio": url}
    if target is not None:
        await tell(target, payload)
        await tell(player, {**payload, "echo": True})
    else:
        await broadcast(room, payload)


from fastapi import Request


@router.post("/amor-con-aroma-a-cafe/api/voz/{code}")
async def voice_clip(code: str, request: Request, to: str = "all", sender: int = -1):
    """A recorded voice clip, converted to mp3 and relayed to the recipient(s)."""
    room = rooms.get(code.upper())
    if room is None:
        return Response(status_code=404)
    sender_p = next((p for p in room["players"] if p["id"] == sender and not p.get("gone")), None)
    if sender_p is None:
        return Response(status_code=403)
    body = await request.body()
    if not body or len(body) > 3_000_000:
        return Response(status_code=400)
    try:
        mp3 = await ogg_to_mp3(body)  # ffmpeg reads webm/opus from the same pipe
    except Exception:
        log.exception("Web sala: voice clip conversion failed")
        return Response(status_code=415)
    url = f"/amor-con-aroma-a-cafe/audio/{cache_audio(mp3)}.mp3"
    payload = {"event": "clip", "from_id": sender_p["id"], "from_name": sender_p["name"],
               "to": to, "url": url}
    if to == "all":
        await broadcast(room, payload)
    else:
        try:
            target_id = int(to)
        except ValueError:
            return Response(status_code=400)
        target = next((p for p in room["players"] if p["id"] == target_id and not p.get("gone")), None)
        if target is None:
            return Response(status_code=404)
        await tell(target, payload)
        await tell(sender_p, {**payload, "echo": True})
    return {"ok": True}


@router.post("/amor-con-aroma-a-cafe/api/salas")
async def crear_sala(request: Request):
    mode = "sala"
    capacity = None
    try:
        data = await request.json()
        mode = "solo" if data.get("mode") == "solo" else "sala"
        capacity = int(data.get("capacity") or 0) or None
    except Exception:
        pass
    if mode == "solo":
        capacity = 1
    elif capacity is not None:
        capacity = max(2, min(MAX_PLAYERS, capacity))
    code = new_room_code()
    voice = random.choice(NARRATOR_VOICES)
    rooms[code] = {
        "players": [],
        "next_id": 1,
        "mode": mode,
        "capacity": capacity,
        "starter": 0,
        "turn": 0,
        "match": 1,
        "phase": "lobby",
        "spinning": False,
        "question": None,
        "scores": {},
        "timer_task": None,
        "audio_lock": asyncio.Lock(),
        "used_retos": set(),
        "used_verdades": set(),
        "used_trivia": set(),
        "used_refranes": set(),
        "used_paises": set(),
        "voice": voice,
        "question_voice": random.choice([v for v in NARRATOR_VOICES if v != voice]),
    }
    return {"code": code}



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
    min-width: 14rem; min-height: 3.5rem; display: block;
  }
  button.secondary { background: #3949ab; }
  button.chatbtn { font-size: 1.1rem; min-width: 10rem; min-height: 2.8rem; padding: 0.6rem 1rem; }
  button:disabled { background: #555; color: #aaa; }
  button:focus-visible, input:focus-visible, select:focus-visible {
    outline: 4px solid #fdd835; outline-offset: 2px;
  }
  #wheel { width: min(80vw, 320px); height: min(80vw, 320px); margin: 1rem auto; }
  #estado { font-size: 1.4rem; min-height: 2.2rem; margin: 0.5rem; color: #fdd835; }
  #temporizador { font-size: 1.3rem; color: #ffab91; min-height: 1.8rem; }
  #jugadores { font-size: 1.1rem; color: #b2dfdb; margin: 0.5rem; list-style: none; padding: 0; }
  #jugadores li { margin: 0.2rem; }
  #compartir {
    background: #101418; border: 2px dashed #8e24aa; border-radius: 0.8rem;
    padding: 0.8rem; margin: 0.5rem; font-size: 1.1rem; word-break: break-all;
    max-width: 34rem;
  }
  #pregunta { max-width: 34rem; }
  #pregunta-texto { font-size: 1.3rem; color: #ffe082; }
  #chat { max-width: 34rem; margin-top: 1rem; border-top: 2px solid #333; padding-top: 0.8rem; }
  #chat-log { list-style: none; padding: 0; text-align: left; font-size: 1rem; color: #cfd8dc; }
  #chat-log li { margin: 0.3rem 0; }
  #chat-texto { font-size: 1.2rem; padding: 0.6rem; border-radius: 0.6rem; width: 100%; }
  #nombre-input { font-size: 1.3rem; padding: 0.7rem; border-radius: 0.6rem; width: 16rem; }
  #cupos-select { font-size: 1.4rem; padding: 0.7rem; border-radius: 0.6rem; min-width: 8rem; }
  #chat-para { font-size: 1.1rem; padding: 0.5rem; border-radius: 0.6rem; }
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
      Juego de la ruleta con amigos: Verdad o Reto, Trivia, Refranes y Países.
      Todo se hace con botones y cada jugada se anuncia en voz alta.
    </p>
    <p id="estado" role="status" tabindex="-1">Bienvenido a la mesa.</p>

    <section id="pantalla-inicio" aria-label="Pantalla de inicio">
      <button id="btn-solo" aria-label="Jugar solo, sin amigos">Jugar solo</button>
      <button id="btn-sala" class="secondary" aria-label="Sala de juego, para jugar con amigos">Sala de juego (con amigos)</button>
    </section>

    <section id="pantalla-cupos" hidden aria-label="Cuántos jugadores">
      <label for="cupos-select" id="cupos-label">¿Cuántos jugadores son? De 2 a 20.</label><br>
      <select id="cupos-select" aria-labelledby="cupos-label"></select><br>
      <button id="btn-crear" aria-label="Crear la sala de juego">Crear la sala</button>
      <button id="btn-volver" class="secondary" aria-label="Volver a la pantalla de inicio">Volver</button>
    </section>

    <section id="pantalla-unirse" hidden aria-label="Unirse a la sala">
      <label for="nombre-input" id="nombre-label">Tu nombre (si no escribís nada, sos Jugador N):</label><br>
      <input id="nombre-input" type="text" autocomplete="off" aria-labelledby="nombre-label"><br>
      <button id="btn-entrar" aria-label="Entrar a jugar">Entrar a jugar</button>
    </section>

    <section id="sala" hidden aria-label="Sala de juego">
      <div id="compartir" hidden>
        Pasá este link a tus amigos:<br><strong id="link"></strong><br>
        <button id="btn-copiar" class="secondary" aria-label="Copiar el link para invitar a tus amigos"><span aria-hidden="true">📤 </span>Copiar el link</button>
      </div>
      <button id="btn-empezar" hidden aria-label="Empezar la partida ya">Empezar la partida</button>
      <p id="temporizador" role="timer" aria-hidden="true"></p>
      <canvas id="wheel" width="640" height="640" aria-hidden="true"></canvas>
      <ul id="jugadores" role="status" aria-label="Jugadores en la mesa"></ul>

      <div id="categorias" hidden role="group" aria-label="Elegir categoría">
        <button data-cat="verdad_reto" aria-label="Categoría Verdad o Reto">Verdad o Reto</button>
        <button data-cat="trivia" class="secondary" aria-label="Categoría Trivia">Trivia</button>
        <button data-cat="refranes" class="secondary" aria-label="Categoría Refranes">Refranes</button>
        <button data-cat="países" class="secondary" aria-label="Categoría Países">Países</button>
      </div>

      <button id="btn-girar" hidden disabled><span aria-hidden="true">🎡 </span><span id="btn-girar-text">Girar la ruleta</span></button>

      <div id="pregunta" hidden>
        <p id="pregunta-texto" role="status"></p>
        <button class="opcion secondary" data-idx="0"></button>
        <button class="opcion secondary" data-idx="1"></button>
        <button class="opcion secondary" data-idx="2"></button>
      </div>

      <div id="reto-verdad" hidden>
        <p id="carta-texto" role="status"></p>
        <button id="btn-listo" aria-label="Listo, ya lo hice">¡Listo, ya lo hice!</button>
        <button id="btn-pasar" class="secondary" aria-label="Pasar, sin punto">Paso</button>
      </div>

      <div id="chat">
        <h2 id="chat-titulo">Chat de la sala</h2>
        <ul id="chat-log" aria-live="polite" aria-label="Mensajes del chat"></ul>
        <label for="chat-para" class="visually-hidden">Destinatario del mensaje</label>
        <select id="chat-para" aria-label="Destinatario del mensaje"></select>
        <label for="chat-texto" class="visually-hidden">Escribí tu mensaje</label>
        <input id="chat-texto" type="text" autocomplete="off" placeholder="Escribí un mensaje (opcional)">
        <button id="btn-chat" class="chatbtn" aria-label="Mandar el mensaje de texto">Mandar mensaje</button>
        <button id="btn-grabar" class="chatbtn secondary" aria-label="Grabar una nota de voz">Grabar nota de voz</button>
      </div>
    </section>

    <div id="voz" class="visually-hidden" aria-live="assertive"></div>
    <audio id="player"></audio>
  </main>
<script>
"use strict";
const $ = (id) => document.getElementById(id);
const estado = $("estado"), voz = $("voz"), player = $("player");
let ws = null, audioUnlocked = false;
let myId = null, myName = localStorage.getItem("cafe_nombre") || "";
let salaCode = null, lastState = null, lastQuestion = null;
let turnStartedAt = 0, timerInterval = null;

// --- One queue for every sound: nothing talks over anything else. ---
const audioQueue = [];
let playing = false;
function queueAudio(url) {
  if (!url) return;
  audioQueue.push(url);
  pumpAudio();
}
function pumpAudio() {
  if (playing || !audioQueue.length || !audioUnlocked) return;
  playing = true;
  player.src = audioQueue.shift();
  player.onended = () => { playing = false; pumpAudio(); };
  player.onerror = () => { playing = false; pumpAudio(); };
  player.play().catch(() => { playing = false; pumpAudio(); });
}

function announce(text) {
  estado.textContent = text;
  voz.textContent = "";
  setTimeout(() => { voz.textContent = text; }, 60);
}

function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  player.play().then(() => { player.pause(); pumpAudio(); }).catch(() => {});
}

function show(id) {
  for (const s of ["pantalla-inicio", "pantalla-cupos", "pantalla-unirse", "sala"]) {
    $(s).hidden = (s !== id);
  }
  estado.focus();
}

// --- La ruleta (canvas decorativo; el control real es el botón) ---
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
  ctx.beginPath(); ctx.moveTo(c - 18, 8); ctx.lineTo(c + 18, 8); ctx.lineTo(c, 44);
  ctx.closePath(); ctx.fillStyle = "#fdd835"; ctx.fill();
}
drawWheel(0);
let animId = null;
function spinAnimation(finalAngle) {
  const start = rotation, giros = 5 * 2 * Math.PI;
  const target = giros + ((360 - finalAngle) * Math.PI) / 180;
  const dur = 3600, t0 = performance.now();
  cancelAnimationFrame(animId);
  function frame(t) {
    const k = Math.min(1, (t - t0) / dur);
    const ease = 1 - Math.pow(1 - k, 3);
    rotation = start + (target - start) * ease;
    drawWheel(rotation % (2 * Math.PI));
    if (k < 1) animId = requestAnimationFrame(frame);
  }
  animId = requestAnimationFrame(frame);
}

// --- El reloj del turno (visible; los avisos hablados los manda el server) ---
function startClock() {
  turnStartedAt = Date.now();
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    const left = Math.max(0, 60 - Math.floor((Date.now() - turnStartedAt) / 1000));
    $("temporizador").textContent = left > 0 ? ("Quedan " + left + " segundos") : "";
  }, 1000);
}

// --- Chat ---
function addChatLine(text) {
  const li = document.createElement("li");
  li.textContent = text;
  $("chat-log").appendChild(li);
  while ($("chat-log").children.length > 30) $("chat-log").removeChild($("chat-log").firstChild);
}
function refreshChatTargets() {
  const sel = $("chat-para");
  const current = sel.value || "all";
  sel.innerHTML = "";
  const all = document.createElement("option");
  all.value = "all"; all.textContent = "Para todos";
  sel.appendChild(all);
  if (lastState) {
    for (const p of lastState.players) {
      if (p.id === myId) continue;
      const opt = document.createElement("option");
      opt.value = String(p.id); opt.textContent = "Para " + p.name;
      sel.appendChild(opt);
    }
  }
  sel.value = current;
}

// --- Pantallas de entrada ---
const parts = location.pathname.split("/");
const inviteCode = parts[2] === "sala" ? (parts[3] || "").toUpperCase() : null;

(function fillCupos() {
  const sel = $("cupos-select");
  for (let n = 2; n <= 20; n++) {
    const opt = document.createElement("option");
    opt.value = String(n); opt.textContent = String(n);
    sel.appendChild(opt);
  }
})();

if (inviteCode) {
  $("nombre-input").value = myName;
  show("pantalla-unirse");
  announce("Te invitaron a una mesa. Si querés, escribí tu nombre; si no, sos Jugador N. Tocá Entrar a jugar.");
} else {
  show("pantalla-inicio");
  announce("Bienvenido. Tocá Jugar solo o Sala de juego para jugar con amigos.");
}

$("btn-solo").addEventListener("click", async () => {
  unlockAudio();
  announce("Creando tu mesa...");
  const res = await fetch("/amor-con-aroma-a-cafe/api/salas", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({mode: "solo"}),
  });
  const data = await res.json();
  history.pushState(null, "", "/amor-con-aroma-a-cafe/sala/" + data.code);
  enterSala(data.code, myName);
});

$("btn-sala").addEventListener("click", () => {
  unlockAudio();
  show("pantalla-cupos");
  announce("¿Cuántos jugadores son? Elegí un número y tocá Crear la sala.");
});

$("btn-volver").addEventListener("click", () => {
  show("pantalla-inicio");
  announce("Tocá Jugar solo o Sala de juego.");
});

$("btn-crear").addEventListener("click", async () => {
  unlockAudio();
  announce("Creando la sala...");
  const res = await fetch("/amor-con-aroma-a-cafe/api/salas", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({mode: "sala", capacity: parseInt($("cupos-select").value, 10)}),
  });
  const data = await res.json();
  history.pushState(null, "", "/amor-con-aroma-a-cafe/sala/" + data.code);
  enterSala(data.code, myName);
});

$("btn-entrar").addEventListener("click", () => {
  unlockAudio();
  const typed = $("nombre-input").value.trim();
  if (typed) { myName = typed; localStorage.setItem("cafe_nombre", myName); }
  enterSala(inviteCode, myName);
});

$("btn-copiar").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("link").textContent);
    announce("Link copiado. Pegalo en un mensaje para invitar a tus amigos.");
  } catch (err) {
    announce("No pude copiarlo. El link está escrito arriba.");
  }
});

$("btn-empezar").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "start"}));
});

function enterSala(code, name) {
  salaCode = code;
  show("sala");
  $("compartir").hidden = false;
  $("link").textContent = location.origin + "/amor-con-aroma-a-cafe/sala/" + code;
  connect(code, name);
}

function connect(code, name) {
  ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://")
    + location.host + "/amor-con-aroma-a-cafe/ws/" + code
    + (name ? "?name=" + encodeURIComponent(name) : ""));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.event === "welcome") {
      myId = msg.id; myName = msg.name;
      localStorage.setItem("cafe_nombre", myName);
      const codeSpelled = code.split("").join(" ");
      announce("Estás en la mesa " + codeSpelled + " como " + myName + ".");
    } else if (msg.event === "state") {
      onState(msg);
    } else if (msg.event === "choose_category") {
      announce("Es tu turno. Elegí una categoría: Verdad o Reto, Trivia, Refranes o Países.");
    } else if (msg.event === "spin_start") {
      announce("Gira la ruleta de " + msg.player + "...");
      spinAnimation(msg.angle);
    } else if (msg.event === "await_done") {
      $("carta-texto").textContent = msg.label + ": " + msg.card;
    } else if (msg.event === "question") {
      onQuestion(msg);
    } else if (msg.event === "say") {
      announce(msg.text);
      queueAudio(msg.audio);
    } else if (msg.event === "chat") {
      const who = msg.to === "all" ? "" : " (privado)";
      addChatLine(msg.from_name + who + ": " + msg.text);
      if (!msg.echo) queueAudio(msg.audio);
    } else if (msg.event === "clip") {
      addChatLine("Nota de voz de " + msg.from_name + (msg.to === "all" ? "" : " (privada)"));
      if (!msg.echo) queueAudio(msg.url);
    }
  };
  ws.onclose = (ev) => {
    if (ev.code === 4004) announce("Esa mesa ya no existe. Creá una nueva.");
    else if (ev.code === 4009) announce("La sala está llena. Pediles que armen otra.");
    else {
      announce("Se cortó la conexión. Reintentando...");
      setTimeout(() => connect(code, myName), 2000);
    }
  };
}

function onState(msg) {
  const turnChanged = !lastState || lastState.turn !== msg.turn || lastState.phase !== msg.phase;
  lastState = msg;
  refreshChatTargets();
  const ul = $("jugadores");
  ul.innerHTML = "";
  for (const p of msg.players) {
    const li = document.createElement("li");
    li.textContent = p.name + ": " + p.score + " puntos" + (p.connected ? "" : " (se fue)");
    ul.appendChild(li);
  }
  const mine = msg.turn === myId;
  $("categorias").hidden = !(mine && msg.phase === "category");
  const vr = msg.phase === "verdad_reto_ready";
  $("btn-girar").hidden = !vr;
  $("btn-girar").disabled = !mine || msg.spinning;
  $("btn-girar-text").textContent = msg.spinning ? "Girando..." : (mine ? "Girar la ruleta" : "Esperando a " + (msg.turn_name || "alguien"));
  $("reto-verdad").hidden = !(mine && msg.phase === "verdad_reto");
  if (!(msg.phase === "question")) { $("pregunta").hidden = true; }
  $("btn-empezar").hidden = !(msg.phase === "lobby" && msg.players.length && msg.players[0].id === myId && msg.capacity !== 1);
  if (turnChanged && msg.phase !== "lobby" && msg.phase !== "gameover") startClock();
  if (msg.phase === "gameover") { clearInterval(timerInterval); $("temporizador").textContent = ""; }
  if (mine && turnChanged && msg.phase === "verdad_reto_ready") {
    announce("Te toca. Tocá el botón Girar la ruleta.");
  }
}

function onQuestion(msg) {
  lastQuestion = msg;
  $("pregunta").hidden = false;
  const letters = ["A", "B", "C"];
  $("pregunta-texto").textContent = msg.q;
  const mine = msg.player === myId;
  document.querySelectorAll("#pregunta .opcion").forEach((btn, i) => {
    btn.textContent = "Opción " + letters[i] + ": " + msg.options[i];
    btn.setAttribute("aria-label", "Opción " + letters[i] + ": " + msg.options[i]);
    btn.disabled = !mine;
  });
  if (!mine) announce(msg.player === myId ? msg.q : "Pregunta para " + (lastState ? lastState.turn_name : "otro jugador") + ": " + msg.q);
}

document.querySelectorAll("#categorias button").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "category", category: btn.dataset.cat}));
    $("categorias").hidden = true;
  });
});

$("btn-girar").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "spin"}));
});

document.querySelectorAll("#pregunta .opcion").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "answer", idx: parseInt(btn.dataset.idx, 10)}));
    $("pregunta").hidden = true;
  });
});

$("btn-listo").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "listo"}));
});
$("btn-pasar").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "pasar"}));
});

// --- Chat: texto ---
$("btn-chat").addEventListener("click", () => {
  const text = $("chat-texto").value.trim();
  if (!text || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({action: "chat", to: $("chat-para").value === "all" ? "all" : parseInt($("chat-para").value, 10), text: text}));
  $("chat-texto").value = "";
  announce("Mensaje mandado.");
});

// --- Chat: nota de voz ---
let recorder = null, chunks = [];
$("btn-grabar").addEventListener("click", async () => {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      $("btn-grabar").textContent = "Grabar nota de voz";
      $("btn-grabar").setAttribute("aria-label", "Grabar una nota de voz");
      const blob = new Blob(chunks, {type: recorder.mimeType || "audio/webm"});
      const to = $("chat-para").value;
      announce("Mandando tu nota de voz...");
      try {
        const res = await fetch("/amor-con-aroma-a-cafe/api/voz/" + salaCode + "?to=" + encodeURIComponent(to) + "&sender=" + myId, {method: "POST", body: blob});
        announce(res.ok ? "Nota de voz mandada." : "No pude mandar la nota. Probá de nuevo.");
      } catch (err) {
        announce("No pude mandar la nota. Probá de nuevo.");
      }
    };
    recorder.start();
    $("btn-grabar").textContent = "Parar y mandar";
    $("btn-grabar").setAttribute("aria-label", "Parar la grabación y mandar la nota de voz");
    announce("Grabando. Tocá Parar y mandar cuando termines.");
  } catch (err) {
    announce("No tengo permiso para el micrófono. Podés escribir el mensaje.");
  }
});
</script>
</body>
</html>
"""


@router.get("/amor-con-aroma-a-cafe", response_class=HTMLResponse)
@router.get("/amor-con-aroma-a-cafe/sala/{code}", response_class=HTMLResponse)
async def page(code: str = ""):
    return HTMLResponse(PAGE)
