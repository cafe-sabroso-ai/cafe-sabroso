"""Café Sabroso on the WhatsApp Business Platform (Cloud API).

Shares the full Café Sabroso pipeline with the Telegram bot in app.py:
the 38 voices, individual and group modes (dúo, trío, cuarteto, historia),
music search, live weather and sports context, edge-tts synthesis, local
Whisper transcription and the OpenRouter -> Pollinations model fallback.
Only the transport (Meta Graph API webhooks and messages) and the
text-driven command interface live here, because WhatsApp has no inline
keyboards: voice picks happen with /voz N.

Runs standalone (uvicorn whatsapp_app:app) or mounted inside app.py at
/whatsapp when WHATSAPP_ACCESS_TOKEN is configured.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import re
import sqlite3
import tempfile
import urllib.parse as urllib_parse
from collections import deque
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import PlainTextResponse

import app as cafe

logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("cafe-sabroso-whatsapp")

VOICES = cafe.VOICES
VOICE_ITEMS = list(VOICES.items())
DEFAULT_VOICE = cafe.DEFAULT_VOICE
GROUP_MODE_SIZES = cafe.GROUP_MODE_SIZES
GROUP_MODE_LABELS = cafe.GROUP_MODE_LABELS

# Cloud API audio messages accept up to 16 MB; keep headroom.
WHATSAPP_AUDIO_LIMIT = 15 * 1024 * 1024


def env(name, default=None):
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing environment variable {name}")
    return value


def graph_api():
    return f"https://graph.facebook.com/{os.getenv('WHATSAPP_GRAPH_VERSION', 'v27.0')}"


router = APIRouter()
group_selection = {}
processed_ids = set()
processed_order = deque()
http = httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=20.0))
whisper_model = None
whisper_lock = asyncio.Lock()

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/cafe_sabroso.db")
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(DATABASE_PATH) as database:
    database.execute(
        "CREATE TABLE IF NOT EXISTS preferred_names_wa "
        "(user_key TEXT PRIMARY KEY, name TEXT NOT NULL)"
    )


def get_preferred_name(user_key: str):
    with sqlite3.connect(DATABASE_PATH) as database:
        row = database.execute(
            "SELECT name FROM preferred_names_wa WHERE user_key = ?", (user_key,)
        ).fetchone()
    return row[0] if row else None


def save_preferred_name(user_key: str, name: str):
    with sqlite3.connect(DATABASE_PATH) as database:
        database.execute(
            "INSERT INTO preferred_names_wa (user_key, name) VALUES (?, ?) "
            "ON CONFLICT(user_key) DO UPDATE SET name = excluded.name",
            (user_key, name),
        )


def auth_headers():
    return {"Authorization": f"Bearer {env('WHATSAPP_ACCESS_TOKEN')}"}


def recipient_fields(user: dict):
    if user.get("bsuid"):
        return {"recipient": user["bsuid"]}
    return {"to": user["wa_id"]}


async def whatsapp_send(user: dict, payload: dict):
    body = {"messaging_product": "whatsapp", **recipient_fields(user), **payload}
    response = await http.post(
        f"{graph_api()}/{env('WHATSAPP_PHONE_NUMBER_ID')}/messages",
        headers=auth_headers(),
        json=body,
    )
    if response.status_code >= 400:
        log.error("WhatsApp send failed: %s %s", response.status_code, response.text[:500])
    response.raise_for_status()
    return response.json()


async def mark_read(message_id: str):
    """Best-effort read receipt; never blocks the reply path."""
    if not message_id:
        return
    try:
        await http.post(
            f"{graph_api()}/{env('WHATSAPP_PHONE_NUMBER_ID')}/messages",
            headers=auth_headers(),
            json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            },
        )
    except Exception:
        log.warning("Could not mark message %s as read", message_id)


async def send_text(user: dict, text: str):
    chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)] or [""]
    for chunk in chunks:
        await whatsapp_send(user, {"type": "text", "text": {"body": chunk, "preview_url": False}})


async def upload_media(filename: str, payload: bytes, mime: str) -> str:
    upload = await http.post(
        f"{graph_api()}/{env('WHATSAPP_PHONE_NUMBER_ID')}/media",
        headers=auth_headers(),
        data={"messaging_product": "whatsapp"},
        files={"file": (filename, payload, mime)},
    )
    if upload.status_code >= 400:
        log.error("WhatsApp media upload failed: %s %s", upload.status_code, upload.text[:500])
    upload.raise_for_status()
    return upload.json()["id"]


async def send_voice(user: dict, text: str, user_key: str):
    if not cafe.voice_enabled[user_key]:
        return
    try:
        audio = await cafe.synthesize(text, cafe.selected_voice[user_key])
        media_id = await upload_media("reply.ogg", audio, "audio/ogg")
        await whatsapp_send(user, {"type": "audio", "audio": {"id": media_id, "voice": True}})
        log.info("Sent individual voice message for WhatsApp user %s", user_key)
    except Exception:
        log.exception("Could not synthesize or send WhatsApp voice")


async def send_group_voice(user: dict, turns, user_key: str):
    if not cafe.voice_enabled[user_key]:
        return
    try:
        audio = await cafe.synthesize_turns(turns)
        media_id = await upload_media("grupo.ogg", audio, "audio/ogg")
        await whatsapp_send(user, {"type": "audio", "audio": {"id": media_id, "voice": True}})
        log.info("Sent joined %s-turn voice message for WhatsApp user %s", len(turns), user_key)
    except Exception:
        log.exception("Could not synthesize or send WhatsApp group voice")


async def transcribe(media_id: str) -> str:
    global whisper_model
    info_response = await http.get(
        f"{graph_api()}/{media_id}",
        headers=auth_headers(),
        params={"phone_number_id": env("WHATSAPP_PHONE_NUMBER_ID")},
    )
    info_response.raise_for_status()
    info = info_response.json()
    audio_response = await http.get(info["url"], headers=auth_headers())
    audio_response.raise_for_status()
    suffixes = {
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/amr": ".amr",
    }
    suffix = suffixes.get(info.get("mime_type"), ".audio")
    async with whisper_lock:
        if whisper_model is None:
            from faster_whisper import WhisperModel
            whisper_model = await asyncio.to_thread(
                WhisperModel, os.getenv("WHISPER_MODEL", "tiny"),
                device="cpu", compute_type="int8", cpu_threads=1,
            )
    with tempfile.TemporaryDirectory() as directory:
        audio_path = Path(directory) / f"whatsapp{suffix}"
        audio_path.write_bytes(audio_response.content)
        segments, _ = await asyncio.to_thread(
            whisper_model.transcribe, str(audio_path), language="es", beam_size=1, vad_filter=True
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
    log.info(
        "Transcribed %s WhatsApp audio bytes with local Whisper %s",
        len(audio_response.content), os.getenv("WHISPER_MODEL", "tiny"),
    )
    return text


async def send_archive_audio(user: dict, item: dict) -> bool:
    """Send a licensed Internet Archive MP3 as a direct WhatsApp audio file.

    Only items whose license cafe.archive_download already verified reach
    this function. The audio streams from archive.org straight into the
    chat as a one-off transfer; the bot does not copy, host or store it.
    """
    size = item.get("size") or 0
    if size and size > WHATSAPP_AUDIO_LIMIT:
        log.info("Archive track too large for WhatsApp audio: %s bytes", size)
        return False
    name = str(item.get("file_name") or "audio.mp3")
    if not name.lower().endswith(".mp3"):
        log.info("Archive track %s is not MP3; sending links instead", name)
        return False
    try:
        async with http.stream(
            "GET", item["download_url"], timeout=120, follow_redirects=True
        ) as response:
            response.raise_for_status()
            declared = response.headers.get("content-length")
            if declared and int(declared) > WHATSAPP_AUDIO_LIMIT:
                log.info("Archive track too large for WhatsApp audio: %s bytes", declared)
                return False
            chunks = []
            received = 0
            async for chunk in response.aiter_bytes(1 << 16):
                received += len(chunk)
                if received > WHATSAPP_AUDIO_LIMIT:
                    log.info("Archive track exceeded the WhatsApp audio limit while streaming")
                    return False
                chunks.append(chunk)
        payload = b"".join(chunks)
        if not payload:
            return False
        media_id = await upload_media(name, payload, "audio/mpeg")
        await whatsapp_send(user, {"type": "audio", "audio": {"id": media_id}})
        log.info("Sent licensed archive audio %s to WhatsApp user %s", name, user.get("wa_id"))
        return True
    except Exception:
        log.exception("Could not send archive audio on WhatsApp")
        return False


async def search_music(user: dict, user_key: str, query: str):
    query = re.sub(r"\s+", " ", query).strip()[:120]
    if not query:
        cafe.pending_music_query[user_key] = True
        await send_text(user, "Decime el artista, la canción o ambos. Por ejemplo: Mercedes Sosa Alfonsina y el mar.")
        return
    cafe.pending_music_query.pop(user_key, None)
    apple_result, archive_result = await asyncio.gather(
        cafe.apple_music_results(query), cafe.licensed_music_downloads(query), return_exceptions=True,
    )
    tracks = apple_result if isinstance(apple_result, list) else []
    downloads = archive_result if isinstance(archive_result, list) else []
    if isinstance(apple_result, Exception):
        log.warning("Apple Music search failed: %s", apple_result)
    if isinstance(archive_result, Exception):
        log.warning("Internet Archive music search failed: %s", archive_result)
    if not tracks and not downloads:
        text = (
            f"No encontré fichas ni descargas con licencia para “{query}”.\n"
            f"Buscar en Spotify: {cafe.spotify_music_url(query)}\n"
            f"Buscar en Internet Archive: {cafe.archive_music_url(query)}"
        )
        await send_text(user, text)
        return
    summary = f"Resultados de música para “{query}”."
    if tracks:
        summary += " Las fichas y muestras son de Apple Music; el enlace de Spotify abre su búsqueda oficial."
    if downloads:
        summary += " Las descargas de Internet Archive tienen una licencia explícita y llegan como archivo de audio directo."
    await send_text(user, summary)
    for track in tracks:
        spotify_url = cafe.spotify_music_url(f"{track['artist']} {track['title']}")
        album = f"\nÁlbum: {track['album']}" if track["album"] else ""
        text = f"🎵 {track['title']}\n{track['artist']}{album}\n▶️ Apple Music: {track['url']}\nSpotify: {spotify_url}"
        if track["preview"]:
            text += f"\n🎧 Muestra oficial: {track['preview']}"
        await send_text(user, text)
    for item in downloads:
        if await send_archive_audio(user, item):
            await send_text(
                user,
                f"⬇️ {item['title']} llegó como archivo de audio directo. Licencia: {item['license']} ({item['license_url']}). "
                f"La descarga la ofrece Internet Archive y no copio ni almaceno el archivo. Ficha y fuente: {item['item_url']}",
            )
        else:
            await send_text(
                user,
                f"⬇️ {item['title']}\n{item['artist']}\nLicencia: {item['license']} ({item['license_url']}).\n"
                f"Escuchar o descargar desde la fuente: {item['download_url']}\nFicha: {item['item_url']}",
            )


async def show_voices(user: dict, user_key: str):
    lines = [
        "🎙️ ELEGIR UNA VOZ",
        "Escribe /voz seguido del número (por ejemplo, /voz 3). Después te envío una muestra.",
        "",
    ]
    for index, (voice, label) in enumerate(VOICE_ITEMS, start=1):
        mark = " (actual)" if cafe.selected_voice[user_key] == voice else ""
        lines.append(f"{index}. {label}{mark}")
    await send_text(user, "\n".join(lines))


async def ask_preferred_name(user: dict, user_key: str, action="mode"):
    cafe.awaiting_name[user_key] = True
    cafe.pending_action[user_key] = action
    await send_text(
        user,
        "👋 PASO 1 DE 2: TU NOMBRE\n"
        "Antes de mostrarte el menú, ¿cómo quieres que te llame? "
        "Escribe solamente tu nombre o dilo en un audio. Después verás el menú para elegir una o varias voces.",
    )


async def start_group_mode(user: dict, user_key: str, kind: str):
    group_selection[user_key] = {"kind": kind, "voices": []}
    size = GROUP_MODE_SIZES[kind]
    numbers = {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis"}
    if kind == "story":
        intro = "Modo historia: elige la primera de cuatro voces distintas. Serán cuatro personajes que continúan una misma escena."
    elif kind == "duo":
        intro = "Modo dúo: elige la primera voz. Después elegirás la segunda y conversarán entre ellas en un solo audio."
    else:
        intro = (
            f"Modo {GROUP_MODE_LABELS[kind]}: elige la primera de {numbers[size]} voces distintas. "
            "Conversarán entre ellas en un solo audio."
        )
    await send_text(
        user,
        f"{intro}\nEscribe /voces para ver la lista y después /voz seguido del número "
        f"(por ejemplo, /voz 3). Llevas 0 de {size}.",
    )


async def advance_group_selection(user: dict, user_key: str, voice: str):
    session = group_selection.get(user_key)
    if not session:
        return False
    kind = session["kind"]
    voices = session["voices"]
    if voice in voices:
        await send_text(user, "Elige voces distintas. Escribe /voz con el número de otra voz de la lista.")
        return True
    voices.append(voice)
    size = GROUP_MODE_SIZES[kind]
    if len(voices) < size:
        await send_text(
            user,
            f"Modo {GROUP_MODE_LABELS[kind]}: voz {len(voices)}: {cafe.voice_name(voice)}. "
            f"Elige la siguiente ({len(voices) + 1} de {size}) con /voz y el número.",
        )
        return True
    group_selection.pop(user_key, None)
    await complete_group_selection(user, user_key, kind, list(voices))
    return True


async def complete_group_selection(user: dict, user_key: str, kind: str, voices):
    voices = tuple(voices)
    cafe.clear_group_modes(user_key)
    flags, pairs = cafe.GROUP_MODE_FLAGS[kind]
    flags[user_key] = True
    pairs[user_key] = voices
    cafe.selected_voice[user_key] = voices[0]
    cafe.voice_enabled[user_key] = True
    names = [cafe.voice_name(item) for item in voices]
    name = get_preferred_name(user_key) or user.get("profile_name") or "amigo"
    samples = cafe.group_samples(kind, names, name)
    combined = "\n\n".join(f"{speaker}: {sample}" for speaker, sample in zip(names, samples))
    await send_text(user, combined)
    await send_group_voice(user, list(zip(voices, samples)), user_key)


async def welcome(user: dict, user_key: str, fallback_name=None):
    group_selection.pop(user_key, None)
    name = get_preferred_name(user_key) or fallback_name or "amigo"
    text = (
        f"📋 MENÚ PRINCIPAL\nHola, {name}. Escribe uno de estos comandos para empezar. "
        "En los modos dúo, trío, cuarteto, quinteto y sexteto, las voces conversan entre ellas "
        "y se llaman por su nombre en un mismo audio.\n\n"
        "/voces - elegir una voz\n"
        "/duo - conversar con dos voces\n"
        "/trio - conversar con tres voces\n"
        "/cuarteto - conversar con cuatro voces\n"
        "/quinteto - conversar con cinco voces\n"
        "/sexteto - conversar con seis voces\n"
        "/historia - crear una historia con cuatro personajes\n"
        "/musica - buscar un artista o una canción\n"
        "/nombre - cambiar cómo te llamo\n"
        "/solo_texto - desactivar las respuestas de audio\n"
        "/con_voz - activar las respuestas de audio\n"
        "/reset - reiniciar la conversación\n\n"
        "También puedes escribirme o enviarme una nota de voz. Para volver a ver este menú, escribe /menu."
    )
    await send_text(user, text)
    await send_voice(user, f"Hola, {name}. Ya estoy listo. Elige hasta seis voces o una historia para empezar.", user_key)


def make_user(message: dict, contact: dict) -> dict:
    profile = contact.get("profile") or {}
    return {
        "wa_id": message.get("from") or contact.get("wa_id"),
        "bsuid": message.get("from_user_id") or contact.get("user_id"),
        "profile_name": profile.get("name"),
    }


async def handle_message(message: dict, contact: dict):
    user = make_user(message, contact)
    user_key = user["bsuid"] or user["wa_id"]
    if not user_key:
        return
    text = message.get("text", {}).get("body", "").strip()
    asyncio.create_task(mark_read(message.get("id", "")))
    try:
        if cafe.awaiting_name[user_key] and not text.startswith("/"):
            if message.get("type") == "audio":
                proposed_name = await transcribe(message["audio"]["id"])
            else:
                proposed_name = text
            name = re.sub(r"\s+", " ", proposed_name).strip()
            if not name or len(name) > 40:
                await send_text(user, "Decime un nombre de hasta 40 caracteres para saber cómo llamarte.")
                return
            save_preferred_name(user_key, name)
            cafe.awaiting_name[user_key] = False
            action = cafe.pending_action.pop(user_key, "mode")
            await send_text(user, f"Gracias, {name}. Voy a llamarte así.")
            if action in GROUP_MODE_SIZES:
                await start_group_mode(user, user_key, action)
            else:
                await welcome(user, user_key, name)
            return
        if text.startswith("/start") or text.startswith("/menu") or text.startswith("/ayuda"):
            await welcome(user, user_key, user.get("profile_name"))
            return
        if text.startswith("/nombre"):
            await ask_preferred_name(user, user_key)
            return
        if text.startswith("/duo"):
            await start_group_mode(user, user_key, "duo")
            return
        if text.startswith("/trio"):
            await start_group_mode(user, user_key, "trio")
            return
        if text.startswith("/cuarteto"):
            await start_group_mode(user, user_key, "quartet")
            return
        if text.startswith("/quinteto"):
            await start_group_mode(user, user_key, "quintet")
            return
        if text.startswith("/sexteto"):
            await start_group_mode(user, user_key, "sextet")
            return
        if text.startswith("/historia"):
            await start_group_mode(user, user_key, "story")
            return
        if text.startswith("/individual"):
            group_selection.pop(user_key, None)
            cafe.clear_group_modes(user_key)
            await send_text(
                user,
                f"Modo individual activado. Tu voz actual es {VOICES[cafe.selected_voice[user_key]]}. "
                "Escribe /voces para ver la lista y /voz N para cambiarla.",
            )
            await send_voice(user, "Modo individual activado. Seguimos con una sola voz.", user_key)
            return
        if text.startswith("/voces") or text.startswith("/voices"):
            await show_voices(user, user_key)
            return
        match = re.fullmatch(r"/?voz\s+(\d{1,2})", text, re.IGNORECASE)
        if match:
            index = int(match.group(1))
            if not 1 <= index <= len(VOICE_ITEMS):
                await send_text(user, f"Elegí un número del 1 al {len(VOICE_ITEMS)}. Usá /voces para ver la lista.")
                return
            voice, label = VOICE_ITEMS[index - 1]
            if await advance_group_selection(user, user_key, voice):
                return
            cafe.clear_group_modes(user_key)
            cafe.selected_voice[user_key] = voice
            cafe.voice_enabled[user_key] = True
            sample = f"Elegiste {label}. Así sueno ahora. Mandame un mensaje o un audio y seguimos probando."
            await send_text(user, sample)
            await send_voice(user, sample, user_key)
            return
        if text.startswith("/solo_texto"):
            cafe.voice_enabled[user_key] = False
            await send_text(user, "Audio desactivado. Te respondo solo por texto. Usá /con_voz para activarlo.")
            return
        if text.startswith("/con_voz"):
            cafe.voice_enabled[user_key] = True
            await send_text(user, "Audio activado.")
            await send_voice(user, "Audio activado. Ya te respondo también por voz.", user_key)
            return
        if text.startswith("/reset"):
            cafe.histories[user_key].clear()
            cafe.pending_music_query.pop(user_key, None)
            cafe.pending_weather_query.pop(user_key, None)
            cafe.pending_sports_query.pop(user_key, None)
            group_selection.pop(user_key, None)
            await send_text(user, "Conversación reiniciada.")
            return
        if text.startswith("/musica") or text.startswith("/music"):
            await search_music(user, user_key, text.partition(" ")[2])
            return
        if message.get("type") == "audio":
            user_text = await transcribe(message["audio"]["id"])
            if not user_text:
                await send_text(user, "No pude entender el audio. Probá grabarlo de nuevo.")
                return
            log.info("Voice message transcribed for WhatsApp user %s (%s characters)", user_key, len(user_text))
        elif message.get("type") == "text" and text:
            user_text = text
        else:
            await send_text(user, "Por ahora puedo responder mensajes de texto y audios.")
            return
        if user_key in cafe.pending_music_query:
            await search_music(user, user_key, user_text)
            return
        music_query = cafe.music_query_from_text(user_text)
        if music_query is not None:
            await search_music(user, user_key, music_query)
            return
        status, user_text, source = await cafe.prepare_live_query(user_key, user_text)
        if status == "ask":
            await send_text(user, user_text)
            return
        source_text = f"\n\nFuente: {source}" if source else ""
        pending = group_selection.get(user_key)
        if pending:
            size = GROUP_MODE_SIZES[pending["kind"]]
            await send_text(
                user,
                f"Estás eligiendo las voces del modo {GROUP_MODE_LABELS[pending['kind']]}: llevas "
                f"{len(pending['voices'])} de {size}. Escribe /voz seguido del número de la siguiente "
                "voz para empezar, o /menu para cancelar.",
            )
            return
        if cafe.story_enabled[user_key]:
            voices = cafe.story_pairs[user_key]
            replies = await cafe.answer_story(user_key, user_text)
            combined = "\n\n".join(
                f"{cafe.voice_name(voice)}: {reply}" for voice, reply in zip(voices, replies)
            )
            await send_text(user, combined + source_text)
            await send_group_voice(user, list(zip(voices, replies)), user_key)
            return
        for kind in cafe.DIALOGUE_KINDS:
            enabled, pairs = cafe.GROUP_MODE_FLAGS[kind]
            if enabled[user_key]:
                voices = pairs[user_key]
                replies = await cafe.answer_dialogue(user_key, user_text, voices)
                combined = "\n\n".join(
                    f"{cafe.voice_name(voice)}: {reply}" for voice, reply in zip(voices, replies)
                )
                await send_text(user, combined + source_text)
                await send_group_voice(user, list(zip(voices, replies)), user_key)
                return
        result = await cafe.answer(user_key, user_text)
        await send_text(user, result + source_text)
        await send_voice(user, result, user_key)
    except Exception:
        log.exception("Failed to handle WhatsApp message")
        await send_text(user, "Tuve un problema técnico. Probá de nuevo en un momento.")


def already_processed(message_id: str) -> bool:
    if not message_id:
        return False
    if message_id in processed_ids:
        return True
    processed_ids.add(message_id)
    processed_order.append(message_id)
    if len(processed_order) > 2000:
        processed_ids.discard(processed_order.popleft())
    return False


async def process_update(update: dict):
    for entry in update.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change.get("value", {})
            contacts = value.get("contacts", [])
            contact = contacts[0] if contacts else {}
            for message in value.get("messages", []):
                if already_processed(message.get("id", "")):
                    continue
                try:
                    await handle_message(message, contact)
                except Exception:
                    log.exception("Failed to process WhatsApp update")


@router.get("/")
async def health():
    return {"ok": True, "service": "cafe-sabroso-whatsapp"}


@router.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == env("WHATSAPP_VERIFY_TOKEN")
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("Verification failed", status_code=403)


@router.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    expected = "sha256=" + hmac.new(
        env("WHATSAPP_APP_SECRET").encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return PlainTextResponse("Invalid signature", status_code=401)
    update = await request.json()
    asyncio.create_task(process_update(update))
    return {"ok": True}


app = FastAPI(title="Café Sabroso WhatsApp")
app.include_router(router)


@app.on_event("shutdown")
async def shutdown():
    await http.aclose()
