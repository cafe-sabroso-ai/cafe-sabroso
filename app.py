import asyncio
import logging
import os
import re
import sqlite3
import tempfile
from collections import defaultdict, deque
from pathlib import Path

import edge_tts
import httpx
from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telegram-voice-bot")

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/cafe_sabroso.db")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
TELEGRAM_FILE = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}"

VOICES = {
    "es-AR-TomasNeural": "Tomás - argentino",
    "es-AR-ElenaNeural": "Elena - argentina",
    "es-ES-AlvaroNeural": "Álvaro - España",
    "es-ES-ElviraNeural": "Elvira - España",
    "es-MX-JorgeNeural": "Jorge - México",
    "es-MX-DaliaNeural": "Dalia - México",
    "es-US-AlonsoNeural": "Alonso - Estados Unidos",
    "es-US-PalomaNeural": "Paloma - Estados Unidos",
    "es-CO-GonzaloNeural": "Gonzalo - Colombia",
    "es-CO-SalomeNeural": "Salome - Colombia",
    "es-CL-LorenzoNeural": "Lorenzo - Chile",
    "es-CL-CatalinaNeural": "Catalina - Chile",
}
DEFAULT_VOICE = "es-AR-TomasNeural"
SYSTEM_PROMPT = (
    "Sos un asistente de IA general, útil, claro y cálido. Respondés en español "
    "rioplatense por defecto, salvo que la persona pida otro idioma. Tus respuestas "
    "se escuchan como notas de voz: usá frases naturales, evitá tablas y formato "
    "visual, y andá directo al punto. Para preguntas cotidianas, respondé en menos "
    "de 120 palabras. Si una respuesta necesita más detalle, dá primero un resumen "
    "breve y ofrecé seguir. No inventes datos actuales; si no sabés algo, decilo."
)

app = FastAPI(title="Telegram Spanish Voice AI Bot")
selected_voice = defaultdict(lambda: DEFAULT_VOICE)
voice_enabled = defaultdict(lambda: True)
histories = defaultdict(lambda: deque(maxlen=12))
duo_enabled = defaultdict(lambda: False)
duo_first = {}
duo_pairs = {}
awaiting_name = defaultdict(lambda: False)
pending_action = {}
http = httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=20.0))
whisper_model = None
whisper_lock = asyncio.Lock()

Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(DATABASE_PATH) as database:
    database.execute(
        "CREATE TABLE IF NOT EXISTS preferred_names (chat_id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )


def get_preferred_name(chat_id: int):
    with sqlite3.connect(DATABASE_PATH) as database:
        row = database.execute(
            "SELECT name FROM preferred_names WHERE chat_id = ?", (chat_id,)
        ).fetchone()
    return row[0] if row else None


def save_preferred_name(chat_id: int, name: str):
    with sqlite3.connect(DATABASE_PATH) as database:
        database.execute(
            "INSERT INTO preferred_names (chat_id, name) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET name = excluded.name",
            (chat_id, name),
        )


async def telegram(method: str, **kwargs):
    response = await http.post(f"{TELEGRAM_API}/{method}", json=kwargs)
    if response.status_code >= 400:
        log.error("Telegram %s failed: %s %s", method, response.status_code, response.text[:500])
    response.raise_for_status()
    return response.json()["result"]


async def send_text(chat_id: int, text: str, **kwargs):
    chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)] or [""]
    for chunk in chunks:
        await telegram("sendMessage", chat_id=chat_id, text=chunk, **kwargs)


