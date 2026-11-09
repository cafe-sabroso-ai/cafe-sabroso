import asyncio
import logging
import os
import re
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
http = httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=20.0))
whisper_model = None
whisper_lock = asyncio.Lock()


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


async def answer(chat_id: int, user_text: str):
    history = histories[chat_id]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
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
    result = response.json()["choices"][0]["message"]["content"].strip()
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": result})
    return result


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


async def show_voices(chat_id: int):
    keyboard = []
    for voice, label in VOICES.items():
        mark = "✓ " if selected_voice[chat_id] == voice else ""
        keyboard.append([{"text": mark + label, "callback_data": f"voice:{voice}"}])
    await send_text(chat_id, "Elegí una voz. Después de elegirla te mando una muestra.", reply_markup={"inline_keyboard": keyboard})


async def welcome(chat_id: int):
    text = (
        "Listo, ya funciono. Escribime o mandame una nota de voz y te respondo en texto y audio. "
        "Con /voces elegís entre doce voces masculinas y femeninas en español. La inicial es Tomás, de Argentina. "
        "Con /solo_texto apagás el audio y con /con_voz lo volvés a activar."
    )
    await send_text(chat_id, text)
    await send_voice(chat_id, text)


async def handle_message(message: dict):
    if "text" not in message and "voice" not in message and "audio" not in message:
        return
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    try:
        if text.startswith("/start"):
            await welcome(chat_id)
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
        result = await answer(chat_id, user_text)
        await send_text(chat_id, result)
        await send_voice(chat_id, result)
    except Exception:
        log.exception("Failed to handle message")
        await send_text(chat_id, "Tuve un problema técnico. Probá de nuevo en un momento.")


async def handle_callback(callback: dict):
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")
    if not data.startswith("voice:"):
        await telegram("answerCallbackQuery", callback_query_id=callback["id"])
        return
    voice = data.split(":", 1)[1]
    if voice not in VOICES:
        await telegram("answerCallbackQuery", callback_query_id=callback["id"], text="Esa voz no está disponible.")
        return
    selected_voice[chat_id] = voice
    voice_enabled[chat_id] = True
    await telegram("answerCallbackQuery", callback_query_id=callback["id"], text=f"Elegiste {VOICES[voice]}")
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
