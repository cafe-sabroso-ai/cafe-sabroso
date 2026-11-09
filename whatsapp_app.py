import asyncio
import hashlib
import hmac
import logging
import os
import re
import tempfile
from collections import defaultdict, deque
from pathlib import Path

import edge_tts
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cafe-sabroso-whatsapp")

WHATSAPP_ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
WHATSAPP_PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
WHATSAPP_VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]
WHATSAPP_APP_SECRET = os.environ["WHATSAPP_APP_SECRET"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
GRAPH_VERSION = os.getenv("WHATSAPP_GRAPH_VERSION", "v27.0")
GRAPH_API = f"https://graph.facebook.com/{GRAPH_VERSION}"

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
VOICE_ITEMS = list(VOICES.items())
DEFAULT_VOICE = "es-AR-TomasNeural"
SYSTEM_PROMPT = (
    "Sos un asistente de IA general, útil, claro y cálido. Respondés en español "
    "rioplatense por defecto, salvo que la persona pida otro idioma. Tus respuestas "
    "se escuchan como notas de voz: usá frases naturales, evitá tablas y formato "
    "visual, y andá directo al punto. Para preguntas cotidianas, respondé en menos "
    "de 120 palabras. Si una respuesta necesita más detalle, dá primero un resumen "
    "breve y ofrecé seguir. No inventes datos actuales; si no sabés algo, decilo."
)

app = FastAPI(title="Café Sabroso WhatsApp")
selected_voice = defaultdict(lambda: DEFAULT_VOICE)
voice_enabled = defaultdict(lambda: True)
histories = defaultdict(lambda: deque(maxlen=12))
processed_ids = set()
processed_order = deque()
http = httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=20.0))
whisper_model = None
whisper_lock = asyncio.Lock()


def auth_headers():
    return {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}


def recipient_fields(user: dict):
    if user.get("bsuid"):
        return {"recipient": user["bsuid"]}
    return {"to": user["wa_id"]}


async def whatsapp_send(user: dict, payload: dict):
    body = {"messaging_product": "whatsapp", **recipient_fields(user), **payload}
    response = await http.post(
        f"{GRAPH_API}/{WHATSAPP_PHONE_NUMBER_ID}/messages", headers=auth_headers(), json=body
    )
    if response.status_code >= 400:
        log.error("WhatsApp send failed: %s %s", response.status_code, response.text[:500])
    response.raise_for_status()
    return response.json()


async def send_text(user: dict, text: str):
    chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)] or [""]
    for chunk in chunks:
        await whatsapp_send(user, {"type": "text", "text": {"body": chunk, "preview_url": False}})


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


async def send_voice(user: dict, text: str, user_key: str):
    if not voice_enabled[user_key]:
        return
    try:
        audio = await synthesize(text, selected_voice[user_key])
        upload = await http.post(
            f"{GRAPH_API}/{WHATSAPP_PHONE_NUMBER_ID}/media",
            headers=auth_headers(),
            data={"messaging_product": "whatsapp"},
            files={"file": ("reply.ogg", audio, "audio/ogg")},
        )
        if upload.status_code >= 400:
            log.error("WhatsApp media upload failed: %s %s", upload.status_code, upload.text[:500])
        upload.raise_for_status()
        media_id = upload.json()["id"]
        await whatsapp_send(user, {"type": "audio", "audio": {"id": media_id, "voice": True}})
    except Exception:
        log.exception("Could not synthesize or send WhatsApp voice")


async def answer(user_key: str, user_text: str):
    history = histories[user_key]
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