def speech_text(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[*_`#>]", "", text)
    return text.strip()[:5000]


async def synthesize(text: str, voice: str) -> bytes:
    with tempfile.TemporaryDirectory() as directory:
        mp3 = Path(directory) / "reply.mp3"
        ogg = Path(directory) / "reply.ogg"
        await edge_tts.Communicate(speech_text(text), voice).save(str(mp3))
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp3),
            "-c:a", "libopus", "-b:a", "48k", "-ac", "1", str(ogg),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()[:300]}")
        return ogg.read_bytes()


async def send_voice(chat_id: int, text: str):
    if not voice_enabled[chat_id]:
        return
    try:
        await telegram("sendChatAction", chat_id=chat_id, action="upload_voice")
        audio = await synthesize(text, selected_voice[chat_id])
        response = await http.post(
            f"{TELEGRAM_API}/sendVoice",
            data={"chat_id": str(chat_id)},
            files={"voice": ("reply.ogg", audio, "audio/ogg")},
        )
        if response.status_code >= 400:
            log.error("Telegram sendVoice failed: %s %s", response.status_code, response.text[:500])
        response.raise_for_status()
    except Exception:
        log.exception("Could not synthesize or send voice")


async def complete(messages):
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "X-Title": "Café Sabroso"}
    if PUBLIC_URL:
        headers["HTTP-Referer"] = PUBLIC_URL
    response = await http.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json={"model": OPENROUTER_MODEL, "messages": messages, "temperature": 0.5, "max_tokens": 700},
    )
    if response.status_code >= 400:
        log.error("OpenRouter chat failed: %s %s", response.status_code, response.text[:500])
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def voice_name(voice: str) -> str:
    return VOICES[voice].split(" - ", 1)[0]


async def synthesize_duo(turns):
    audio_parts = await asyncio.gather(
        *(synthesize(text, voice) for voice, text in turns)
    )
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for index, audio in enumerate(audio_parts):
            path = Path(directory) / f"turn-{index}.ogg"
            path.write_bytes(audio)
            paths.append(path)
        concat_file = Path(directory) / "turns.txt"
        concat_file.write_text("".join(f"file '{path}'\n" for path in paths))
        joined = Path(directory) / "duo.ogg"
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:a", "libopus", "-b:a", "48k", "-ac", "1", str(joined),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError(f"ffmpeg duo join failed: {stderr.decode()[:300]}")
        return joined.read_bytes()


async def send_duo_voice(chat_id: int, turns):
    if not voice_enabled[chat_id]:
        return
    try:
        await telegram("sendChatAction", chat_id=chat_id, action="upload_voice")
        audio = await synthesize_duo(turns)
        response = await http.post(
            f"{TELEGRAM_API}/sendVoice",
            data={"chat_id": str(chat_id)},
            files={"voice": ("duo.ogg", audio, "audio/ogg")},
        )
        if response.status_code >= 400:
            log.error("Telegram duo sendVoice failed: %s %s", response.status_code, response.text[:500])
        response.raise_for_status()
    except Exception:
        log.exception("Could not synthesize or send duo voice")


async def answer(chat_id: int, user_text: str):
    history = histories[chat_id]
    name = get_preferred_name(chat_id)
    name_instruction = f" La persona prefiere que la llamen {name}. Usá ese nombre de forma natural." if name else ""
    messages = [{"role": "system", "content": SYSTEM_PROMPT + name_instruction}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    result = await complete(messages)
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": result})
    return result


async def answer_duo(chat_id: int, user_text: str):
    first_voice, second_voice = duo_pairs[chat_id]
    first_name = voice_name(first_voice)
    second_name = voice_name(second_voice)
    history = histories[chat_id]
    name = get_preferred_name(chat_id)
    name_instruction = f" La persona prefiere que la llamen {name}. Empezá tu turno usando ese nombre de forma natural." if name else ""
    first_prompt = (
        SYSTEM_PROMPT
        + name_instruction
        + f" En este modo dúo sos {first_name}. Respondé primero, de forma útil y concreta, "
        "en un máximo de 70 palabras y sin anunciar que sos una IA."
    )
    first_messages = [{"role": "system", "content": first_prompt}]
    first_messages.extend(history)
    first_messages.append({"role": "user", "content": user_text})
    first = await complete(first_messages)
    second_prompt = (
        SYSTEM_PROMPT
        + name_instruction
        + f" En este modo dúo sos {second_name}. Otro asistente llamado {first_name} ya habló. "
        "Aportá una idea complementaria, un ejemplo o un matiz útil sin repetirlo. "
        "Podés reaccionar naturalmente a su comentario. Usá un máximo de 60 palabras "
        "y no te presentes ni anuncies que sos una IA."
    )
    second_messages = [{"role": "system", "content": second_prompt}]
    second_messages.extend(history)
    second_messages.append({
        "role": "user",
        "content": (
            f"Mensaje original de la persona: {user_text}\n\n"
            f"{first_name} respondió: {first}\n\n"
            f"Ahora respondé vos como {second_name}."
        ),
    })
    second = await complete(second_messages)
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": f"{first_name}: {first}\n{second_name}: {second}"})
    return first, second


async def transcribe(file_id: str) -> str:
    global whisper_model
    info = await telegram("getFile", file_id=file_id)
    audio_response = await http.get(f"{TELEGRAM_FILE}/{info['file_path']}")
    audio_response.raise_for_status()
    suffix = Path(info["file_path"]).suffix or ".ogg"
    async with whisper_lock:
        if whisper_model is None:
            from faster_whisper import WhisperModel
            whisper_model = await asyncio.to_thread(
                WhisperModel, WHISPER_MODEL, device="cpu", compute_type="int8"
            )
    with tempfile.TemporaryDirectory() as directory:
        audio_path = Path(directory) / f"telegram{suffix}"
        audio_path.write_bytes(audio_response.content)
        segments, _ = await asyncio.to_thread(
            whisper_model.transcribe, str(audio_path), language="es", beam_size=1, vad_filter=True
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
    log.info("Transcribed %s audio bytes with local Whisper %s", len(audio_response.content), WHISPER_MODEL)
    return text


def voice_keyboard(chat_id: int, prefix: str, exclude=None):
    keyboard = []
    for voice, label in VOICES.items():
        if voice == exclude:
            continue
        mark = "✓ " if prefix == "voice" and selected_voice[chat_id] == voice else ""
        keyboard.append([{"text": mark + label, "callback_data": f"{prefix}:{voice}"}])
    return keyboard


async def show_voices(chat_id: int):
    await send_text(
        chat_id,
        "Elegí una voz. Después de elegirla te mando una muestra.",
        reply_markup={"inline_keyboard": voice_keyboard(chat_id, "voice")},
    )


async def ask_preferred_name(chat_id: int, action="mode"):
    awaiting_name[chat_id] = True
    pending_action[chat_id] = action
    await send_text(chat_id, "Antes de empezar, ¿cómo querés que te llame? Podés escribir tu nombre o decirlo en un audio.")


async def start_duo(chat_id: int):
    if not get_preferred_name(chat_id):
        await ask_preferred_name(chat_id, "duo")
        return
    duo_first.pop(chat_id, None)
    await send_text(
        chat_id,
        "Modo dúo: elegí la primera voz. Después vas a elegir la segunda y van a responder por turnos en un solo audio.",
        reply_markup={"inline_keyboard": voice_keyboard(chat_id, "duo1")},
    )


async def welcome(chat_id: int):
    name = get_preferred_name(chat_id)
    if not name:
        await ask_preferred_name(chat_id)
        return
    text = (
        f"Hola, {name}. Escribime o mandame una nota de voz y te respondo en texto y audio. "
        "Elegí una voz o un dúo. En el dúo, dos voces responden por turnos en un mismo audio. "
        "Con /individual volvés al modo normal y con /nombre cambiás tu nombre. "
        "Con /solo_texto apagás el audio y con /con_voz lo volvés a activar."
    )
    keyboard = [[
        {"text": "Elegir una voz", "callback_data": "mode:single"},
        {"text": "Elegir modo dúo", "callback_data": "mode:duo"},
    ]]
    await send_text(chat_id, text, reply_markup={"inline_keyboard": keyboard})
    await send_voice(chat_id, f"Hola, {name}. Ya estoy listo. Elegí una voz o un dúo para empezar.")


async def handle_message(message: dict):
    if "text" not in message and "voice" not in message and "audio" not in message:
        return
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    try:
        if awaiting_name[chat_id] and not text.startswith("/"):
            if "voice" in message or "audio" in message:
                media = message.get("voice") or message.get("audio")
                proposed_name = await transcribe(media["file_id"])
            else:
                proposed_name = text
            name = re.sub(r"\s+", " ", proposed_name).strip()
            if not name or len(name) > 40:
                await send_text(chat_id, "Decime un nombre de hasta 40 caracteres para saber cómo llamarte.")
                return
            save_preferred_name(chat_id, name)
            awaiting_name[chat_id] = False
            action = pending_action.pop(chat_id, "mode")
            await send_text(chat_id, f"Gracias, {name}. Voy a llamarte así.")
            if action == "duo":
                await start_duo(chat_id)
            else:
                await welcome(chat_id)
            return
        if text.startswith("/start"):
            await welcome(chat_id)
            return
        if text.startswith("/nombre"):
            await ask_preferred_name(chat_id)
            return
        if text.startswith("/duo"):
            await start_duo(chat_id)
            return
        if text.startswith("/individual"):
            duo_enabled[chat_id] = False
            await send_text(chat_id, f"Volviste al modo de una voz: {VOICES[selected_voice[chat_id]]}.")
            await send_voice(chat_id, "Modo individual activado. Seguimos con una sola voz.")
            return
        if text.startswith("/voces") or text.startswith("/voices") or text.startswith("/voz"):
            await show_voices(chat_id)
            return
        if text.startswith("/solo_texto"):
            voice_enabled[chat_id] = False
            await send_text(chat_id, "Audio desactivado. Te respondo solo por texto. Usá /con_voz para activarlo.")
            return
        if text.startswith("/con_voz"):
            voice_enabled[chat_id] = True
            await send_text(chat_id, "Audio activado.")
            await send_voice(chat_id, "Audio activado. Ya te respondo también por voz.")
            return
        if text.startswith("/reset"):
            histories[chat_id].clear()
            await send_text(chat_id, "Conversación reiniciada.")
            return
        if not get_preferred_name(chat_id):
            await ask_preferred_name(chat_id)
            return
        await telegram("sendChatAction", chat_id=chat_id, action="typing")
        if "voice" in message or "audio" in message:
            media = message.get("voice") or message.get("audio")
            user_text = await transcribe(media["file_id"])
            if not user_text:
                await send_text(chat_id, "No pude entender el audio. Probá grabarlo de nuevo.")
                return
            log.info("Voice message transcribed for chat %s (%s characters)", chat_id, len(user_text))
        else:
            user_text = text
        if duo_enabled[chat_id]:
            first_voice, second_voice = duo_pairs[chat_id]
            first, second = await answer_duo(chat_id, user_text)
            combined = f"{voice_name(first_voice)}: {first}\n\n{voice_name(second_voice)}: {second}"
            await send_text(chat_id, combined)
            await send_duo_voice(chat_id, [(first_voice, first), (second_voice, second)])
            return
        result = await answer(chat_id, user_text)
        await send_text(chat_id, result)
        await send_voice(chat_id, result)
    except Exception:
        log.exception("Failed to handle message")
        await send_text(chat_id, "Tuve un problema técnico. Probá de nuevo en un momento.")


async def handle_callback(callback: dict):
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")
    callback_id = callback["id"]
    if data == "mode:single":
        duo_enabled[chat_id] = False
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Modo de una voz")
        await show_voices(chat_id)
        return
    if data == "mode:duo":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Modo dúo")
        await start_duo(chat_id)
        return
    if data.startswith("duo1:"):
        voice = data.split(":", 1)[1]
        if voice not in VOICES:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Esa voz no está disponible.")
            return
        duo_first[chat_id] = voice
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=f"Primera voz: {voice_name(voice)}")
        await send_text(
            chat_id,
            f"Primera voz: {voice_name(voice)}. Ahora elegí una segunda voz distinta.",
            reply_markup={"inline_keyboard": voice_keyboard(chat_id, "duo2", exclude=voice)},
        )
        return
    if data.startswith("duo2:"):
        voice = data.split(":", 1)[1]
        first = duo_first.get(chat_id)
        if voice not in VOICES or not first:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Empecemos de nuevo.")
            await start_duo(chat_id)
            return
        if voice == first:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Elegí dos voces distintas.")
            return
        duo_pairs[chat_id] = (first, voice)
        duo_enabled[chat_id] = True
        selected_voice[chat_id] = first
        voice_enabled[chat_id] = True
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=f"Dúo: {voice_name(first)} y {voice_name(voice)}")
        name = get_preferred_name(chat_id)
        first_sample = f"Hola, {name}. Soy {voice_name(first)} y vamos a responder juntos, por turnos."
        second_sample = f"{name}, yo soy {voice_name(voice)}. Mandanos un mensaje o un audio para probar el modo dúo."
        await send_text(chat_id, f"{voice_name(first)}: {first_sample}\n\n{voice_name(voice)}: {second_sample}")
        await send_duo_voice(chat_id, [(first, first_sample), (voice, second_sample)])
        return
    if not data.startswith("voice:"):
        await telegram("answerCallbackQuery", callback_query_id=callback_id)
        return
    voice = data.split(":", 1)[1]
    if voice not in VOICES:
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Esa voz no está disponible.")
        return
    duo_enabled[chat_id] = False
    selected_voice[chat_id] = voice
    voice_enabled[chat_id] = True
    await telegram("answerCallbackQuery", callback_query_id=callback_id, text=f"Elegiste {VOICES[voice]}")
    sample = f"Elegiste {VOICES[voice]}. Así sueno ahora. Mandame un mensaje o un audio y seguimos probando."
    await send_text(chat_id, sample)
    await send_voice(chat_id, sample)


async def process_update(update: dict):
    try:
        if "message" in update:
            await handle_message(update["message"])
        elif "callback_query" in update:
            await handle_callback(update["callback_query"])
    except Exception:
        log.exception("Failed to process update")


@app.on_event("startup")
async def startup():
    if PUBLIC_URL:
        payload = {"url": f"{PUBLIC_URL}/webhook", "drop_pending_updates": True}
        if WEBHOOK_SECRET:
            payload["secret_token"] = WEBHOOK_SECRET
        await telegram("setWebhook", **payload)
        log.info("Telegram webhook configured at %s/webhook", PUBLIC_URL)


@app.on_event("shutdown")
async def shutdown():
    await http.aclose()


@app.get("/")
async def health():
    return {"ok": True, "service": "telegram-spanish-voice-ai"}


@app.post("/webhook")
async def webhook(request: Request):
    if WEBHOOK_SECRET and request.headers.get("x-telegram-bot-api-secret-token") != WEBHOOK_SECRET:
        return {"ok": False}
    update = await request.json()
    asyncio.create_task(process_update(update))
    return {"ok": True}