async def transcribe(media_id: str) -> str:
    global whisper_model
    info_response = await http.get(
        f"{GRAPH_API}/{media_id}",
        headers=auth_headers(),
        params={"phone_number_id": WHATSAPP_PHONE_NUMBER_ID},
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
                WhisperModel, WHISPER_MODEL, device="cpu", compute_type="int8"
            )
    with tempfile.TemporaryDirectory() as directory:
        audio_path = Path(directory) / f"whatsapp{suffix}"
        audio_path.write_bytes(audio_response.content)
        segments, _ = await asyncio.to_thread(
            whisper_model.transcribe, str(audio_path), language="es", beam_size=1, vad_filter=True
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
    log.info("Transcribed %s WhatsApp audio bytes with local Whisper %s", len(audio_response.content), WHISPER_MODEL)
    return text


async def welcome(user: dict, user_key: str):
    text = (
        "Soy Café Sabroso. Escribime o mandame una nota de voz y te respondo en texto y audio. "
        "Con /voces ves las doce voces en español. La inicial es Tomás, de Argentina. "
        "Con /solo_texto apagás el audio y con /con_voz lo volvés a activar."
    )
    await send_text(user, text)
    await send_voice(user, text, user_key)


async def show_voices(user: dict, user_key: str):
    lines = ["Elegí una voz y mandame, por ejemplo, /voz 2:", ""]
    for index, (voice, label) in enumerate(VOICE_ITEMS, start=1):
        mark = " (actual)" if selected_voice[user_key] == voice else ""
        lines.append(f"{index}. {label}{mark}")
    await send_text(user, "\n".join(lines))


async def handle_message(message: dict, contact: dict):
    user = {
        "wa_id": message.get("from") or contact.get("wa_id"),
        "bsuid": message.get("from_user_id") or contact.get("user_id"),
    }
    user_key = user["bsuid"] or user["wa_id"]
    if not user_key:
        return
    text = message.get("text", {}).get("body", "").strip()
    try:
        if text.startswith("/start") or text.startswith("/ayuda"):
            await welcome(user, user_key)
            return
        if text.startswith("/voces"):
            await show_voices(user, user_key)
            return
        match = re.fullmatch(r"/?voz\s+(\d{1,2})", text, re.IGNORECASE)
        if match:
            index = int(match.group(1))
            if not 1 <= index <= len(VOICE_ITEMS):
                await send_text(user, f"Elegí un número del 1 al {len(VOICE_ITEMS)}. Usá /voces para ver la lista.")
                return
            voice, label = VOICE_ITEMS[index - 1]
            selected_voice[user_key] = voice
            voice_enabled[user_key] = True
            sample = f"Elegiste {label}. Así sueno ahora. Mandame un mensaje o un audio y seguimos probando."
            await send_text(user, sample)
            await send_voice(user, sample, user_key)
            return
        if text.startswith("/solo_texto"):
            voice_enabled[user_key] = False
            await send_text(user, "Audio desactivado. Te respondo solo por texto. Usá /con_voz para activarlo.")
            return
        if text.startswith("/con_voz"):
            voice_enabled[user_key] = True
            await send_text(user, "Audio activado.")
            await send_voice(user, "Audio activado. Ya te respondo también por voz.", user_key)
            return
        if text.startswith("/reset"):
            histories[user_key].clear()
            await send_text(user, "Conversación reiniciada.")
            return
        if message.get("type") == "audio":
            user_text = await transcribe(message["audio"]["id"])
            if not user_text:
                await send_text(user, "No pude entender el audio. Probá grabarlo de nuevo.")
                return
        elif message.get("type") == "text" and text:
            user_text = text
        else:
            await send_text(user, "Por ahora puedo responder mensajes de texto y audios.")
            return
        result = await answer(user_key, user_text)
        await send_text(user, result)
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


@app.get("/")
async def health():
    return {"ok": True, "service": "cafe-sabroso-whatsapp"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("Verification failed", status_code=403)


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    expected = "sha256=" + hmac.new(WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return PlainTextResponse("Invalid signature", status_code=401)
    update = await request.json()
    asyncio.create_task(process_update(update))
    return {"ok": True}


@app.on_event("shutdown")
async def shutdown():
    await http.aclose()
