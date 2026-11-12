import asyncio
import gc
import logging
import os
import random
import re
import sqlite3
import tempfile
import time
import unicodedata
import urllib.parse as urllib_parse
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from pathlib import Path

import edge_tts
import httpx
from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO)
# httpx includes Telegram's bot token in request URLs at INFO level.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)
log = logging.getLogger("telegram-voice-bot")

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
# Hosted transcription: much faster than local whisper on Render's shared CPU.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/cafe_sabroso.db")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
TELEGRAM_FILE = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}"

# Screen-reader style voices synthesized locally with eSpeak-NG (the NVDA
# default and the free stand-in for the proprietary Eloquence voice in JAWS),
# keyed apart from the Edge TTS IDs so synthesize can route them.
ESPEAK_VOICES = {
    "espeak-es-419": {"espeak_voice": "es-419", "rate": 175},
    "espeak-es-419-m1": {"espeak_voice": "es-419+m1", "rate": 175},
    "espeak-es-419-m3": {"espeak_voice": "es-419+m3", "rate": 175},
    "espeak-es-419-f1": {"espeak_voice": "es-419+f1", "rate": 175},
    "espeak-es-419-f2": {"espeak_voice": "es-419+f2", "rate": 175},
}
# Free Piper neural voices synthesized locally in the container, keyed apart
# from the Edge TTS IDs so synthesize can route them.
# Only "medium" piper models: the "high" ones (daniela, claude) need ~215 MB
# per synthesis and OOM-crashed on Render's 512 MB plan, silently killing
# game voice notes.
PIPER_VOICES = {
    "piper-es-mx-ald": {"model": "es_MX-ald-medium"},
    "piper-es-es-davefx": {"model": "es_ES-davefx-medium"},
    "piper-es-es-sharvard": {"model": "es_ES-sharvard-medium"},
}
PIPER_DIR = Path(os.environ.get("PIPER_DIR", "/app/piper-voices"))
RHVOICE_VOICES = {
    "rhvoice-mateo": {"rhvoice_voice": "Mateo"},
}
RHVOICE_BIN = os.environ.get("RHVOICE_BIN", "/opt/rhvoice/bin/RHVoice-test")
VOICES = {
    "espeak-es-419": "Voz Lector 1 - estilo NVDA",
    "espeak-es-419-m1": "Voz Lector 2 - estilo NVDA, masculina",
    "espeak-es-419-m3": "Voz Lector 3 - estilo NVDA, grave",
    "espeak-es-419-f1": "Voz Lector 4 - estilo NVDA, femenina",
    "espeak-es-419-f2": "Voz Lector 5 - estilo NVDA, aguda",
    "piper-es-mx-ald": "Ald - México (Piper)",
    "piper-es-es-davefx": "Davefx - España (Piper)",
    "piper-es-es-sharvard": "Sharvard - España (Piper)",
    "rhvoice-mateo": "Mateo RH - voz de la comunidad ciega (RHVoice)",
    "es-AR-TomasNeural": "Tomás - argentino",
    "es-AR-ElenaNeural": "Elena - argentina",
    "es-MX-JorgeNeural": "Jorge - México",
    "es-MX-DaliaNeural": "Dalia - México",
    "es-CO-GonzaloNeural": "Gonzalo - Colombia",
    "es-CO-SalomeNeural": "Salome - Colombia",
    "es-CL-LorenzoNeural": "Lorenzo - Chile",
    "es-CL-CatalinaNeural": "Catalina - Chile",
    "es-UY-MateoNeural": "Mateo - Uruguay",
    "es-UY-ValentinaNeural": "Valentina - Uruguay",
    "es-PE-AlexNeural": "Alex - Perú",
    "es-PE-CamilaNeural": "Camila - Perú",
    "es-VE-SebastianNeural": "Sebastián - Venezuela",
    "es-VE-PaolaNeural": "Paola - Venezuela",
    "es-BO-MarceloNeural": "Marcelo - Bolivia",
    "es-BO-SofiaNeural": "Sofía - Bolivia",
    "es-CR-JuanNeural": "Juan - Costa Rica",
    "es-CR-MariaNeural": "María - Costa Rica",
    "es-EC-LuisNeural": "Luis - Ecuador",
    "es-EC-AndreaNeural": "Andrea - Ecuador",
    "es-PY-MarioNeural": "Mario - Paraguay",
    "es-PY-TaniaNeural": "Tania - Paraguay",
    "es-PR-VictorNeural": "Víctor - Puerto Rico",
    "es-PR-KarinaNeural": "Karina - Puerto Rico",
    "es-DO-EmilioNeural": "Emilio - República Dominicana",
    "es-DO-RamonaNeural": "Ramona - República Dominicana",
    "es-CU-ManuelNeural": "Manuel - Cuba",
    "es-CU-BelkysNeural": "Belkys - Cuba",
    "es-GT-AndresNeural": "Andrés - Guatemala",
    "es-GT-MartaNeural": "Marta - Guatemala",
    "es-HN-CarlosNeural": "Carlos - Honduras",
    "es-HN-KarlaNeural": "Karla - Honduras",
    "es-NI-FedericoNeural": "Federico - Nicaragua",
    "es-NI-YolandaNeural": "Yolanda - Nicaragua",
    "es-PA-RobertoNeural": "Roberto - Panamá",
    "es-PA-MargaritaNeural": "Margarita - Panamá",
    "es-SV-RodrigoNeural": "Rodrigo - El Salvador",
    "es-SV-LorenaNeural": "Lorena - El Salvador",
    "es-ES-ElviraNeural": "Elvira - España",
    "es-ES-XimenaNeural": "Ximena - España",
    "es-GQ-TeresaNeural": "Teresa - España (Guinea Ecuatorial)",
}
DEFAULT_VOICE = "es-AR-TomasNeural"
SYSTEM_PROMPT = (
    "Sos un asistente de IA general, útil, claro y cálido. Respondés en español "
    "rioplatense por defecto, salvo que la persona pida otro idioma. Tus respuestas "
    "se escuchan como notas de voz: usá frases naturales, evitá tablas y formato "
    "visual, y andá directo al punto. Para preguntas cotidianas, respondé en menos "
    "de 120 palabras. Si una respuesta necesita más detalle, dá primero un resumen "
    "breve y ofrecé seguir. No inventes datos actuales; si no sabés algo, decilo. "
    "Devolvé únicamente la respuesta final. Nunca muestres análisis, razonamientos, "
    "pasos, listas de consignas ni explicaciones sobre cómo respondiste. Andá directo "
    "al contenido: no saludes, no uses el nombre guardado de la persona y no repitas "
    "fórmulas como 'Hola' o '¿en qué te puedo ayudar?' en cada respuesta. Si la persona "
    "pide una presentación, respondé a ese pedido de forma natural."
)

app = FastAPI(title="Telegram Spanish Voice AI Bot")
selected_voice = defaultdict(lambda: DEFAULT_VOICE)
voice_enabled = defaultdict(lambda: True)
histories = defaultdict(lambda: deque(maxlen=12))
duo_enabled = defaultdict(lambda: False)
duo_pairs = {}
trio_enabled = defaultdict(lambda: False)
trio_pairs = {}
quartet_enabled = defaultdict(lambda: False)
quartet_pairs = {}
quintet_enabled = defaultdict(lambda: False)
quintet_pairs = {}
sextet_enabled = defaultdict(lambda: False)
sextet_pairs = {}
septet_enabled = defaultdict(lambda: False)
septet_pairs = {}
octet_enabled = defaultdict(lambda: False)
octet_pairs = {}
nonet_enabled = defaultdict(lambda: False)
nonet_pairs = {}
decet_enabled = defaultdict(lambda: False)
decet_pairs = {}
story_enabled = defaultdict(lambda: False)
story_pairs = {}
GROUP_MODE_SIZES = {
    "duo": 2, "trio": 3, "quartet": 4, "quintet": 5, "sextet": 6,
    "septet": 7, "octet": 8, "nonet": 9, "decet": 10, "story": 4,
    "trivia": 3,
}
GROUP_MODE_LABELS = {
    "duo": "dúo", "trio": "trío", "quartet": "cuarteto",
    "quintet": "quinteto", "sextet": "sexteto", "septet": "sépteto",
    "octet": "octeto", "nonet": "noneto", "decet": "deceto", "story": "historia",
    "trivia": "ruleta",
}
GROUP_MODE_FLAGS = {
    "duo": (duo_enabled, duo_pairs),
    "trio": (trio_enabled, trio_pairs),
    "quartet": (quartet_enabled, quartet_pairs),
    "quintet": (quintet_enabled, quintet_pairs),
    "sextet": (sextet_enabled, sextet_pairs),
    "septet": (septet_enabled, septet_pairs),
    "octet": (octet_enabled, octet_pairs),
    "nonet": (nonet_enabled, nonet_pairs),
    "decet": (decet_enabled, decet_pairs),
    "story": (story_enabled, story_pairs),
}
# Conversation modes where the voices address each other by name; story is a
# narration with its own prompt.
DIALOGUE_KINDS = (
    "duo", "trio", "quartet", "quintet", "sextet",
    "septet", "octet", "nonet", "decet",
)


def clear_group_modes(chat_id: int):
    for flags, _ in GROUP_MODE_FLAGS.values():
        flags[chat_id] = False
group_selection = {}
pending_weather_query = {}
pending_weather_country = {}
pending_sports_query = {}
pending_music_query = {}
awaiting_name = defaultdict(lambda: False)
pending_action = {}
http = httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=20.0))
BOT_COMMANDS = [
    {"command": "menu", "description": "Abrir el menú principal"},
    {"command": "individual", "description": "Elegir una sola voz"},
    {"command": "voces", "description": "Ver todas las voces"},
    {"command": "duo", "description": "Conversar con dos voces"},
    {"command": "trio", "description": "Conversar con tres voces"},
    {"command": "cuarteto", "description": "Conversar con cuatro voces"},
    {"command": "quinteto", "description": "Conversar con cinco voces"},
    {"command": "sexteto", "description": "Conversar con seis voces"},
    {"command": "septeto", "description": "Conversar con siete voces"},
    {"command": "octeto", "description": "Conversar con ocho voces"},
    {"command": "noneto", "description": "Conversar con nueve voces"},
    {"command": "deceto", "description": "Conversar con diez voces"},
    {"command": "historia", "description": "Crear una historia con cuatro personajes"},
    {"command": "juegos", "description": "Abrir el apartado de juegos"},
    {"command": "musica", "description": "Buscar un artista o una canción"},
    {"command": "nombre", "description": "Cambiar cómo te llama el bot"},
    {"command": "solo_texto", "description": "Desactivar las respuestas de audio"},
    {"command": "con_voz", "description": "Activar las respuestas de audio"},
    {"command": "reset", "description": "Reiniciar la conversación"},
]
whisper_model = None
whisper_lock = asyncio.Lock()
# Local piper models use a few hundred MB of RAM and cannot coexist with the
# cached whisper model on the 512 MB free plan: one lock serializes local TTS
# and voice-note transcription so the two never load at the same time.
piper_lock = asyncio.Semaphore(1)

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
    result = None
    for chunk in chunks:
        result = await telegram("sendMessage", chat_id=chat_id, text=chunk, **kwargs)
    return result


def speech_text(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[*_`#>]", "", text)
    return text.strip()[:5000]


# When a voice engine fails, the beat still gets read aloud: fall back to a
# free neural voice (edge-tts), then to fully-local eSpeak. A blind user must
# never get a silent beat.
FALLBACK_VOICES = ("es-AR-ElenaNeural", "espeak-es-419")


async def synthesize(text: str, voice: str) -> bytes:
    try:
        return await synthesize_once(text, voice)
    except Exception:
        log.exception("Voice %s failed; trying fallback voices", voice)
    for fallback in FALLBACK_VOICES:
        if fallback == voice:
            continue
        try:
            return await synthesize_once(text, fallback)
        except Exception:
            log.exception("Fallback voice %s failed too", fallback)
    raise RuntimeError(f"Every voice engine failed for: {text[:80]}")


async def synthesize_once(text: str, voice: str) -> bytes:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "reply.src"
        ogg = Path(directory) / "reply.ogg"
        if voice in ESPEAK_VOICES:
            config = ESPEAK_VOICES[voice]
            process = await asyncio.create_subprocess_exec(
                "espeak-ng", "-v", config["espeak_voice"], "-s", str(config["rate"]),
                "--stdin", "-w", str(source),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate(speech_text(text).encode())
            if process.returncode:
                raise RuntimeError(f"espeak-ng failed: {stderr.decode()[:600]}")
        elif voice in PIPER_VOICES:
            global whisper_model
            model = PIPER_VOICES[voice]["model"]
            async with piper_lock:
                # Free the cached whisper model first: Render's free 512 MB plan
                # cannot hold whisper and a local piper model at the same time.
                if whisper_model is not None:
                    whisper_model = None
                    gc.collect()
                    log.info("Unloaded whisper model to free memory for piper")
                process = await asyncio.create_subprocess_exec(
                    "python3", "-m", "piper",
                    "--model", str(PIPER_DIR / f"{model}.onnx"),
                    "--config", str(PIPER_DIR / f"{model}.onnx.json"),
                    "--output_file", str(source),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await process.communicate(speech_text(text).encode())
            if process.returncode:
                raise RuntimeError(f"piper failed: {stderr.decode()[:1200]}")
        elif voice in RHVOICE_VOICES:
            process = await asyncio.create_subprocess_exec(
                RHVOICE_BIN, "-p", RHVOICE_VOICES[voice]["rhvoice_voice"],
                "-o", str(source),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate(speech_text(text).encode())
            if process.returncode:
                raise RuntimeError(f"rhvoice failed: {stderr.decode()[:600]}")
        else:
            await edge_tts.Communicate(speech_text(text), voice).save(str(source))
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-c:a", "libopus", "-b:a", "48k", "-ac", "1", str(ogg),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()[:300]}")
        return ogg.read_bytes()


async def send_voice(chat_id: int, text: str, voice: str = None):
    if not voice_enabled[chat_id]:
        return
    try:
        await telegram("sendChatAction", chat_id=chat_id, action="upload_voice")
        audio = await synthesize(text, voice or selected_voice[chat_id])
        response = await http.post(
            f"{TELEGRAM_API}/sendVoice",
            data={"chat_id": str(chat_id)},
            files={"voice": ("reply.ogg", audio, "audio/ogg")},
        )
        if response.status_code >= 400:
            log.error("Telegram sendVoice failed: %s %s", response.status_code, response.text[:500])
        response.raise_for_status()
        log.info("Sent individual voice message for chat %s", chat_id)
        return (response.json().get("result") or {}).get("message_id")
    except Exception:
        log.exception("Could not synthesize or send voice")
    return None


async def complete_openrouter(messages):
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "X-Title": "Cafe Sabroso"}
    if PUBLIC_URL:
        headers["HTTP-Referer"] = PUBLIC_URL
    for max_tokens in (1200, 2400):
        response = await http.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": OPENROUTER_MODEL,
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": max_tokens,
                "reasoning": {"effort": "low", "exclude": True},
                "provider": {"require_parameters": True},
            },
        )
        if response.status_code >= 400:
            log.error("OpenRouter chat failed: %s %s", response.status_code, response.text[:500])
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"].get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        truncated = choice.get("finish_reason") == "length"
        if content and content.strip() and not truncated:
            return content.strip()
        if truncated and max_tokens < 2400:
            log.warning("OpenRouter used the response budget; retrying with a larger budget")
            continue
        if not content or not content.strip():
            log.error("OpenRouter returned empty content: %s", str(data)[:500])
            raise RuntimeError("OpenRouter returned an empty response")
        log.error("OpenRouter truncated the visible response: %s", str(data)[:500])
        raise RuntimeError("OpenRouter truncated the response")
    raise RuntimeError("OpenRouter returned no usable response")


async def complete_pollinations(messages):
    """Anonymous free fallback; do not send an Authorization header."""
    for attempt in range(2):
        response = await http.post(
            "https://text.pollinations.ai/openai",
            json={
                "model": "openai-fast",
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 2400,
                "stream": False,
            },
        )
        if response.status_code in (402, 429) and attempt == 0:
            match = re.search(r"Retry after (\d+)s", response.text, re.IGNORECASE)
            delay = int(match.group(1)) if match else 45
            delay = min(max(delay, 1), 50)
            log.warning("Pollinations free slot opens in %s seconds; waiting once", delay)
            await asyncio.sleep(delay)
            continue
        if response.status_code >= 400:
            log.error("Pollinations chat failed: %s %s", response.status_code, response.text[:500])
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"].get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if content and content.strip() and choice.get("finish_reason") != "length":
            return content.strip()
        raise RuntimeError("Pollinations returned no usable response")
    raise RuntimeError("Pollinations free fallback remained rate limited")


async def complete(messages):
    try:
        return await complete_openrouter(messages)
    except Exception as error:
        log.warning("OpenRouter unavailable (%s); using free fallback", type(error).__name__)
    return await complete_pollinations(messages)


def voice_name(voice: str) -> str:
    return VOICES[voice].split(" - ", 1)[0]


def name_pattern(name: str) -> str:
    """Accent-insensitive regex for one voice-name label (Sofia matches Sofía)."""
    variants = {"a": "aá", "e": "eé", "i": "ií", "o": "oó", "u": "uú", "n": "nñ"}
    parts = []
    for char in name:
        base = unicodedata.normalize("NFD", char)[0].lower()
        if base in variants:
            parts.append("[" + variants[base] + "]")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


def clean_turn(text: str, names) -> str:
    label = "(?:" + "|".join(name_pattern(name) for name in names) + ")"
    text = re.sub(rf"^\s*{label}\s*:\s*", "", text, count=1, flags=re.IGNORECASE)
    text = re.split(rf"\n\s*{label}\s*:\s*", text, maxsplit=1, flags=re.IGNORECASE)[0]
    return text.strip()


async def synthesize_turns(turns):
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


async def send_group_voice(chat_id: int, turns):
    if not voice_enabled[chat_id]:
        return
    try:
        await telegram("sendChatAction", chat_id=chat_id, action="upload_voice")
        audio = await synthesize_turns(turns)
        response = await http.post(
            f"{TELEGRAM_API}/sendVoice",
            data={"chat_id": str(chat_id)},
            files={"voice": ("duo.ogg", audio, "audio/ogg")},
        )
        if response.status_code >= 400:
            log.error("Telegram duo sendVoice failed: %s %s", response.status_code, response.text[:500])
        response.raise_for_status()
        log.info("Sent joined %s-turn voice message for chat %s", len(turns), chat_id)
    except Exception:
        log.exception("Could not synthesize or send duo voice")


async def answer(chat_id: int, user_text: str):
    history = histories[chat_id]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    result = await complete(messages)
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": result})
    return result


def parse_group_turns(text: str, names):
    """Read the labeled turns returned by one shared group completion."""
    text = text.strip().replace("**", "")
    labels = "|".join(name_pattern(name) for name in names)
    matches = list(re.finditer(rf"(?mi)^\s*(?:[-•]\s+)?({labels})\s*(?::|\s+-\s+)\s*", text))
    if not matches:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if len(paragraphs) == len(names):
            return [clean_turn(part, names) for part in paragraphs]
        return None
    if len(matches) != len(names):
        return None
    if [normalized(match.group(1)) for match in matches] != [normalized(name) for name in names]:
        return None
    replies = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        reply = clean_turn(text[match.end():end].strip(), names)
        if not reply:
            return None
        replies.append(reply)
    return replies


async def answer_group_sequential(chat_id: int, user_text: str, voices):
    """Compatibility fallback when a model does not follow the group format."""
    history = histories[chat_id]
    names = [voice_name(voice) for voice in voices]
    replies = []
    for index, speaker in enumerate(names):
        if index == 0:
            role = "Respondé primero, de forma útil y concreta."
        elif index == 1:
            role = f"{names[0]} ya habló. Aportá una idea complementaria, un ejemplo o un matiz sin repetirlo."
        elif index == 2:
            role = f"{names[0]} y {names[1]} ya hablaron. Sumá una idea práctica o un ejemplo sin repetirlos."
        else:
            role = f"{', '.join(names[:-1])} ya hablaron. Cerrá con una síntesis o recomendación sin repetirlos."
        prompt = (
            SYSTEM_PROMPT
            + f" En esta conversación de {len(voices)} voces sos {speaker}. {role} "
            "Podés reaccionar naturalmente a los comentarios anteriores. Escribí únicamente "
            "el texto final hablado de tu turno, sin análisis ni rótulos. Usá un máximo "
            "de 60 palabras. No anuncies que sos una IA. No te presentes salvo que la "
            "persona pida presentaciones; en ese caso, presentate con tu nombre y una "
            "descripción breve."
        )
        messages = [{"role": "system", "content": prompt}]
        messages.extend(history)
        previous = "\n\n".join(f"{speaker_name} respondió: {reply}" for speaker_name, reply in zip(names, replies))
        content = user_text
        if previous:
            content += f"\n\n{previous}\n\nAhora respondé vos como {speaker}."
        messages.append({"role": "user", "content": content})
        reply = clean_turn(await complete(messages), names)
        if not reply:
            reply = clean_turn(await complete(messages), names)
        if not reply:
            reply = "Perdón, se me cortó la voz. ¿Me repetís?"
        replies.append(reply)
    history.append({"role": "user", "content": user_text})
    history.append({
        "role": "assistant",
        "content": "\n".join(f"{speaker}: {reply}" for speaker, reply in zip(names, replies)),
    })
    return replies


async def answer_group(chat_id: int, user_text: str, voices):
    history = histories[chat_id]
    names = [voice_name(voice) for voice in voices]
    labels = ", ".join(names)
    prompt = (
        SYSTEM_PROMPT
        + f" En esta conversación participan {len(voices)} voces: {labels}. "
        "Respondé al pedido con exactamente un turno por voz, en ese orden. "
        "La primera responde de forma útil y concreta; las siguientes aportan "
        "ideas complementarias sin repetir. Escribí cada turno en una línea que "
        "empiece con el nombre de la voz y dos puntos, por ejemplo 'Nombre: texto'. "
        "Usá un máximo de 60 palabras por turno. No agregues ningún otro rótulo. "
        "No anuncies que son IA. No incluyas presentaciones salvo que la persona "
        "las pida; en ese caso, cada voz se presenta con su nombre y una descripción breve."
    )
    messages = [{"role": "system", "content": prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    replies = parse_group_turns(await complete(messages), names)
    if replies is None:
        return await answer_group_sequential(chat_id, user_text, voices)
    history.append({"role": "user", "content": user_text})
    history.append({
        "role": "assistant",
        "content": "\n".join(f"{speaker}: {reply}" for speaker, reply in zip(names, replies)),
    })
    return replies


async def answer_dialogue(chat_id: int, user_text: str, voices):
    """Group conversation: every voice speaks once and addresses another by name."""
    history = histories[chat_id]
    names = [voice_name(voice) for voice in voices]
    labels = ", ".join(names)
    word_limit = 60 if len(voices) <= 2 else (45 if len(voices) <= 6 else 30)
    user_name = get_preferred_name(chat_id)
    if user_name:
        address_line = (
            f" Hablan con {user_name}: dirigite a esa persona por su nombre, respondé "
            "a lo que dice e invitala a seguir participando."
        )
    else:
        address_line = (
            " Dirigite también a la persona que escribe: respondé a lo que dice e "
            "invitala a seguir participando."
        )
    prompt = (
        SYSTEM_PROMPT
        + f" En esta conversación participan {len(voices)} voces: {labels}."
        + address_line
        + " Respondé al pedido como una conversación entre ellas: cada una habla exactamente "
        f"una vez, en ese orden. Si la persona nombró a una voz en particular, {names[0]} "
        "le pasa la palabra a esa voz y esa voz le responde directamente a la persona en "
        "su turno, llamándola por su nombre. Si no nombró a ninguna, "
        f"{names[0]} responde al pedido y se dirige a {names[1]} "
        "por su nombre, comentándole algo o haciéndole una pregunta. Cada una de las "
        "siguientes le contesta a la voz que la nombró o se dirige a otra, siempre "
        "llamándola por su nombre, y aporta algo nuevo sin repetir. La última cierra la idea. "
        "Escribí cada turno en una línea que empiece con el nombre de la voz y dos puntos, "
        f"por ejemplo 'Nombre: texto'. Usá un máximo de {word_limit} palabras por turno. "
        "No agregues ningún otro rótulo. No anuncies que son IA. No incluyas presentaciones "
        "salvo que la persona las pida; en ese caso, cada voz se presenta con su nombre "
        "y una descripción breve."
    )
    messages = [{"role": "system", "content": prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    replies = parse_group_turns(await complete(messages), names)
    if replies is None:
        return await answer_dialogue_sequential(chat_id, user_text, voices)
    history.append({"role": "user", "content": user_text})
    history.append({
        "role": "assistant",
        "content": "\n".join(f"{speaker}: {reply}" for speaker, reply in zip(names, replies)),
    })
    return replies


async def answer_dialogue_sequential(chat_id: int, user_text: str, voices):
    """Compatibility fallback when a model does not follow the dialogue format."""
    history = histories[chat_id]
    names = [voice_name(voice) for voice in voices]
    replies = []
    for index, speaker in enumerate(names):
        if index == 0:
            role = (
                f"Respondé primero al pedido y dirigite a {names[1]} por su nombre: "
                "comentale algo o hacéle una pregunta."
            )
        else:
            role = (
                f"Ya hablaron {', '.join(names[:index])}. Si alguna te nombró, respondéle "
                "a esa voz llamándola por su nombre; si no, dirigite a una de ellas por "
                "su nombre. Aportá una idea nueva sin repetir."
            )
            if index == len(names) - 1:
                role += " Cerrá la conversación con una idea final breve."
        user_name = get_preferred_name(chat_id)
        if user_name:
            address_line = (
                f" Hablan con {user_name}: dirigite a esa persona por su nombre y "
                "respondé a lo que dice. Si te nombró a vos, contestale directamente."
            )
        else:
            address_line = (
                " Dirigite también a la persona que escribe y respondé a lo que dice. "
                "Si te nombró a vos, contestale directamente."
            )
        prompt = (
            SYSTEM_PROMPT
            + f" En esta conversación de {len(voices)} voces ({', '.join(names)}) sos {speaker}.{address_line} {role} "
            "Podés reaccionar naturalmente a los comentarios anteriores. Escribí únicamente "
            "el texto final hablado de tu turno, sin análisis ni rótulos. Usá un máximo "
            "de 60 palabras. No anuncies que sos una IA. No te presentes salvo que la "
            "persona pida presentaciones; en ese caso, presentate con tu nombre y una "
            "descripción breve."
        )
        messages = [{"role": "system", "content": prompt}]
        messages.extend(history)
        previous = "\n\n".join(f"{speaker_name} respondió: {reply}" for speaker_name, reply in zip(names, replies))
        content = user_text
        if previous:
            content += f"\n\n{previous}\n\nAhora respondé vos como {speaker}."
        messages.append({"role": "user", "content": content})
        reply = clean_turn(await complete(messages), names)
        if not reply:
            reply = clean_turn(await complete(messages), names)
        if not reply:
            reply = "Perdón, se me cortó la voz. ¿Me repetís?"
        replies.append(reply)
    history.append({"role": "user", "content": user_text})
    history.append({
        "role": "assistant",
        "content": "\n".join(f"{speaker}: {reply}" for speaker, reply in zip(names, replies)),
    })
    return replies


async def answer_duo(chat_id: int, user_text: str):
    return await answer_dialogue(chat_id, user_text, duo_pairs[chat_id])


async def answer_trio(chat_id: int, user_text: str):
    return await answer_dialogue(chat_id, user_text, trio_pairs[chat_id])


async def answer_quartet(chat_id: int, user_text: str):
    return await answer_dialogue(chat_id, user_text, quartet_pairs[chat_id])


async def answer_quintet(chat_id: int, user_text: str):
    return await answer_dialogue(chat_id, user_text, quintet_pairs[chat_id])


async def answer_sextet(chat_id: int, user_text: str):
    return await answer_dialogue(chat_id, user_text, sextet_pairs[chat_id])


async def answer_story(chat_id: int, theme: str):
    voices = story_pairs[chat_id]
    names = [voice_name(voice) for voice in voices]
    history = histories[chat_id]
    replies = []
    for index, speaker in enumerate(names):
        stage = (
            "Empezá la escena y presentá la situación." if index == 0
            else "Continuá la escena a partir del diálogo anterior." if index == 1
            else "Sumá un giro o conflicto breve a la escena." if index == 2
            else "Cerrá esta escena con un desenlace breve."
        )
        prompt = (
            SYSTEM_PROMPT
            + f"Estamos contando una historia con cuatro personajes. Vos sos {speaker}. {stage} "
            "Escribí únicamente el diálogo hablado de tu personaje, en primera persona, sin rótulos ni narración "
            "entre comillas. No uses el nombre de quien escucha salvo que la historia lo "
            "necesite. Usá entre 35 y 55 palabras "
            "y mantené continuidad con los diálogos anteriores. No hables como asistente ni como IA."
        )
        messages = [{"role": "system", "content": prompt}]
        messages.extend(history)
        previous = "\n".join(f"{character}: {dialogue}" for character, dialogue in zip(names, replies))
        content = f"Tema de la historia: {theme}"
        if previous:
            content += f"\nDiálogos anteriores:\n{previous}"
        messages.append({"role": "user", "content": content})
        reply = clean_turn(await complete(messages), names)
        if not reply:
            reply = clean_turn(await complete(messages), names)
        if not reply:
            reply = "Perdón, se me cortó la voz. ¿Me repetís?"
        replies.append(reply)
    history.append({"role": "user", "content": f"Historia sobre: {theme}"})
    history.append({
        "role": "assistant",
        "content": "\n".join(f"{speaker}: {dialogue}" for speaker, dialogue in zip(names, replies)),
    })
    return replies


async def transcribe(file_id: str) -> str:
    global whisper_model
    info = await telegram("getFile", file_id=file_id)
    audio_response = await http.get(f"{TELEGRAM_FILE}/{info['file_path']}")
    audio_response.raise_for_status()
    suffix = Path(info["file_path"]).suffix or ".ogg"
    if GROQ_API_KEY:
        try:
            response = await http.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                data={"model": GROQ_WHISPER_MODEL, "language": "es", "response_format": "json"},
                files={"file": (f"telegram{suffix}", audio_response.content)},
                timeout=30,
            )
            if response.status_code < 400:
                text = (response.json().get("text") or "").strip()
                log.info("Transcribed %s audio bytes with Groq %s", len(audio_response.content), GROQ_WHISPER_MODEL)
                return text
            log.warning("Groq transcription failed: %s %s", response.status_code, response.text[:300])
        except Exception:
            log.exception("Groq transcription error; falling back to local Whisper")
    # Hold the shared lock for the whole transcription so whisper and local
    # piper never use memory at the same time.
    async with piper_lock:
        async with whisper_lock:
            if whisper_model is None:
                from faster_whisper import WhisperModel
                whisper_model = await asyncio.to_thread(
                    WhisperModel, WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=1
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


WEATHER_CODES = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
    45: "niebla", 48: "niebla con escarcha", 51: "llovizna leve", 53: "llovizna",
    55: "llovizna intensa", 56: "llovizna helada", 57: "llovizna helada intensa",
    61: "lluvia leve", 63: "lluvia", 65: "lluvia intensa", 66: "lluvia helada",
    67: "lluvia helada intensa", 71: "nevada leve", 73: "nevada", 75: "nevada intensa",
    77: "granos de nieve", 80: "chubascos leves", 81: "chubascos", 82: "chubascos fuertes",
    85: "chubascos de nieve", 86: "chubascos de nieve fuertes", 95: "tormenta",
    96: "tormenta con granizo", 99: "tormenta con granizo fuerte",
}


def normalized(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(char) != "Mn"
    )


def is_weather_query(text: str) -> bool:
    query = normalized(text)
    return any(word in query for word in (
        "clima", "temperatura", "pronostico", "lluvia", "llover", "nevada",
        "humedad", "viento", "que tiempo hace", "hace calor", "hace frio",
    ))


def weather_place(text: str):
    """Extract a place from a weather question or a conversational city reply."""
    text = text.strip(" ¿?¡!.,;")
    match = re.search(r"\b(?:en|para|de)\s+([^?!\n]{2,80})", text, re.IGNORECASE)
    place = match.group(1) if match else re.sub(r"^(?:pon[eé](?:me)?|mostr[aá](?:me)?|dame|clima|temperatura)\s+", "", text, flags=re.IGNORECASE)
    place = re.sub(r"^(?:el|la)\s+(?:de\s+)?", "", place, flags=re.IGNORECASE)
    place = re.sub(r"\b(?:hoy|mañana|manana|ahora|actualmente|por favor|esta semana)\b", "", place, flags=re.IGNORECASE)
    place = " ".join(place.split()).strip(" ,.;")
    if not place or is_weather_query(place):
        return None
    return place


class WeatherCountryRequired(ValueError):
    def __init__(self, name, code):
        super().__init__(f"¿De qué ciudad de {name} querés el clima actual? Un país no tiene una sola temperatura.")
        self.code = code


async def weather_context(place: str, question: str, country_code=None):
    response = await http.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": place[:80], "count": 10, "language": "es", "format": "json", **({"countryCode": country_code} if country_code else {})},
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise ValueError("No encontré ese lugar. Decime la ciudad, por ejemplo Quilmes.")
    for candidate in results:
        if candidate.get("feature_code") == "PCLI" and normalized(candidate.get("name", "")) == normalized(place):
            raise WeatherCountryRequired(candidate["name"], candidate.get("country_code"))
    cities = [x for x in results if x.get("feature_code", "").startswith("PPL") and (not country_code or x.get("country_code") == country_code)]
    if not cities:
        raise ValueError("Necesito una ciudad para consultar el clima actual. ¿Cuál querés?")
    location = cities[0]
    response = await http.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": location["latitude"], "longitude": location["longitude"],
                "current": "temperature_2m,weather_code", "timezone": "auto"},
    )
    response.raise_for_status()
    data = response.json()
    current = data.get("current", {})
    temperature = current.get("temperature_2m")
    code = current.get("weather_code")
    if not isinstance(temperature, (int, float)) or code not in WEATHER_CODES or not current.get("time"):
        raise ValueError("La fuente no devolvió temperatura y estado actuales completos. Probá de nuevo en un momento.")
    current_time = datetime.fromisoformat(current["time"]).strftime("%H:%M")
    label = ", ".join(str(x) for x in (location.get("name"), location.get("admin1"), location.get("country")) if x)
    degrees = f"{temperature:g}".replace(".", ",")
    condition = WEATHER_CODES[code]
    state = f"está {condition}" if code in {0, 1, 2, 3} else f"hay {condition}"
    text = f"En {label} {state} y la temperatura es de {degrees} grados Celsius. Datos de Open-Meteo de las {current_time}, hora local."
    return text, "https://open-meteo.com/"


SPORT_LEAGUES = (
    (("champions",), "soccer", "uefa.champions"),
    (("libertadores",), "soccer", "conmebol.libertadores"),
    (("premier",), "soccer", "eng.1"),
    (("la liga", "espana", "espanol"), "soccer", "esp.1"),
    (("argentina", "argentino"), "soccer", "arg.1"),
    (("nba",), "basketball", "nba"),
    (("nfl",), "football", "nfl"),
    (("mlb",), "baseball", "mlb"),
    (("nhl",), "hockey", "nhl"),
    (("futbol", "soccer"), "soccer", "all"),
)


def is_sports_query(text: str) -> bool:
    query = normalized(text)
    return any(word in query for word in (
        "partido", "resultado", "deporte", "futbol", "soccer", "nba", "nfl", "mlb", "nhl",
        "basquet", "basket", "hockey", "gano", "salio", "marcador", "juega", "juegan", "cuando juega",
    ))


async def sports_context(query_text: str):
    query = normalized(query_text)
    league = None
    for keywords, sport, slug in SPORT_LEAGUES:
        if any(keyword in query for keyword in keywords):
            league = (sport, slug)
            break
    if not league:
        raise ValueError("¿Qué deporte o liga te interesa? Por ejemplo, fútbol, NBA, NFL, MLB o NHL.")
    today = datetime.now(timezone.utc).date()
    if "ayer" in query:
        date = today - timedelta(days=1)
    elif "manana" in query:
        date = today + timedelta(days=1)
    else:
        date = today
    sport, slug = league
    source = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard"
    response = await http.get(source, params={"dates": date.strftime("%Y%m%d"), "limit": 100})
    response.raise_for_status()
    events = response.json().get("events", [])
    matching = []
    for event in events:
        competitors = event.get("competitions", [{}])[0].get("competitors", [])
        if any(normalized(c.get("team", {}).get("displayName", "")) in query for c in competitors):
            matching.append(event)
    if matching:
        events = matching
    elif any(word in query for word in ("gano", "salio", "juega", "juegan")):
        events = []
    if not events:
        raise ValueError("No encontré eventos para esa consulta en ESPN. Probá indicar equipo, liga y si buscás hoy, ayer o mañana.")
    month_names = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    relative_day = "hoy" if date == today else "ayer" if date == today - timedelta(days=1) else "mañana"
    readable_date = f"{relative_day}, {date.day} de {month_names[date.month - 1]} de {date.year}"
    lines = []
    for event in events[:5]:
        competition = event["competitions"][0]
        status = event.get("status", {}).get("type", {})
        state = status.get("state")
        label = "Programado" if state == "pre" else "Finalizado" if state == "post" else "En curso"
        detail = status.get("detail", "")
        if state == "in" and sport == "soccer":
            detail = f"minuto {status.get('displayClock') or detail}"
        elif state == "pre":
            detail = relative_day
        competitors = competition.get("competitors", [])
        if state == "pre":
            teams = " vs ".join(c.get("team", {}).get("displayName", "Equipo") for c in competitors)
            score = ""
        else:
            teams = " - ".join(
                f"{c.get('team', {}).get('displayName', 'Equipo')} {c.get('score', '?')}"
                for c in competitors
            )
            score = ""
        lines.append(f"{teams}; {label} ({detail}){score}")
    context = (
        f"Datos deportivos reales consultados ahora en el marcador de ESPN para {readable_date}: "
        + " | ".join(lines)
        + f"\nPregunta original: {query_text}\n"
        "Para deportes usá únicamente estos eventos, estados, marcadores y fechas; no inventes otros resultados "
        "ni estadísticas. La primera voz debe mencionar que los datos son de ESPN."
    )
    return context, source


def music_query_from_text(text: str):
    """Return a music query only for explicit listening/search requests."""
    stripped = text.strip()
    if normalized(stripped) in {
        "busca musica", "buscar musica", "escuchar musica", "quiero escuchar musica",
        "pone musica", "poner musica", "reproduci musica", "reproducir musica",
        "busca una cancion", "buscar una cancion", "busca canciones", "buscar canciones",
    }:
        return ""
    patterns = (
        r"^(?:busc[aá](?:me)?|buscar|encontr[aá](?:me)?|encontrar)\s+(?:(?:la|el|varias)\s+)?(?:canci[oó]n(?:es)?|tema|m[uú]sica)(?:\s+de)?\s+(.+)$",
        r"^(?:quiero\s+)?escuchar\s+(?:(?:la|el|una)\s+)?(?:(?:canci[oó]n(?:es)?|tema|m[uú]sica)(?:\s+de)?\s+)?(.+)$",
        r"^(?:pon[eé](?:me)?|poner|reproduc[ií](?:me)?|reproducir)\s+(?:(?:la|el|una)\s+)?(?:(?:canci[oó]n(?:es)?|tema|m[uú]sica)(?:\s+de)?\s+)?(.+)$",
        r"^(?:busc[aá](?:me)?|buscar|encontr[aá](?:me)?|encontrar)\s+(.+?)\s+en\s+(?:spotify|apple\s+music|internet\s+archive)$",
    )
    for pattern in patterns:
        match = re.match(pattern, stripped, flags=re.IGNORECASE)
        if match:
            query = match.group(1).strip(" .,;:!?")
            if normalized(query).startswith(("una historia", "historia", "un cuento", "cuento")):
                return None
            return query
    return None


def spotify_music_url(query: str):
    return "https://open.spotify.com/search/" + urllib_parse.quote(query, safe="")


def archive_music_url(query: str):
    return "https://archive.org/search?" + urllib_parse.urlencode({"query": query})


async def apple_music_results(query: str):
    term = re.sub(r"[,;:!?¿¡]", " ", query[:120])
    term = re.sub(r"\s+", " ", term).strip()
    last_error = None
    # Second attempt drops the country filter and declares the media type:
    # the narrow query occasionally comes back empty for known songs.
    for params in (
        {"term": term, "entity": "song", "limit": 10, "country": "AR"},
        {"term": term, "media": "music", "entity": "song", "limit": 10},
    ):
        try:
            response = await http.get(
                "https://itunes.apple.com/search", params=params, timeout=20,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            log.info("Apple Music search for %r returned %s results", term, len(results))
        except Exception as error:
            last_error = error
            log.warning("Apple Music search attempt failed: %s", error)
            continue
        tracks = []
        for item in results:
            url = item.get("trackViewUrl", "")
            if item.get("kind") != "song" or not url.startswith("https://music.apple.com/"):
                continue
            tracks.append({
                "title": str(item.get("trackName", "Canción"))[:180],
                "artist": str(item.get("artistName", "Artista"))[:180],
                "album": str(item.get("collectionName", ""))[:180],
                "url": url,
                "preview": item.get("previewUrl", "")
                if str(item.get("previewUrl", "")).startswith("https://") else None,
            })
        if tracks:
            query_normalized = normalized(term)
            tracks.sort(key=lambda track: (
                normalized(track["artist"]) != query_normalized,
                query_normalized not in normalized(track["artist"]),
                query_normalized not in normalized(track["title"]),
            ))
            return tracks[:5]
    if last_error is not None:
        raise last_error
    return []


def archive_license(license_url: str):
    """Accept only an explicit Creative Commons or public-domain license."""
    url = license_url.replace("http://", "https://", 1)
    if not url.startswith("https://creativecommons.org/"):
        return None
    if "/publicdomain/zero/" in url:
        return "CC0"
    if "/publicdomain/mark/" in url:
        return "Dominio público"
    match = re.search(r"/licenses/(by(?:-(?:nc|nd|sa))*)/([0-9.]+)/", url)
    if not match:
        return None
    return f"CC {match.group(1).upper()} {match.group(2)}"


async def archive_download(item: dict):
    identifier = str(item.get("identifier", ""))
    if not identifier or not re.fullmatch(r"[A-Za-z0-9_.-]+", identifier):
        return None
    response = await http.get(f"https://archive.org/metadata/{identifier}", timeout=20)
    response.raise_for_status()
    data = response.json()
    metadata = data.get("metadata", {})
    license_url = str(metadata.get("licenseurl", ""))
    license_name = archive_license(license_url)
    if not license_name:
        return None
    preferred_formats = {"VBR MP3": 0, "MP3": 1, "Ogg Vorbis": 2, "Opus": 3, "FLAC": 4, "WAVE": 5}
    files = [
        file for file in data.get("files", [])
        if file.get("format") in preferred_formats
        and str(file.get("private", "")).lower() not in ("true", "1")
        and file.get("name")
    ]
    if not files:
        return None
    files.sort(key=lambda file: (preferred_formats[file["format"]], file.get("source") != "original"))
    selected = files[0]
    try:
        size = int(str(selected.get("size") or 0))
    except ValueError:
        size = 0
    title = str(metadata.get("title") or item.get("title") or identifier)[:180]
    creator = metadata.get("creator") or item.get("creator") or "Autor no indicado"
    if isinstance(creator, list):
        creator = ", ".join(str(value) for value in creator)
    return {
        "title": title,
        "artist": str(creator)[:180],
        "license": license_name,
        "license_url": license_url.replace("http://", "https://", 1),
        "item_url": f"https://archive.org/details/{identifier}",
        "download_url": f"https://archive.org/download/{identifier}/{urllib_parse.quote(selected['name'])}",
        "file_name": selected["name"],
        "format": str(selected.get("format", "")),
        "size": size,
    }


async def licensed_music_downloads(query: str):
    # Plain words keep user text from changing the Archive query structure.
    terms = re.findall(r"[^\W_]+", query, flags=re.UNICODE)[:8]
    if not terms:
        return []
    archive_query = "collection:opensource_audio AND licenseurl:* AND (" + " AND ".join(terms) + ")"
    response = await http.get(
        "https://archive.org/advancedsearch.php",
        params=[
            ("q", archive_query), ("fl[]", "identifier"), ("fl[]", "title"),
            ("fl[]", "creator"), ("fl[]", "licenseurl"), ("rows", "5"),
            ("page", "1"), ("output", "json"),
        ],
        timeout=20,
    )
    response.raise_for_status()
    docs = response.json().get("response", {}).get("docs", [])
    candidates = [
        item for item in docs if archive_license(str(item.get("licenseurl", "")))
    ][:3]
    downloads = await asyncio.gather(
        *(archive_download(item) for item in candidates), return_exceptions=True,
    )
    return [item for item in downloads if isinstance(item, dict)]


# Telegram bots send files up to 50 MB; keep headroom for the transfer.
ARCHIVE_AUDIO_LIMIT = 40 * 1024 * 1024


async def send_archive_audio(chat_id: int, item: dict):
    """Send a licensed Internet Archive track as a direct Telegram file.

    Only items whose license archive_download already verified reach this
    function. The audio streams from archive.org straight into the chat as a
    one-off transfer; the bot does not copy, host or store it.
    """
    size = item.get("size") or 0
    if size and size > ARCHIVE_AUDIO_LIMIT:
        log.info("Archive track too large for direct send: %s bytes", size)
        return False
    name = str(item.get("file_name") or "audio.mp3")
    is_mp3 = name.lower().endswith(".mp3")
    try:
        async with http.stream(
            "GET", item["download_url"], timeout=120, follow_redirects=True
        ) as response:
            response.raise_for_status()
            declared = response.headers.get("content-length")
            if declared and int(declared) > ARCHIVE_AUDIO_LIMIT:
                log.info("Archive track too large for direct send: %s bytes", declared)
                return False
            chunks = []
            received = 0
            async for chunk in response.aiter_bytes(1 << 16):
                received += len(chunk)
                if received > ARCHIVE_AUDIO_LIMIT:
                    log.info("Archive track exceeded the direct-send limit while streaming")
                    return False
                chunks.append(chunk)
        payload = b"".join(chunks)
        if not payload:
            return False
        await telegram("sendChatAction", chat_id=chat_id, action="upload_document")
        caption = (
            f"{item['title']}\n{item['artist']}\n"
            f"Licencia: {item['license']}. Fuente: {item['item_url']}"
        )[:1000]
        if is_mp3:
            response = await http.post(
                f"{TELEGRAM_API}/sendAudio",
                data={
                    "chat_id": str(chat_id),
                    "title": item["title"][:180],
                    "performer": item["artist"][:180],
                    "caption": caption,
                },
                files={"audio": (name, payload, "audio/mpeg")},
                timeout=120,
            )
        else:
            response = await http.post(
                f"{TELEGRAM_API}/sendDocument",
                data={"chat_id": str(chat_id), "caption": caption},
                files={"document": (name, payload, "application/octet-stream")},
                timeout=120,
            )
        if response.status_code >= 400:
            log.error("Telegram archive audio failed: %s %s", response.status_code, response.text[:500])
            return False
        log.info("Sent licensed archive audio %s to chat %s", name, chat_id)
        return True
    except Exception:
        log.exception("Could not send archive audio")
        return False


async def search_music(chat_id: int, query: str):
    query = re.sub(r"\s+", " ", query).strip()[:120]
    if not query:
        pending_music_query[chat_id] = True
        await send_text(chat_id, "Decime el artista, la canción o ambos. Por ejemplo: Mercedes Sosa Alfonsina y el mar.")
        await send_voice(chat_id, "Decime el artista o la canción que querés buscar.")
        return
    apple_result, archive_result = await asyncio.gather(
        apple_music_results(query), licensed_music_downloads(query), return_exceptions=True,
    )
    tracks = apple_result if isinstance(apple_result, list) else []
    downloads = archive_result if isinstance(archive_result, list) else []
    if isinstance(apple_result, Exception):
        log.warning("Apple Music search failed: %s", apple_result)
    if isinstance(archive_result, Exception):
        log.warning("Internet Archive music search failed: %s", archive_result)
    if not tracks and not downloads:
        text = (
            f"No encontré fichas ni descargas con licencia para “{query}”. "
            "Podés abrir la búsqueda oficial en Spotify o Internet Archive."
            if not isinstance(apple_result, Exception)
            else "No pude consultar el catálogo ahora. Podés abrir la búsqueda oficial en Spotify o Internet Archive."
        )
        pending_music_query[chat_id] = True
        await send_text(chat_id, text + "\n\nPodés decirme otra canción o artista, o 'salir' para dejar la música.", reply_markup={"inline_keyboard": [
            [{"text": "Buscar en Spotify", "url": spotify_music_url(query)}],
            [{"text": "Buscar en Internet Archive", "url": archive_music_url(query)}],
        ]})
        if isinstance(apple_result, Exception):
            await send_voice(
                chat_id,
                "No pude consultar el catálogo ahora. Te dejo botones para abrir "
                "la búsqueda oficial en Spotify o en Internet Archive.",
            )
        else:
            await send_voice(
                chat_id,
                f"No encontré nada para {query}. Te dejo botones para abrir la "
                "búsqueda oficial en Spotify o en Internet Archive. "
                "Si querés, decime otra canción.",
            )
        return
    summary = f"Resultados de música para «{query}»."
    if tracks:
        summary += " Las fichas y muestras son de Apple Music; Spotify abre su búsqueda oficial."
    if downloads:
        summary += " Las descargas de Internet Archive tienen una licencia explícita y llegan como archivo MP3 directo."
    pending_music_query[chat_id] = True
    log.info(
        "Music search for %r: %s Apple tracks, %s licensed downloads",
        query, len(tracks), len(downloads),
    )
    await send_text(chat_id, summary + "\n\nPodés decirme otra canción o artista, o 'salir' para dejar la música.")
    total = len(tracks) + len(downloads)
    canciones = "una canción" if total == 1 else f"{total} canciones"
    top = tracks[0] if tracks else downloads[0]
    await send_voice(
        chat_id,
        f"Encontré {canciones} para {query}. El primero de la lista es "
        f"{top['title']}, de {top['artist']}. Te paso la lista abajo: cada ficha "
        "tiene botones para escuchar la muestra, abrir Spotify o descargar el MP3. "
        "Podés pedirme otra canción cuando quieras.",
    )
    for track in tracks:
        spotify_url = spotify_music_url(f"{track['artist']} {track['title']}")
        share_url = "https://t.me/share/url?" + urllib_parse.urlencode({
            "url": track["url"], "text": f"{track['title']} - {track['artist']}",
        })
        rows = [
            [{"text": "▶️ Apple Music", "url": track["url"]}, {"text": "Spotify", "url": spotify_url}],
            [{"text": "Compartir", "url": share_url}],
        ]
        if track["preview"]:
            rows.append([{"text": "Escuchar muestra oficial", "url": track["preview"]}])
        album = f"\nÁlbum: {track['album']}" if track["album"] else ""
        await send_text(
            chat_id, f"🎵 {track['title']}\n{track['artist']}{album}",
            reply_markup={"inline_keyboard": rows},
        )
    for item in downloads:
        if await send_archive_audio(chat_id, item):
            await send_text(
                chat_id,
                f"⬇️ {item['title']} llegó como archivo directo. Licencia: {item['license']}; la descarga la ofrece Internet Archive y no copio ni almaceno el archivo.",
                reply_markup={"inline_keyboard": [
                    [{"text": "Ver licencia", "url": item["license_url"]}, {"text": "Ficha y fuente", "url": item["item_url"]}],
                ]},
            )
        else:
            await send_text(
                chat_id,
                f"⬇️ {item['title']}\n{item['artist']}\nLicencia: {item['license']}. No pude adjuntar el archivo; la descarga la ofrece Internet Archive desde la fuente.",
                reply_markup={"inline_keyboard": [
                    [{"text": "Escuchar o descargar desde la fuente", "url": item["download_url"]}],
                    [{"text": "Ver licencia", "url": item["license_url"]}, {"text": "Ficha y fuente", "url": item["item_url"]}],
                ]},
            )


async def prepare_live_query(chat_id: int, user_text: str):
    if chat_id in pending_weather_query or is_weather_query(user_text):
        if normalized(user_text).strip(" .!¿?") in {"salir", "cancelar", "basta"}:
            pending_weather_query.pop(chat_id, None)
            pending_weather_country.pop(chat_id, None)
            return "ask", "Listo, dejamos la consulta del clima.", None
        original = pending_weather_query.get(chat_id, user_text)
        place = weather_place(user_text)
        if not place:
            pending_weather_query[chat_id] = original
            return "ask", "¿Para qué ciudad querés saber el clima actual?", None
        try:
            context, source = await weather_context(place, original, pending_weather_country.get(chat_id))
            pending_weather_query.pop(chat_id, None)
            pending_weather_country.pop(chat_id, None)
            return "ready", context, source
        except WeatherCountryRequired as error:
            pending_weather_query[chat_id] = original
            pending_weather_country[chat_id] = error.code
            return "ask", str(error), None
        except ValueError as error:
            pending_weather_query[chat_id] = original
            return "ask", str(error), None
        except Exception:
            pending_weather_query[chat_id] = original
            log.exception("Open-Meteo lookup failed")
            return "ask", "No pude consultar Open-Meteo ahora. Probá de nuevo en un momento.", None
    if chat_id in pending_sports_query:
        original = pending_sports_query.pop(chat_id)
        combined = f"{original} {user_text}"
        try:
            context, source = await sports_context(combined)
            return "ready", context, source
        except ValueError as error:
            pending_sports_query[chat_id] = original
            return "ask", str(error), None
        except Exception:
            log.exception("ESPN lookup failed")
            return "ask", "No pude consultar ESPN ahora. Probá de nuevo en un momento.", None
    if is_sports_query(user_text):
        try:
            context, source = await sports_context(user_text)
            return "ready", context, source
        except ValueError as error:
            pending_sports_query[chat_id] = user_text
            return "ask", str(error), None
        except Exception:
            log.exception("ESPN lookup failed")
            return "ask", "No pude consultar ESPN ahora. Probá de nuevo en un momento.", None
    return "none", user_text, None


def voice_keyboard(chat_id: int, prefix: str, exclude=None):
    excluded = {exclude} if isinstance(exclude, str) else set(exclude or ())
    keyboard = []
    for voice, label in VOICES.items():
        if voice in excluded:
            continue
        mark = "✓ " if prefix == "voice" and selected_voice[chat_id] == voice else ""
        keyboard.append([{"text": mark + label, "callback_data": f"{prefix}:{voice}"}])
    return keyboard


async def show_voices(chat_id: int):
    keyboard = voice_keyboard(chat_id, "voice")
    keyboard.append([{"text": "⬅️ Volver al menú principal", "callback_data": "mode:menu"}])
    await send_text(
        chat_id,
        "🎙️ ELEGIR UNA VOZ\nPulsa el nombre de una voz en los botones de abajo. Después te envío una muestra.",
        reply_markup={"inline_keyboard": keyboard},
    )


async def ask_preferred_name(chat_id: int, action="mode"):
    awaiting_name[chat_id] = True
    pending_action[chat_id] = action
    await send_text(
        chat_id,
        "👋 PASO 1 DE 2: TU NOMBRE\n"
        "Antes de mostrarte el menú, ¿cómo quieres que te llame? "
        "Escribe solamente tu nombre o dilo en un audio. Después verás los botones para elegir una o varias voces.",
    )


async def start_group_mode(chat_id: int, kind: str):
    trivia_games.pop(chat_id, None)
    group_selection[chat_id] = {"kind": kind, "voices": []}
    own = selected_voice[chat_id]
    await send_text(
        chat_id,
        f"¿Sumás tu voz actual ({voice_name(own)}) a la conversación? "
        "Tu voz sería una de las que charlan entre ellas.",
        reply_markup={"inline_keyboard": [[
            {"text": f"🙋 Sí, sumar a {voice_name(own)}", "callback_data": f"gself:{kind}:yes"},
            {"text": "🎙️ No, elijo todas", "callback_data": f"gself:{kind}:no"},
        ]]},
    )


async def pick_group_voices(chat_id: int, kind: str, include_self: bool):
    session = group_selection.get(chat_id) or {"kind": kind, "voices": []}
    session["kind"] = kind
    group_selection[chat_id] = session
    if include_self:
        own = selected_voice[chat_id]
        if own not in session["voices"]:
            session["voices"].insert(0, own)
    voices = session["voices"]
    size = GROUP_MODE_SIZES[kind]
    numbers = {
        2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis",
        7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
    }
    if kind == "trivia":
        text = (
            "Ruleta: elige la primera de tres voces distintas para el juego. "
            "La primera presenta la ruleta, la segunda lee las preguntas y la tercera reacciona."
        )
    elif kind == "story":
        text = "Modo historia: elige la primera de cuatro voces distintas. Serán cuatro personajes que continúan una misma escena."
    elif kind == "duo":
        text = "Modo dúo: elige la primera voz. Después elegirás la segunda y conversarán entre ellas en un solo audio."
    else:
        text = (
            f"Modo {GROUP_MODE_LABELS[kind]}: elige la primera de {numbers[size]} voces distintas. "
            "Conversarán entre ellas en un solo audio."
        )
    if voices:
        text = (
            f"Modo {GROUP_MODE_LABELS[kind]}: tu voz ({voice_name(voices[0])}) ya participa. "
            f"Elige la siguiente ({len(voices) + 1} de {size})."
        )
    await send_text(
        chat_id, text,
        reply_markup={"inline_keyboard": voice_keyboard(chat_id, f"gsel:{kind}", exclude=voices)},
    )


# --- La Ruleta: voice trivia game (Preguntados-style) ---
# Single-player voice trivia: a colorful spinning-wheel GIF, one voice
# announcing the category, a different voice reading the question, and a
# third reacting (congratulating or playfully mocking). Three lives per game;
# five correct answers win a category and take it out of the wheel. Questions
# are LLM-generated with a no-repeat exclusion list. All state is in memory
# and degrades gracefully on the free-plan spin-down, like the group modes.
TRIVIA_CATEGORIES = [
    "deportes", "fútbol mundial", "películas", "series", "cultura",
    "historia", "ciencia", "arte", "comida", "países",
    "nombres y apellidos", "marcas", "animales", "política", "religión",
    "música", "geografía", "tecnología", "videojuegos", "refranes",
]
TRIVIA_COUNTRIES = [
    # Argentina first, then EVERY American country individually: his rule is
    # "ninguno se queda afuera".
    "Argentina", "Brasil", "Chile", "Uruguay", "Paraguay", "Bolivia",
    "Perú", "Ecuador", "Colombia", "Venezuela", "Guyana", "Surinam",
    "México", "Estados Unidos", "Canadá", "Belice",
    "Guatemala", "Honduras", "El Salvador", "Nicaragua", "Costa Rica",
    "Panamá", "Cuba", "República Dominicana", "Puerto Rico", "Curazao",
    "Haití",
    "Jamaica", "Bahamas", "Barbados", "Trinidad y Tobago", "Granada",
    "Dominica", "Santa Lucía", "San Vicente y las Granadinas",
    "San Cristóbal y Nieves", "Antigua y Barbuda",
    # Europe: the great majority.
    "España", "Francia", "Italia", "Alemania", "Reino Unido", "Irlanda",
    "Portugal", "Países Bajos", "Bélgica", "Luxemburgo", "Suiza",
    "Austria", "Mónaco", "Liechtenstein", "Andorra", "San Marino",
    "Malta", "Suecia", "Noruega", "Dinamarca", "Finlandia", "Islandia",
    "Estonia", "Letonia", "Lituania", "Polonia", "República Checa",
    "Eslovaquia", "Hungría", "Rumania", "Bulgaria", "Grecia", "Chipre",
    "Croacia", "Serbia", "Eslovenia", "Bosnia y Herzegovina",
    "Montenegro", "Macedonia del Norte", "Albania", "Kosovo",
    "Ucrania", "Rusia", "Bielorrusia", "Moldavia",
    # Asia: the great majority.
    "China", "Japón", "Corea del Sur", "Corea del Norte", "Mongolia",
    "Taiwán", "India", "Pakistán", "Bangladés", "Sri Lanka", "Nepal",
    "Bután", "Maldivas", "Afganistán", "Kazajistán", "Uzbekistán",
    "Turkmenistán", "Kirguistán", "Tayikistán", "Irán", "Irak",
    "Arabia Saudita", "Emiratos Árabes Unidos", "Catar", "Kuwait",
    "Baréin", "Omán", "Yemen", "Jordania", "Líbano", "Siria",
    "Israel", "Palestina", "Turquía", "Georgia", "Armenia",
    "Azerbaiyán", "Tailandia", "Vietnam", "Laos", "Camboya",
    "Myanmar", "Malasia", "Singapur", "Indonesia", "Filipinas",
    "Brunéi", "Timor Oriental",
    # Africa: the main ones.
    "Egipto", "Marruecos", "Argelia", "Túnez", "Libia", "Sudán",
    "Senegal", "Mali", "Níger", "Chad", "Nigeria", "Ghana",
    "Costa de Marfil", "Camerún", "Etiopía", "Somalia", "Kenia",
    "Uganda", "Tanzania", "Ruanda", "República Democrática del Congo",
    "Angola", "Zambia", "Zimbabue", "Botsuana", "Namibia",
    "Sudáfrica", "Mozambique", "Madagascar",
]
TRIVIA_CATEGORY_HINTS = {
    "deportes": (
        "Incluí cualquier deporte del mundo MENOS fútbol (esa es otra "
        "categoría): rugby, tenis, básquet, hockey, billar, bochas, carreras "
        "de caballos, polo, boxeo, atletismo, natación, etc. "
    ),
    "fútbol mundial": (
        "Sobre fútbol de todo el mundo: selecciones, mundiales, Champions "
        "League, ligas de Europa y América, jugadores de todas las épocas. "
        "No te centres solo en Argentina. "
    ),
    "refranes": (
        "Sobre refranes y dichos populares REALES y conocidos, de todo el "
        "mundo pero sobre todo de Argentina, Latinoamérica y España. Variá "
        "entre tres formatos: (1) '¿Cómo termina este refrán?' con el "
        "comienzo del refrán en la pregunta y terminaciones plausibles como "
        "opciones; (2) '¿Qué significa este refrán?'; (3) '¿De qué país o "
        "zona es este refrán?'. Cuando puedas, nombrá en la pregunta el país "
        "o la zona de origen (ej. 'Refrán de México: ...'). Si el origen es "
        "incierto o compartido, usá la zona amplia ('toda Latinoamérica', "
        "'España y Latinoamérica') en vez de inventar un país. Nunca "
        "inventes refranes: usá solo dichos que la gente dice de verdad. "
    ),
    "nombres y apellidos": (
        "Sobre el origen o significado de nombres y apellidos, o famosos que "
        "los llevan. "
    ),
}
TRIVIA_CONGRATS = [
    "¡Correcto, {name}! Sos un fenómeno.",
    "¡Exacto, {name}! Estás imparable.",
    "¡Muy bien, {name}! Respuesta perfecta.",
    "¡Correcto, {name}! Se nota que sabés.",
]
TRIVIA_CANNED_MOCKS = [
    "Ay {name}... esa la sabía hasta mi abuela.",
    "No, {name}, ¿en qué estabas pensando?",
    "Uy, {name}, esa estuvo lejísimos.",
    "{name}, che, ¿jugás en serio o me hacés reír?",
]
TRIVIA_LIVES = 3
TRIVIA_MAX_LIVES = 6
TRIVIA_STREAK_GIFT = 3  # every N-answer streak gifts a life
TRIVIA_CATEGORY_GOAL = 5
TRIVIA_TIMER_SECONDS = 600  # 10-minute cronometro per category sprint
TRIVIA_TIMER_WARNINGS = (300, 120, 60, 30)  # seconds remaining
TRIVIA_MAX_LEVEL = 150
TRIVIA_GRAND_PRIZE = "el Gran Trofeo de la Ruleta Sabrosa 🏆"
TRIVIA_COUNTRY_PRIZES = {
    "Argentina": "un mate bien cebado 🧉",
    "Brasil": "una caipirinha 🍹",
    "Chile": "un vino tinto del valle 🍷",
    "Uruguay": "un asado de domingo 🥩",
    "Paraguay": "un tereré bien frío 🧊",
    "Bolivia": "una salteña 🥟",
    "Perú": "un ceviche fresco 🐟",
    "Ecuador": "un encebollado 🍲",
    "Colombia": "un café de la zona cafetera ☕",
    "Venezuela": "una arepa 🫓",
    "México": "unos tacos al pastor 🌮",
    "Estados Unidos": "una hamburguesa gigante 🍔",
    "Canadá": "un jarabe de arce 🍁",
    "Cuba": "una noche de son cubano 🎺",
    "República Dominicana": "una bachata bailada 💃",
    "Puerto Rico": "una piña colada 🍍",
    "Jamaica": "una tarde de reggae 🎶",
    "Costa Rica": "un día de pura vida 🌴",
    "Panamá": "un sombrero pintado 👒",
    "Guatemala": "un tejido de colores 🧵",
    "Honduras": "una baleada 🌯",
    "El Salvador": "una pupusa 🥙",
    "Nicaragua": "un gallo pinto 🍚",
    "Haití": "un griot con arroz 🍗",
    "Trinidad y Tobago": "un tambor de calipso 🥁",
    "España": "una paella 🥘",
    "Francia": "un croissant 🥐",
    "Italia": "una pizza napolitana 🍕",
    "Alemania": "un pretzel 🥨",
    "Reino Unido": "un té de las cinco 🫖",
    "Portugal": "un pastel de nata 🍮",
    "Países Bajos": "unos tulipanes 🌷",
    "Bélgica": "un chocolate belga 🍫",
    "Suiza": "un reloj de cuco 🕰️",
    "Suecia": "unas albóndigas suecas 🍽️",
    "Noruega": "un fiordo en miniatura 🏔️",
    "Polonia": "unos pierogi 🥟",
    "Grecia": "una ensalada griega 🥗",
    "China": "un té de jazmín 🍵",
    "Japón": "un sushi variado 🍣",
    "India": "un curry con naan 🍛",
    "Corea del Sur": "un kimchi 🥬",
    "Turquía": "un dulce de baklava 🍯",
    "Arabia Saudita": "unos dátiles premium 🌴",
    "Egipto": "una pirámide en miniatura 🔺",
    "Sudáfrica": "una vuvuzela 🎺",
    "Nigeria": "un jollof rice 🍚",
    "Marruecos": "un té a la menta 🍵",
    "Kenia": "un safari en miniatura 🦁",
}
trivia_games = {}
trivia_lineups = {}
trivia_media = {}
# chat_id -> message_id of the one live ruleta keyboard (tidy-chat rule).
trivia_last_keyboard = {}
# chat_id -> message_id of the ruleta menu message, so a started game can
# delete it with the rest of its flow on exit.
trivia_pending_menu = {}


async def trivia_clear_keyboard(chat_id: int):
    """Retire the previous ruleta keyboard so old buttons never pile up."""
    old = trivia_last_keyboard.pop(chat_id, None)
    if old:
        try:
            await telegram(
                "editMessageReplyMarkup", chat_id=chat_id,
                message_id=old, reply_markup={"inline_keyboard": []},
            )
        except Exception:
            pass  # message gone or already cleared; nothing to clean


async def trivia_send_keyboard(chat_id: int, text: str, keyboard):
    """Post the next ruleta keyboard: at most ONE live keyboard at a time."""
    await trivia_clear_keyboard(chat_id)
    result = await send_text(
        chat_id, text, reply_markup={"inline_keyboard": keyboard},
    )
    mid = (result or {}).get("message_id")
    if isinstance(mid, int):
        trivia_last_keyboard[chat_id] = mid
    return mid


def trivia_track(game, *results):
    """Remember bot message ids so a finished game can tidy up after itself."""
    if not game:
        return
    sent = game.setdefault("sent_ids", [])
    for result in results:
        mid = result.get("message_id") if isinstance(result, dict) else result
        if isinstance(mid, int):
            sent.append(mid)


async def trivia_delete_flow(chat_id: int, game):
    """On exit the game deletes its own messages, leaving one summary line."""
    trivia_last_keyboard.pop(chat_id, None)
    for mid in game.get("sent_ids", []):
        try:
            await telegram("deleteMessage", chat_id=chat_id, message_id=mid)
        except Exception:
            log.debug("Could not delete ruleta message %s", mid)
    game["sent_ids"] = []


TRIVIA_NUMBER_WORDS = {
    0: "ninguna", 1: "una", 2: "dos", 3: "tres",
    4: "cuatro", 5: "cinco", 6: "seis",
}


def trivia_lives_line(lives: int) -> str:
    """The voices count his lives down in words: 'te quedan dos', 'te queda una'."""
    if lives <= 0:
        return "Te quedaste sin vidas."
    if lives == 1:
        return "Te queda una vida."
    return f"Te quedan {TRIVIA_NUMBER_WORDS.get(lives, str(lives))} vidas."


def trivia_difficulty(level: int) -> str:
    """Questions get harder as he levels up."""
    if level <= 10:
        return "fácil"
    if level <= 30:
        return "media"
    if level <= 60:
        return "difícil"
    return "de experto"


def trivia_level_up(game) -> int:
    """One correct answer = one level. Returns the new level, 0 when already capped."""
    level = game.get("level", 1)
    if level < TRIVIA_MAX_LEVEL:
        level += 1
        game["level"] = level
        return level
    return 0


def trivia_apply_gift(game) -> bool:
    """Every 3-answer streak gifts a life (up to the cap). True when granted."""
    streak = game.get("streak", 0)
    if streak and streak % TRIVIA_STREAK_GIFT == 0 and game["lives"] < TRIVIA_MAX_LIVES:
        game["lives"] += 1
        return True
    return False


def trivia_timeout_life(game) -> bool:
    """A cronometro time-out costs a life. True when the game is over."""
    game["lives"] -= 1
    game["streak"] = 0
    return game["lives"] <= 0


def trivia_country_prize(country: str) -> str:
    return TRIVIA_COUNTRY_PRIZES.get(country, f"un recuerdo de {country} 🎁")


def trivia_round_voices(chat_id: int):
    """Announcer, reader, reactor: the picked lineup or three distinct random voices."""
    lineup = trivia_lineups.get(chat_id)
    if lineup and len(lineup) >= 3:
        return lineup[0], lineup[1], lineup[2]
    return tuple(random.sample(list(VOICES.keys()), 3))


def build_spin_gif() -> bytes:
    """One short looping roulette-wheel GIF, reused for every spin (light for the 512 MB plan)."""
    import io
    from PIL import Image, ImageDraw
    size, center, radius = 240, 120, 106
    colors = [
        "#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5",
        "#8e24aa", "#d81b60", "#00acc1", "#7cb342", "#f4511e",
    ]
    frames = []
    for frame in range(36):
        angle = frame * 10.0
        image = Image.new("RGB", (size, size), "#101418")
        draw = ImageDraw.Draw(image)
        start = angle
        for color in colors:
            draw.pieslice(
                [center - radius, center - radius, center + radius, center + radius],
                start=start, end=start + 36.2, fill=color, outline="#101418",
            )
            start += 36.0
        draw.ellipse(
            [center - 26, center - 26, center + 26, center + 26],
            fill="#ffffff", outline="#101418", width=3,
        )
        draw.polygon(
            [(center - 13, 4), (center + 13, 4), (center, 32)],
            fill="#ffffff", outline="#101418",
        )
        frames.append(image.convert("P", palette=Image.ADAPTIVE, colors=64))
    buffer = io.BytesIO()
    frames[0].save(
        buffer, format="GIF", save_all=True, append_images=frames[1:],
        duration=55, loop=0, optimize=True, disposal=1,
    )
    return buffer.getvalue()


def build_spin_sfx() -> bytes:
    """WAV: fast clicking that speeds up, then a final ding (the wheel sound)."""
    import io
    import math
    import struct
    import wave
    rate = 22050
    total = int(rate * 2.2)
    data = [0.0] * total
    times = []
    moment = 0.0
    interval = 0.16
    while moment < 1.5:
        times.append(moment)
        moment += interval
        interval = max(0.055, interval * 0.9)
    for start in times:
        offset = int(rate * start)
        length = int(rate * 0.03)
        for i in range(length):
            if offset + i < total:
                envelope = 1.0 - i / length
                data[offset + i] += 0.7 * envelope * math.sin(2 * math.pi * 1900 * i / rate)
    ding = int(rate * 1.55)
    for i in range(int(rate * 0.5)):
        if ding + i < total:
            envelope = math.exp(-i / (rate * 0.12))
            data[ding + i] += 0.6 * envelope * (
                math.sin(2 * math.pi * 880 * i / rate)
                + 0.5 * math.sin(2 * math.pi * 1318 * i / rate)
            )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(
            b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in data)
        )
    return buffer.getvalue()


async def wav_to_ogg(wav_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "spin.wav"
        ogg = Path(directory) / "spin.ogg"
        source.write_bytes(wav_bytes)
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-c:a", "libopus", "-b:a", "48k", "-ac", "1", str(ogg),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError(f"ffmpeg wav->ogg failed: {stderr.decode()[:300]}")
        return ogg.read_bytes()


async def join_ogg(blobs) -> bytes:
    """Concatenate ready ogg/opus blobs into one voice-note file."""
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for index, blob in enumerate(blobs):
            path = Path(directory) / f"part-{index}.ogg"
            path.write_bytes(blob)
            paths.append(path)
        concat_file = Path(directory) / "join.txt"
        concat_file.write_text("".join(f"file '{path}'\n" for path in paths))
        joined = Path(directory) / "joined.ogg"
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:a", "libopus", "-b:a", "48k", "-ac", "1", str(joined),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError(f"ffmpeg ogg join failed: {stderr.decode()[:300]}")
        return joined.read_bytes()


async def trivia_sfx_ogg() -> bytes:
    if "sfx_ogg" not in trivia_media:
        wav = await asyncio.to_thread(build_spin_sfx)
        trivia_media["sfx_ogg"] = await wav_to_ogg(wav)
    return trivia_media["sfx_ogg"]


async def send_voice_audio(chat_id: int, audio: bytes, filename="ruleta.ogg"):
    """Raw voice-note sender for pre-built audio (send_voice uses the selected voice)."""
    if not voice_enabled[chat_id]:
        return
    try:
        await telegram("sendChatAction", chat_id=chat_id, action="upload_voice")
        response = await http.post(
            f"{TELEGRAM_API}/sendVoice",
            data={"chat_id": str(chat_id)},
            files={"voice": (filename, audio, "audio/ogg")},
        )
        if response.status_code >= 400:
            log.error("Telegram sendVoice failed: %s %s", response.status_code, response.text[:500])
        response.raise_for_status()
        return (response.json().get("result") or {}).get("message_id")
    except Exception:
        log.exception("Could not send trivia voice note")
    return None


async def send_spin_animation(chat_id: int):
    file_id = trivia_media.get("gif_file_id")
    if file_id:
        try:
            result = await telegram(
                "sendAnimation", chat_id=chat_id, animation=file_id,
                caption="🎡 Girando la ruleta...",
            )
            return (result or {}).get("message_id")
        except Exception:
            trivia_media.pop("gif_file_id", None)
    gif = trivia_media.get("gif_bytes")
    if gif is None:
        gif = await asyncio.to_thread(build_spin_gif)
        trivia_media["gif_bytes"] = gif
    response = await http.post(
        f"{TELEGRAM_API}/sendAnimation",
        data={"chat_id": str(chat_id), "caption": "🎡 Girando la ruleta..."},
        files={"animation": ("ruleta.gif", gif, "image/gif")},
    )
    if response.status_code >= 400:
        log.error("Telegram sendAnimation failed: %s %s", response.status_code, response.text[:500])
    response.raise_for_status()
    result = response.json().get("result") or {}
    animation = result.get("animation") or result.get("document") or {}
    if animation.get("file_id"):
        trivia_media["gif_file_id"] = animation["file_id"]
    return result.get("message_id")


def parse_trivia_question(text: str):
    question = re.search(r"PREGUNTA:\s*(.+)", text)
    options = re.findall(r"OPCION\s*\d\s*:\s*(.+)", text)
    correct = re.search(r"CORRECTA:\s*([1-4])", text)
    if not question or len(options) != 4 or not correct:
        return None
    return {
        "question": question.group(1).strip(),
        "options": [option.strip() for option in options],
        "correct": int(correct.group(1)) - 1,
    }


async def trivia_generate_question(category: str, country, asked, level: int = 1):
    country_clause = f" ambientada o referida a {country}" if country else ""
    hint = TRIVIA_CATEGORY_HINTS.get(category, "")
    difficulty = trivia_difficulty(level)
    recent = list(asked)[-8:] or ["(todavía ninguna)"]
    prompt = (
        "Sos el generador de un juego de trivia argentino estilo Preguntados. "
        f"Generá UNA pregunta de dificultad {difficulty} (nivel {level} de "
        f"{TRIVIA_MAX_LEVEL}) sobre la categoría \"{category}\"{country_clause}. "
        "Tiene que tener una sola respuesta correcta inequívoca y cuatro opciones plausibles. "
        + hint +
        "No repitas ninguna de estas preguntas ya usadas: "
        + " | ".join(recent) + ". "
        "Respondé con este formato exacto, seis líneas, sin texto extra:\n"
        "PREGUNTA: <el texto de la pregunta>\n"
        "OPCION 1: <una opción>\n"
        "OPCION 2: <una opción>\n"
        "OPCION 3: <una opción>\n"
        "OPCION 4: <una opción>\n"
        "CORRECTA: <el número de la opción correcta, 1 a 4>"
    )
    for _ in range(2):
        try:
            result = await complete([{"role": "user", "content": prompt}])
            parsed = parse_trivia_question(result)
            if parsed:
                return parsed
            log.warning("Trivia question parse failed: %s", result[:200])
        except Exception:
            log.exception("Trivia question generation failed")
    return None


def trivia_match_answer(user_text: str, options):
    """Map a spoken/written answer to an option index, or None when unclear."""
    text = normalized(user_text).strip()
    match = re.search(r"\b([1-4])\b", text)
    if match:
        return int(match.group(1)) - 1
    match = re.match(r"^(?:la\s+)?([abcd])$", text)
    if match:
        return "abcd".index(match.group(1))
    number_words = {"uno": 0, "dos": 1, "tres": 2, "cuatro": 3}
    match = re.search(r"\b(uno|dos|tres|cuatro)\b", text)
    if match:
        return number_words[match.group(1)]
    ordinals = {
        "primer": 0, "segunda": 1, "segundo": 1,
        "tercer": 2, "cuarta": 3, "cuarto": 3,
        "ultima": 3, "ultimo": 3,
    }
    for word, index in ordinals.items():
        if word in text:
            return index
    for index, option in enumerate(options):
        opt = normalized(option).strip(" .,")
        if len(opt) >= 4 and (opt in text or (len(text) >= 4 and text in opt)):
            return index
    return None


async def trivia_menu(chat_id: int):
    # Retired Telegram game: old commands and natural-language aliases redirect.
    await games_menu(chat_id)
    return
    mid = await trivia_send_keyboard(
        chat_id,
        "🎡 LA RULETA SABROSA\n"
        f"Tenés {TRIVIA_LIVES} vidas por partida: cada error te saca una, "
        f"pero una racha de {TRIVIA_STREAK_GIFT} aciertos te regala una. "
        f"{TRIVIA_CATEGORY_GOAL} aciertos ganan una categoría y esa no vuelve a salir. "
        "Cada categoría corre contra un cronómetro de 10 minutos: si se acaba, "
        "perdés una vida. Cada acierto te sube de nivel (hasta el "
        f"{TRIVIA_MAX_LEVEL}) y las preguntas se ponen más difíciles. "
        "Completar todo un país, o toda la ruleta clásica, te desbloquea un premio. "
        "Respondés con los botones, o hablado: decí el número o el nombre de la opción. "
        "Las voces cambian en cada ronda: una presenta, otra lee la pregunta y otra reacciona.\n\n"
        "Elegí cómo jugar:",
        [
            [{"text": "🎡 Ruleta clásica (categorías)", "callback_data": "trivia:start:classic"}],
            [{"text": "🌍 Ruleta de países (país + categoría)", "callback_data": "trivia:start:countries"}],
            [{"text": "🎭 Elegir mis 3 voces del juego", "callback_data": "trivia:lineup"}],
            [{"text": "⬅️ Volver al menú principal", "callback_data": "mode:menu"}],
        ],
    )
    if isinstance(mid, int):
        trivia_pending_menu[chat_id] = mid


async def trivia_begin(chat_id: int, countries_mode: bool):
    clear_group_modes(chat_id)
    pending_music_query.pop(chat_id, None)
    if chat_id in ahorcado_games:
        await ahorcado_end(chat_id)
    trivia_games[chat_id] = {
        "phase": "ready",
        "countries": countries_mode,
        "lives": TRIVIA_LIVES,
        "streak": 0,
        "level": 1,
        "score": {},
        "won": [],
        "country": None,
        "country_won": [],
        "countries_done": [],
        "sprint": None,
        "timer_gen": 0,
        "deadline": None,
        "asked": deque(maxlen=80),
        "current": None,
    }
    mode_line = "con países y categorías cruzados" if countries_mode else "con las categorías"
    name = get_preferred_name(chat_id) or "campeón"
    menu_mid = trivia_pending_menu.pop(chat_id, None)
    if isinstance(menu_mid, int):
        trivia_track(trivia_games.get(chat_id), menu_mid)
    mid = await trivia_send_keyboard(
        chat_id,
        f"🎡 EMPIEZA LA RULETA\nArranca la ruleta {mode_line}. Tenés "
        f"{TRIVIA_LIVES} vidas y un cronómetro de 10 minutos por categoría. "
        "Girá con el botón de abajo o decime 'girá'.",
        [
            [{"text": "🎡 Girar la ruleta", "callback_data": "trivia:spin"}],
            [{"text": "🚪 Salir de la ruleta", "callback_data": "trivia:quit"}],
        ],
    )
    game = trivia_games.get(chat_id)
    trivia_track(game, mid)
    voice_mid = await send_voice(
        chat_id,
        f"{name}, arranca la ruleta {mode_line}. Tenés {TRIVIA_LIVES} vidas. "
        "Decime girá cuando quieras.",
    )
    trivia_track(game, voice_mid)


async def trivia_end(chat_id: int):
    game = trivia_games.pop(chat_id, None)
    await trivia_clear_keyboard(chat_id)
    if game:
        await trivia_delete_flow(chat_id, game)
    await send_text(
        chat_id,
        "🏁 TERMINÓ LA RULETA. Escribí /ruleta o pulsá el botón del menú "
        "para jugar de nuevo.",
    )


async def trivia_spin(chat_id: int):
    game = trivia_games.get(chat_id)
    if not game:
        await send_text(chat_id, "La ruleta no está en marcha. Escribí /ruleta para empezar.")
        return
    name = get_preferred_name(chat_id) or "campeón"
    country = None
    new_country = False
    if game["countries"]:
        # Country mode: he must complete EVERY category of the landed country
        # before the roulette offers another country.
        country = game.get("country")
        if country is None:
            remaining = [c for c in TRIVIA_COUNTRIES if c not in game["countries_done"]]
            if not remaining:
                await send_text(
                    chat_id,
                    f"🌎 ¡CAMPEÓN MUNDIAL, {name}! Completaste TODOS los países de la "
                    f"ruleta. Desbloqueaste {TRIVIA_GRAND_PRIZE}. "
                    "Escribí /ruleta para jugar de nuevo.",
                )
                trivia_games.pop(chat_id, None)
                return
            country = random.choice(remaining)
            game["country"] = country
            game["country_won"] = []
            game["score"] = {}
            new_country = True
        available = [c for c in TRIVIA_CATEGORIES if c not in game["country_won"]]
        if not available:
            prize = trivia_country_prize(country)
            game["countries_done"].append(country)
            game["country"] = None
            game["sprint"] = None
            trivia_cancel_timer(game)
            done = len(game["countries_done"])
            total = len(TRIVIA_COUNTRIES)
            text = (
                f"🏆 ¡{name}, completaste TODAS las categorías de {country}! "
                f"{country} te regala {prize}. Llevás {done} de {total} países. "
                "Girá de nuevo para conocer tu próximo destino."
            )
            mid = await trivia_send_keyboard(chat_id, text, [
                [{"text": "🌍 Girar por otro país", "callback_data": "trivia:spin"}],
                [{"text": "🚪 Salir de la ruleta", "callback_data": "trivia:quit"}],
            ])
            trivia_track(game, mid)
            try:
                _, _, announcer = trivia_round_voices(chat_id)
                voice_mid = await send_voice_audio(chat_id, await synthesize(text, announcer), "premio.ogg")
                trivia_track(game, voice_mid)
            except Exception:
                log.exception("Could not send the prize voice note")
            return
    else:
        available = [c for c in TRIVIA_CATEGORIES if c not in game["won"]]
        if not available:
            trivia_cancel_timer(game)
            await trivia_delete_flow(chat_id, game)
            await send_text(
                chat_id,
                f"🏆 ¡Ganaste todas las categorías, {name}! Desbloqueaste "
                f"{TRIVIA_GRAND_PRIZE}. Sos el campeón absoluto de la ruleta. "
                "Escribí /ruleta para jugar de nuevo.",
            )
            trivia_games.pop(chat_id, None)
            return
    game["phase"] = "spinning"
    category = random.choice(available)
    announcer, reader, reactor = trivia_round_voices(chat_id)
    try:
        trivia_track(game, await send_spin_animation(chat_id))
    except Exception:
        log.exception("Could not send the spin animation; continuing without it")
    if country and new_country:
        announce = (
            "¡Giramos la ruleta! Gira, gira... ¡paró la ruleta! "
            f"Te tocó... ¡{country}! Y la categoría es... ¡{category}!"
        )
    elif country:
        announce = (
            "¡Giramos la ruleta! Gira, gira... ¡paró! "
            f"Seguís en {country}. La categoría es... ¡{category}!"
        )
    else:
        announce = (
            "¡Giramos la ruleta! Gira, gira... ¡paró la ruleta! "
            f"Te salió... ¡{category}!"
        )
    try:
        sfx = await trivia_sfx_ogg()
        voice_part = await synthesize(announce, announcer)
        trivia_track(game, await send_voice_audio(chat_id, await join_ogg([sfx, voice_part])))
    except Exception:
        log.exception("Could not send the spin announcement")
    question = await trivia_generate_question(
        category, country, game["asked"], game.get("level", 1)
    )
    if not question:
        game["phase"] = "ready"
        mid = await trivia_send_keyboard(
            chat_id,
            "No me salió armar la pregunta. Girá de nuevo con el botón o decime 'girá'.",
            [[{"text": "🎡 Girar la ruleta", "callback_data": "trivia:spin"}]],
        )
        trivia_track(game, mid)
        return
    game["asked"].append(question["question"])
    game["phase"] = "question"
    game["current"] = {
        "category": category,
        "country": country,
        "question": question["question"],
        "options": question["options"],
        "correct": question["correct"],
        "voices": (announcer, reader, reactor),
        "message_id": None,
    }
    # The cronometro covers a whole category sprint: it (re)starts when the
    # landed category changes and stops when the category is won.
    if game.get("sprint") != category:
        game["sprint"] = category
        trivia_start_timer(chat_id, game)
    where = f" de {country}" if country else ""
    option_lines = "\n".join(
        f"{index + 1}. {option}" for index, option in enumerate(question["options"])
    )
    keyboard = [
        [{"text": f"{index + 1}. {option[:45]}", "callback_data": f"tans:{index}"}]
        for index, option in enumerate(question["options"])
    ]
    await trivia_clear_keyboard(chat_id)
    result = await telegram(
        "sendMessage",
        chat_id=chat_id,
        text=(
            f"🎯 {category.upper()}{where}\n\n{question['question']}\n\n{option_lines}"
        ),
        reply_markup={"inline_keyboard": keyboard},
    )
    game["current"]["message_id"] = result.get("message_id")
    if isinstance(game["current"]["message_id"], int):
        trivia_last_keyboard[chat_id] = game["current"]["message_id"]
    trivia_track(game, result)
    numbers = ["uno", "dos", "tres", "cuatro"]
    # One voice reads the question, ANOTHER voice reads the options: he asked
    # to tell them apart by voice, and the two notes chain-play with one tap.
    question_text = f"Pregunta: {question['question']}"
    options_text = (
        "Y las opciones son. "
        + " ".join(
            f"Opción {numbers[index]}: {option}."
            for index, option in enumerate(question["options"])
        )
        + " Decí el número o el nombre de la opción."
    )
    try:
        trivia_track(
            game,
            await send_voice_audio(
                chat_id, await synthesize(question_text, reader), "pregunta.ogg"
            ),
        )
    except Exception:
        log.exception("Could not send the question voice note")
    try:
        trivia_track(
            game,
            await send_voice_audio(
                chat_id, await synthesize(options_text, announcer), "opciones.ogg"
            ),
        )
    except Exception:
        log.exception("Could not send the options voice note")


async def trivia_mock(name: str, current) -> str:
    wrong = current["options"][current["picked"]]
    right = current["options"][current["correct"]]
    try:
        return await complete([
            {"role": "system", "content": (
                "Sos una voz de un juego de trivia argentino. Te burlás con buena "
                "onda de una respuesta equivocada: UNA frase corta, rioplatense, "
                "cargada pero cariñosa, sin maldiciones ni malas palabras."
            )},
            {"role": "user", "content": (
                f"{name} respondió '{wrong}' y la correcta era '{right}' "
                f"en la categoría {current['category']}. Burlate en una frase."
            )},
        ])
    except Exception:
        return random.choice(TRIVIA_CANNED_MOCKS).format(name=name)


async def trivia_handle_answer(chat_id: int, index: int, callback=None):
    game = trivia_games.get(chat_id)
    if not game or game.get("phase") != "question" or not game.get("current"):
        await send_text(chat_id, "Esa pregunta ya pasó. Girá de nuevo con el botón o escribí /ruleta.")
        return
    current = game["current"]
    current["picked"] = index
    game["phase"] = "ready"
    correct = current["correct"]
    category = current["category"]
    name = get_preferred_name(chat_id) or "campeón"
    marked_lines = []
    for position, option in enumerate(current["options"]):
        if position == correct:
            marked_lines.append(f"🟢 {option}")
        elif position == index:
            marked_lines.append(f"❌ {option}")
        else:
            marked_lines.append(f"⚪ {option}")
    if current.get("message_id"):
        try:
            await telegram(
                "editMessageText", chat_id=chat_id, message_id=current["message_id"],
                text=(
                    f"🎯 {category.upper()}\n\n{current['question']}\n\n"
                    + "\n".join(marked_lines)
                ),
                reply_markup={"inline_keyboard": []},
            )
        except Exception:
            log.exception("Could not mark the trivia answer in place")
        trivia_last_keyboard.pop(chat_id, None)
    _, _, reactor = current["voices"]
    if index == correct:
        game["streak"] = game.get("streak", 0) + 1
        level = trivia_level_up(game)
        level_line = f" ¡Pasaste al nivel {level}!" if level else ""
        wins = game["score"].get(category, 0) + 1
        game["score"][category] = wins
        if wins >= TRIVIA_CATEGORY_GOAL:
            # Category won: the cronometro for this sprint stops here.
            trivia_cancel_timer(game)
            game["sprint"] = None
            if game["countries"]:
                if category not in game["country_won"]:
                    game["country_won"].append(category)
                left = len(TRIVIA_CATEGORIES) - len(game["country_won"])
                feedback = (
                    f"¡Correcto, {name}! ¡Y con esta ganaste la categoría "
                    f"{category} de {current.get('country')}! No sale más en este país."
                    + (f" Te quedan {left} categorías de {current.get('country')}." if left else "")
                )
            else:
                if category not in game["won"]:
                    game["won"].append(category)
                feedback = (
                    f"¡Correcto, {name}! ¡Y con esta ganaste la categoría {category}! "
                    "No sale más en la ruleta. Sos un crack."
                )
        else:
            feedback = (
                random.choice(TRIVIA_CONGRATS).format(name=name)
                + f" Llevás {wins} de {TRIVIA_CATEGORY_GOAL} en {category}."
            )
        feedback += level_line
        if trivia_apply_gift(game):
            feedback += (
                " Y de yapa te regalamos una vida: ahora tenés "
                f"{TRIVIA_NUMBER_WORDS.get(game['lives'], game['lives'])}."
            )
        game_over = False
    else:
        game["streak"] = 0
        game["lives"] -= 1
        mock = await trivia_mock(name, current)
        feedback = (
            f"{mock} La correcta era {current['options'][correct]}. "
            f"{trivia_lives_line(game['lives'])}"
        )
        game_over = game["lives"] <= 0
    trivia_track(game, await send_text(chat_id, feedback))
    try:
        trivia_track(
            game,
            await send_voice_audio(chat_id, await synthesize(feedback, reactor), "reaccion.ogg"),
        )
    except Exception:
        log.exception("Could not send the feedback voice note")
    if game_over:
        await trivia_game_over(chat_id, game, name)
        return
    mid = await trivia_send_keyboard(
        chat_id,
        "¿Seguimos? Girá con el botón o decime 'girá'.",
        [
            [{"text": "🎡 Girar de nuevo", "callback_data": "trivia:spin"}],
            [{"text": "🚪 Salir de la ruleta", "callback_data": "trivia:quit"}],
        ],
    )
    trivia_track(game, mid)


async def trivia_game_over(chat_id: int, game, name: str):
    """Shared 'lost all lives' ending: summary, restart buttons, clean state.

    Starting over means from zero: in countries mode the next run spins a new
    random country, exactly as he asked.
    """
    trivia_cancel_timer(game)
    if game.get("countries"):
        done = game.get("countries_done") or []
        summary = (
            "Países completados: " + ", ".join(done) + "."
            if done else "No completaste ningún país esta vez."
        )
        restart = " La próxima partida arranca de cero, con un país nuevo al azar."
    else:
        summary = (
            "Categorías ganadas: " + ", ".join(game["won"]) + "."
            if game["won"] else "No ganaste ninguna categoría esta vez."
        )
        restart = ""
    await trivia_delete_flow(chat_id, game)
    await trivia_send_keyboard(
        chat_id,
        f"🏁 TERMINÓ LA RULETA\n💀 Fin de la partida, {name}. {summary}{restart} ¿Revancha?",
        [
            [{"text": "🎡 Jugar de nuevo", "callback_data": "trivia:menu"}],
            [{"text": "⬅️ Menú principal", "callback_data": "mode:menu"}],
        ],
    )
    trivia_games.pop(chat_id, None)


def trivia_start_timer(chat_id: int, game):
    """(Re)start the 10-minute cronometro for the current category sprint."""
    game["timer_gen"] = game.get("timer_gen", 0) + 1
    game["deadline"] = time.time() + TRIVIA_TIMER_SECONDS
    gen = game["timer_gen"]
    for remaining in TRIVIA_TIMER_WARNINGS:
        asyncio.create_task(trivia_timer_warning(chat_id, gen, remaining))
    asyncio.create_task(trivia_timer_timeout(chat_id, gen))


def trivia_cancel_timer(game):
    """Stop the cronometro: pending wake-ups check the generation counter."""
    game["timer_gen"] = game.get("timer_gen", 0) + 1
    game["deadline"] = None


async def trivia_timer_warning(chat_id: int, gen: int, remaining: int):
    """The voices hurry him along as the cronometro runs down."""
    await asyncio.sleep(TRIVIA_TIMER_SECONDS - remaining)
    game = trivia_games.get(chat_id)
    if not game or game.get("timer_gen") != gen or not game.get("deadline"):
        return
    name = get_preferred_name(chat_id) or "campeón"
    if remaining >= 120:
        text = f"⏳ {name}, quedan {remaining // 60} minutos del cronómetro."
    elif remaining == 60:
        text = f"⏳ ¡Último minuto, {name}! ¡Dale que se acaba!"
    else:
        text = f"⏳ ¡{remaining} segundos, {name}, apurate!"
    trivia_track(game, await send_text(chat_id, text))
    try:
        round_voices = (game.get("current") or {}).get("voices")
        warner = round_voices[2] if round_voices else trivia_round_voices(chat_id)[0]
        trivia_track(
            game,
            await send_voice_audio(chat_id, await synthesize(text, warner), "cronometro.ogg"),
        )
    except Exception:
        log.exception("Could not send the cronometro warning voice")


async def trivia_timer_timeout(chat_id: int, gen: int):
    """A time-out costs a life; a pending question is forfeited."""
    await asyncio.sleep(TRIVIA_TIMER_SECONDS)
    game = trivia_games.get(chat_id)
    if not game or game.get("timer_gen") != gen:
        return
    name = get_preferred_name(chat_id) or "campeón"
    current = game.get("current") if game.get("phase") == "question" else None
    if current:
        if current.get("message_id"):
            try:
                await telegram(
                    "editMessageText", chat_id=chat_id,
                    message_id=current["message_id"],
                    text=(
                        f"🎯 {current['category'].upper()}\n\n{current['question']}\n\n"
                        + "\n".join(
                            f"{'🟢' if position == current['correct'] else '⚪'} {option}"
                            for position, option in enumerate(current["options"])
                        )
                    ),
                    reply_markup={"inline_keyboard": []},
                )
            except Exception:
                log.exception("Could not mark the timed-out question")
        game["current"] = None
        game["phase"] = "ready"
    over = trivia_timeout_life(game)
    # The clock restarts with his next spin, not while he is away.
    game["sprint"] = None
    if over:
        trivia_track(
            game,
            await send_text(
                chat_id, f"⏰ ¡Se acabó el cronómetro, {name}! Y era tu última vida..."
            ),
        )
        await trivia_game_over(chat_id, game, name)
        return
    text = (
        f"⏰ ¡Se acabó el cronómetro, {name}! Perdés una vida. "
        + trivia_lives_line(game["lives"])
        + " El cronómetro arranca de nuevo con tu próximo giro."
    )
    mid = await trivia_send_keyboard(chat_id, text, [
        [{"text": "🎡 Girar de nuevo", "callback_data": "trivia:spin"}],
        [{"text": "🚪 Salir de la ruleta", "callback_data": "trivia:quit"}],
    ])
    trivia_track(game, mid)
    try:
        announcer = trivia_round_voices(chat_id)[0]
        trivia_track(
            game,
            await send_voice_audio(chat_id, await synthesize(text, announcer), "cronometro.ogg"),
        )
    except Exception:
        log.exception("Could not send the timeout voice")


async def start_trivia_lineup(chat_id: int):
    group_selection[chat_id] = {"kind": "trivia", "voices": []}
    await pick_group_voices(chat_id, "trivia", include_self=False)


async def complete_trivia_lineup(chat_id: int, callback: dict, voices):
    lineup = list(voices)[:3]
    trivia_lineups[chat_id] = lineup
    names = [voice_name(voice) for voice in lineup]
    message = callback.get("message") or {}
    if message.get("message_id"):
        try:
            await telegram(
                "editMessageReplyMarkup", chat_id=chat_id,
                message_id=message["message_id"],
                reply_markup={"inline_keyboard": []},
            )
        except Exception:
            log.exception("Could not clear the trivia lineup keyboard")
    await telegram(
        "answerCallbackQuery", callback_query_id=callback["id"],
        text=f"Voces de la ruleta: {', '.join(names)}",
    )
    await trivia_send_keyboard(
        chat_id,
        f"🎭 Tus voces de la ruleta: {names[0]} presenta, {names[1]} lee las "
        f"preguntas y {names[2]} reacciona. Ya podés girar.",
        [
            [{"text": "🎡 Ruleta clásica", "callback_data": "trivia:start:classic"}],
            [{"text": "🌍 Ruleta de países", "callback_data": "trivia:start:countries"}],
        ],
    )


# --- El Ahorcado: voice-first word guessing game ---

AHORCADO_TIME_LIMIT = 600  # 10 minutes per word
AHORCADO_CLOCK_WARNINGS = (300, 60)  # spoken warnings when this much is left
AHORCADO_MAX_LIVES = 3
# The three ruleta voices: the game, the clock, and the levels/lives announcer.
AHORCADO_GAME_VOICE = "es-AR-ElenaNeural"
AHORCADO_CLOCK_VOICE = "es-AR-TomasNeural"
AHORCADO_LEVEL_VOICE = "es-UY-ValentinaNeural"

# Local leveled word bank: instant start (no LLM round-trip) and difficulty
# that rises deterministically with the level. Words have no tildes and use
# only letters that AHORCADO_SPEAK can pronounce.
AHORCADO_BANK = [
    # 4-5 letras (nivel 1)
    ("MATE", "Infusión caliente que se comparte con bombilla."),
    ("GATO", "Animal que maúlla y duerme mucho."),
    ("LUNA", "Se ve de noche en el cielo."),
    ("TREN", "Va por las vías con vagones."),
    ("NUBE", "Blanca, flota en el cielo y a veces trae lluvia."),
    ("FARO", "Torre que guía a los barcos con su luz."),
    ("FLOR", "Crece en el jardín y huele rico."),
    ("DEDO", "Tenés cinco en cada mano."),
    ("VASO", "Se usa para tomar agua."),
    ("BOTE", "Barquito chico a remo."),
    ("PERRO", "El mejor amigo del hombre."),
    ("TORTA", "Se come en los cumpleaños."),
    ("LLAVE", "Sirve para abrir puertas."),
    ("SILLA", "Tiene cuatro patas y se usa para sentarse."),
    ("RADIO", "Aparato para escuchar música y noticias."),
    ("PLAZA", "Lugar con juegos y bancos para los chicos."),
    ("PLATO", "Ahí se sirve la comida."),
    ("CAMPO", "Lugar con vacas y sembrados."),
    ("LIBRO", "Tiene páginas para leer."),
    ("BANCO", "Te sentás en la plaza; también guarda plata."),
    ("PEINE", "Ordena el pelo."),
    ("JABON", "Hace espuma para lavarse."),
    ("QUESO", "Va rallado sobre los fideos."),
    # 6 letras (nivel 2)
    ("HELADO", "Postre frío y dulce."),
    ("ZAPATO", "Prenda que va en el pie."),
    ("ESPEJO", "Te devuelve tu imagen."),
    ("AZUCAR", "Endulza el café."),
    ("PUERTA", "Se abre para entrar a casa."),
    ("CAMINO", "Sendero que lleva a algún lugar."),
    ("PUEBLO", "Ciudad chiquita."),
    ("PIERNA", "La usás para patear una pelota."),
    ("MONEDA", "Plata chica de metal; sirve para el colectivo."),
    ("PLANTA", "Verde, crece en una maceta."),
    ("SOMBRA", "Te cubre del sol bajo el árbol."),
    ("BANANA", "Fruta amarilla que se pela."),
    ("COCINA", "Ambiente donde se prepara la comida."),
    ("PASTEL", "Torta dulce de cumpleaños."),
    # 7 letras (nivel 3)
    ("FACTURA", "Pastelito dulce que acompaña el mate."),
    ("VENTANA", "Abertura en la pared para ver afuera."),
    ("CUCHARA", "Utensilio para comer la sopa."),
    ("BOTELLA", "Envase para guardar líquidos."),
    ("TECLADO", "Tiene teclas con letras."),
    ("PELUCHE", "Juguete blando para abrazar."),
    ("LAMPARA", "Da luz sobre la mesa."),
    ("CABALLO", "Animal que se monta y relincha."),
    ("MANTECA", "Se unta en el pan."),
    ("VERDURA", "Lechuga o tomate: comida sana."),
    ("ZAPALLO", "Naranja y grande, va en la sopa o el puré."),
    ("NARANJA", "Fruta cítrica con mucho jugo."),
    ("CORAZON", "Órgano que late en el pecho."),
    ("SEMILLA", "Chiquita, se planta y crece."),
    # 8 letras (nivel 4)
    ("GUITARRA", "Instrumento de seis cuerdas."),
    ("BILLETERA", "Guarda la plata y las tarjetas."),
    ("PARAGUAS", "Te protege de la lluvia."),
    ("ESCALERA", "Sirve para subir a lo alto."),
    ("CAMISETA", "Prenda de manga corta; también la de tu club."),
    ("ALMOHADA", "Apoya la cabeza para dormir."),
    ("CUADERNO", "Tiene hojas para escribir."),
    ("MARIPOSA", "Insecto de alas de colores."),
    ("HELADERA", "Mantiene la comida fría en la cocina."),
    ("TELARAÑA", "La teje la araña en un rincón."),
    ("SOMBRERO", "Te cubre la cabeza del sol."),
    ("ELEFANTE", "Animal enorme con trompa."),
    # 9-10 letras (nivel 5 en adelante)
    ("AURICULAR", "Va en la oreja para escuchar música."),
    ("BICICLETA", "Dos ruedas y pedales."),
    ("CHOCOLATE", "Dulce marrón, el favorito de muchos."),
    ("CUCURUCHO", "El cono crocante del helado."),
    ("PARACAIDAS", "Te salva al saltar de un avión."),
    ("MURCIELAGO", "Animal nocturno que vuela."),
    ("DINOSAURIO", "Reptil gigante que ya no existe."),
    ("BIBLIOTECA", "Lugar lleno de libros para leer."),
    ("AEROPUERTO", "De ahí salen y llegan los aviones."),
    ("LAVARROPAS", "Electrodoméstico que lava la ropa solo."),
    ("MICROONDAS", "Calienta la comida en un minuto."),
    ("ESCARABAJO", "Insecto de caparazón duro."),
    ("HIPOPOTAMO", "Animal enorme que vive en el río."),
]

# Spanish letter names as Whisper usually transcribes them ("la e" -> E).
AHORCADO_LETTER_NAMES = {
    "a": "A", "be": "B", "ce": "C", "de": "D", "e": "E", "efe": "F",
    "ge": "G", "hache": "H", "i": "I", "jota": "J", "ka": "K",
    "ele": "L", "eme": "M", "ene": "N", "eñe": "Ñ", "enie": "Ñ",
    "o": "O", "pe": "P", "cu": "Q", "ere": "R", "ese": "S",
    "te": "T", "u": "U", "uve": "V", "ve": "V", "equis": "X",
    "ye": "Y", "i griega": "Y", "zeta": "Z",
}

# How each letter is spoken back so single letters never sound cryptic.
AHORCADO_SPEAK = {
    "A": "a", "B": "be", "C": "ce", "D": "de", "E": "e", "F": "efe",
    "G": "ge", "H": "hache", "I": "i", "J": "jota", "K": "ka",
    "L": "ele", "M": "eme", "N": "ene", "Ñ": "eñe", "O": "o",
    "P": "pe", "Q": "cu", "R": "ere", "S": "ese", "T": "te",
    "U": "u", "V": "ve", "W": "uve doble", "X": "equis", "Y": "ye",
    "Z": "zeta",
}

AHORCADO_EXIT_WORDS = {"salir", "basta", "cancelar", "terminar"}

ahorcado_games = {}


def ahorcado_clean(text: str) -> str:
    """Uppercase letters only; tildes dropped, Ñ preserved."""
    table = str.maketrans("ÁÉÍÓÚÜáéíóúü", "AEIOUUaeiouu")
    cleaned = text.strip().translate(table).upper()
    return "".join(
        char for char in cleaned if char in "ABCDEFGHIJKLMNOPQRSTUVWXYZÑ"
    )


def ahorcado_parse_guess(text: str):
    """('letter', 'E') | ('word', 'PALABRA') | None from voice or typed input."""
    cleaned = normalized(text).strip(" .,!¿?¡")
    cleaned = re.sub(r"^(?:(?:la|el|una|un|letra|es)\s+)+", "", cleaned)
    if cleaned in ("ene", "enie") and re.search(r"eñe|enie", text.lower()):
        return ("letter", "Ñ")  # normalized() flattens eñe to ene; check the raw text
    if len(cleaned) == 1 and cleaned.isalpha():
        return ("letter", ahorcado_clean(cleaned))
    if cleaned in AHORCADO_LETTER_NAMES:
        return ("letter", AHORCADO_LETTER_NAMES[cleaned])
    word = ahorcado_clean(cleaned)
    if len(word) >= 2:
        return ("word", word)
    return None


def ahorcado_band(level: int):
    """Word-length band per level: the difficulty that rises each level."""
    if level <= 1:
        return (4, 5)
    if level == 2:
        return (6, 6)
    if level == 3:
        return (7, 7)
    if level == 4:
        return (8, 8)
    return (9, 10)


def ahorcado_attempts_for(word: str) -> int:
    """His rule: 4 attempts for 7+ letters, 3 attempts for 6 or fewer."""
    return 4 if len(word) >= 7 else 3


def ahorcado_pick_word(game):
    """Pick an unseen word from the level's band of the local bank."""
    lo, hi = ahorcado_band(game["level"])
    choices = [
        (word, hint) for word, hint in AHORCADO_BANK
        if lo <= len(word) <= hi and word not in game["used"]
    ]
    if not choices:  # the band ran out: reshuffle it and keep playing
        game["used"] = {
            word for word in game["used"] if not (lo <= len(word) <= hi)
        }
        choices = [(w, h) for w, h in AHORCADO_BANK if lo <= len(w) <= hi]
    word, hint = random.choice(choices)
    game["used"].add(word)
    return word, hint


def ahorcado_spelled(word: str) -> str:
    """'MATE' -> 'eme, a, te, e' so the word can be heard letter by letter."""
    return ", ".join(AHORCADO_SPEAK[char] for char in word)


def ahorcado_board_text(game) -> str:
    shown = " ".join(
        char if char in game["guessed"] else "▁" for char in game["word"]
    )
    wrong = ", ".join(sorted(game["wrong"])) or "ninguna"
    left = game["attempts_left"]
    intentos = "intento" if left == 1 else "intentos"
    vidas = "❤️" * game["lives"]
    return (
        f"🎯 AHORCADO · NIVEL {game['level']}\nPista: {game['hint']}\n\n{shown}\n\n"
        f"Letras que no están: {wrong}\nTe quedan {left} {intentos} · Vidas: {vidas}"
    )


def ahorcado_spoken_board(game) -> str:
    return "... ".join(
        AHORCADO_SPEAK[char] if char in game["guessed"] else "vacío"
        for char in game["word"]
    )


def ahorcado_keyboard():
    return [[{"text": "🚪 Salir del ahorcado", "callback_data": "ahorcado:quit"}]]


async def ahorcado_update_board(chat_id: int, game):
    """One live board message, edited in place; the keyboard never piles up."""
    text = ahorcado_board_text(game)
    keyboard = ahorcado_keyboard()
    mid = game.get("board_mid")
    if isinstance(mid, int):
        try:
            await telegram(
                "editMessageText", chat_id=chat_id, message_id=mid,
                text=text, reply_markup={"inline_keyboard": keyboard},
            )
            return
        except Exception:
            log.debug("Could not edit the ahorcado board; sending a fresh one")
    new_mid = await trivia_send_keyboard(chat_id, text, keyboard)
    game["board_mid"] = new_mid
    trivia_track(game, new_mid)


def ahorcado_cancel_timer(game):
    task = game.get("timer")
    if task and not task.done():
        task.cancel()
    game["timer"] = None


def ahorcado_clock_alive(chat_id: int, game, round_no: int) -> bool:
    return ahorcado_games.get(chat_id) is game and game["round"] == round_no


async def ahorcado_clock(chat_id: int, game, round_no: int):
    """Ten minutes per word, with spoken warnings from the clock voice."""
    try:
        elapsed = 0
        for left in AHORCADO_CLOCK_WARNINGS:
            await asyncio.sleep(AHORCADO_TIME_LIMIT - left - elapsed)
            elapsed = AHORCADO_TIME_LIMIT - left
            if not ahorcado_clock_alive(chat_id, game, round_no):
                return
            if left >= 120:
                aviso = f"Te quedan {left // 60} minutos para adivinar la palabra. ¡Dale!"
            else:
                aviso = "¡Último minuto! Apurate que se termina el tiempo."
            await send_voice(chat_id, aviso, voice=AHORCADO_CLOCK_VOICE)
        await asyncio.sleep(AHORCADO_CLOCK_WARNINGS[-1])
        if not ahorcado_clock_alive(chat_id, game, round_no):
            return
        async with game["lock"]:
            if not ahorcado_clock_alive(chat_id, game, round_no):
                return
            await ahorcado_word_lost(chat_id, game, "Se acabaron los diez minutos")
    except asyncio.CancelledError:
        pass


async def ahorcado_new_word(chat_id: int, game, name: str, intro: bool = False):
    """Deal the next word at the current level and restart the clock."""
    ahorcado_cancel_timer(game)
    game["round"] += 1
    word, hint = ahorcado_pick_word(game)
    game.update(
        word=word, hint=hint, guessed=set(), wrong=set(),
        attempts_left=ahorcado_attempts_for(word),
    )
    game["timer"] = asyncio.create_task(ahorcado_clock(chat_id, game, game["round"]))
    level, left = game["level"], game["attempts_left"]
    intentos = "intento" if left == 1 else "intentos"
    if intro:
        spoken = (
            f"{name}, ¡empieza el ahorcado! Nivel {level}: la palabra tiene "
            f"{len(word)} letras y tenés {left} {intentos} para adivinarla. "
            f"Pista: {hint} "
            f"Tenés {game['lives']} vidas y un reloj de diez minutos por palabra: "
            "si perdés la palabra, perdés una vida; si perdés las tres, volvés "
            "al nivel 1. Decime una letra, hablado o escrito, o la palabra entera."
        )
    else:
        spoken = (
            f"Nivel {level}, {name}: palabra de {len(word)} letras, "
            f"{left} {intentos}. Pista: {hint} Decime una letra."
        )
    voice_mid = await send_voice(chat_id, spoken, voice=AHORCADO_GAME_VOICE)
    trivia_track(game, voice_mid)
    if intro:
        header = (
            f"🎯 EMPIEZA EL AHORCADO · NIVEL {level}\n"
            "Adiviná la palabra letra por letra, hablado o escrito. Diez minutos "
            "por palabra; los intentos dependen del largo (4 si tiene 7 letras o "
            "más, 3 si tiene menos). Perder la palabra cuesta una vida; perder "
            "las 3 te devuelve al nivel 1. "
            "Decí 'salir' para terminar.\n\n"
            + ahorcado_board_text(game).split("\n", 1)[1]
        )
        mid = await trivia_send_keyboard(chat_id, header, ahorcado_keyboard())
        game["board_mid"] = mid
        trivia_track(game, mid)
    else:
        await ahorcado_update_board(chat_id, game)


async def ahorcado_word_won(chat_id: int, game, beat: str):
    """Win: level up (announced), one life back (announced), next word."""
    ahorcado_cancel_timer(game)
    name = get_preferred_name(chat_id) or "campeón"
    word = game["word"]
    game["level"] += 1
    if game["lives"] < AHORCADO_MAX_LIVES:
        game["lives"] += 1
        vidas = "una vida" if game["lives"] == 1 else f"{TRIVIA_NUMBER_WORDS.get(game['lives'], str(game['lives']))} vidas"
        vida_txt = f" Ganaste una vida: tenés {vidas}."
    else:
        vida_txt = f" Seguís con {AHORCADO_MAX_LIVES} vidas."
    spoken = (
        f"{beat} ¡Acertaste, {name}! Era {word}: {ahorcado_spelled(word)}. "
        f"Pasaste al nivel {game['level']}.{vida_txt}"
    )
    await send_voice(chat_id, spoken, voice=AHORCADO_LEVEL_VOICE)
    await ahorcado_new_word(chat_id, game, name)


async def ahorcado_word_lost(chat_id: int, game, reason: str):
    """Lose the word: one life less (announced); no lives left -> level 1."""
    ahorcado_cancel_timer(game)
    name = get_preferred_name(chat_id) or "campeón"
    word = game["word"]
    game["lives"] -= 1
    if game["lives"] <= 0:
        game["level"] = 1
        game["lives"] = AHORCADO_MAX_LIVES
        spoken = (
            f"{reason}, {name}. La palabra era {word}: {ahorcado_spelled(word)}. "
            f"Perdiste las {AHORCADO_MAX_LIVES} vidas: volvés al nivel 1, "
            f"con {AHORCADO_MAX_LIVES} vidas nuevas. ¡De nuevo, que se puede!"
        )
    else:
        vidas = (
            "te queda una vida" if game["lives"] == 1
            else f"te quedan {TRIVIA_NUMBER_WORDS.get(game['lives'], str(game['lives']))} vidas"
        )
        spoken = (
            f"{reason}, {name}. La palabra era {word}: {ahorcado_spelled(word)}. "
            f"Perdiste una vida: {vidas}."
        )
    await send_voice(chat_id, spoken, voice=AHORCADO_LEVEL_VOICE)
    await ahorcado_new_word(chat_id, game, name)


async def ahorcado_start(chat_id: int):
    # Retired Telegram game: preserve old entrypoints as safe redirects.
    await games_menu(chat_id)
    return
    clear_group_modes(chat_id)
    pending_music_query.pop(chat_id, None)
    if chat_id in trivia_games:
        await trivia_end(chat_id)
    old = ahorcado_games.pop(chat_id, None)
    if old:
        ahorcado_cancel_timer(old)
        await trivia_delete_flow(chat_id, old)
    game = {
        "level": 1, "lives": AHORCADO_MAX_LIVES, "used": set(),
        "lock": asyncio.Lock(), "round": 0, "timer": None, "board_mid": None,
        "word": "", "hint": "", "guessed": set(), "wrong": set(),
        "attempts_left": 0,
    }
    ahorcado_games[chat_id] = game
    name = get_preferred_name(chat_id) or "amigo"
    await ahorcado_new_word(chat_id, game, name, intro=True)


async def ahorcado_end(chat_id: int, summary: str = ""):
    game = ahorcado_games.pop(chat_id, None)
    if game:
        ahorcado_cancel_timer(game)
    await trivia_clear_keyboard(chat_id)
    if game:
        await trivia_delete_flow(chat_id, game)
    text = "🏁 TERMINÓ EL AHORCADO"
    if summary:
        text += f"\n{summary}"
    if game and game.get("level"):
        text += f"\nLlegaste al nivel {game['level']}."
    text += "\nEscribí /ahorcado o pulsá Juegos en el menú para jugar de nuevo."
    await send_text(chat_id, text)


async def ahorcado_guess(chat_id: int, raw: str):
    game = ahorcado_games.get(chat_id)
    if not game:
        return
    async with game["lock"]:
        await ahorcado_guess_locked(chat_id, game, raw)


async def ahorcado_guess_locked(chat_id: int, game, raw: str):
    name = get_preferred_name(chat_id) or "campeón"
    word = game["word"]
    parsed = ahorcado_parse_guess(raw)
    if parsed is None:
        await send_text(
            chat_id,
            "No entendí. Decime una sola letra, hablado o escrito, "
            "la palabra entera, o 'salir' para terminar el ahorcado.",
        )
        return
    kind, value = parsed
    beat = None
    if kind == "word":
        if value == word:
            await ahorcado_word_won(chat_id, game, f"¡Sí, {name}!")
            return
        game["attempts_left"] -= 1
        left = game["attempts_left"]
        beat = (
            f"No, la palabra no es {value}. "
            + ("Te queda un intento." if left == 1 else f"Te quedan {left} intentos.")
        )
    else:
        letter = value
        if letter in game["guessed"] or letter in game["wrong"]:
            beat = f"Ya probaste la {AHORCADO_SPEAK[letter]}. Decime otra letra."
            _, voice_mid = await asyncio.gather(
                ahorcado_update_board(chat_id, game),
                send_voice(chat_id, beat, voice=AHORCADO_GAME_VOICE),
            )
            trivia_track(game, voice_mid)
            return
        if letter in word:
            game["guessed"].add(letter)
            count = word.count(letter)
            veces = "una vez" if count == 1 else f"{TRIVIA_NUMBER_WORDS.get(count, str(count))} veces"
            beat = f"¡La {AHORCADO_SPEAK[letter]} aparece {veces}! "
        else:
            game["wrong"].add(letter)
            game["attempts_left"] -= 1
            left = game["attempts_left"]
            beat = f"La {AHORCADO_SPEAK[letter]} no está. "
            beat += "Te queda un intento." if left == 1 else f"Te quedan {left} intentos."
    if all(char in game["guessed"] for char in word):
        await ahorcado_word_won(chat_id, game, beat)
        return
    if game["attempts_left"] <= 0:
        await ahorcado_word_lost(chat_id, game, "Te quedaste sin intentos")
        return
    beat += " " + ahorcado_spoken_board(game) + "."
    _, voice_mid = await asyncio.gather(
        ahorcado_update_board(chat_id, game),
        send_voice(chat_id, beat, voice=AHORCADO_GAME_VOICE),
    )
    trivia_track(game, voice_mid)


WEB_GAMES_URL = "https://cafe-sabroso.onrender.com/amor-con-aroma-a-cafe"
WEB_GAMES_TITLE = "Amor con aroma a café ☕ 🧉 🧁 ❤️"
WEB_GAMES_DESCRIPTION = (
    "Animate a jugar y compartir un momento lindo, lleno de amor. "
    "Elegí tu juego en la página. Los juegos anteriores de este chat se retiraron."
)


async def games_menu(chat_id: int):
    # Mini Apps are supported in private chats. Group chats keep the same HTTPS
    # destination as a normal link. Never copy or redeploy the web game here.
    play = {"text": "A jugar"}
    play["web_app" if chat_id > 0 else "url"] = {"url": WEB_GAMES_URL} if chat_id > 0 else WEB_GAMES_URL
    await send_text(
        chat_id, WEB_GAMES_TITLE + "\n\n" + WEB_GAMES_DESCRIPTION +
        "\n\nSi preferís tu navegador, usá el enlace alternativo y la opción Abrir en… de Telegram.",
        reply_markup={"inline_keyboard": [
            [play],
            [{"text": "Abrir juegos en el navegador", "url": WEB_GAMES_URL}],
            [{"text": "Volver al menú principal", "callback_data": "mode:menu"}],
        ]},
    )


async def welcome(chat_id: int, fallback_name=None):
    # A free Render filesystem is replaced on deploy. Never block the bot on a
    # saved preference that may no longer exist; /nombre remains available.
    group_selection.pop(chat_id, None)
    pending_music_query.pop(chat_id, None)
    name = get_preferred_name(chat_id) or fallback_name or "amigo"
    text = (
        f"📋 MENÚ PRINCIPAL\nHola, {name}. Pulsa uno de estos botones para empezar. "
        "En los modos de dúo a deceto (de 2 a 10 voces), las voces conversan entre ellas "
        "y contigo, y se llaman por su nombre en un mismo audio. "
        "Después de elegir el modo, pulsa las voces en los botones que aparecen.\n\n"
        "También puedes escribirme o enviarme una nota de voz. Para volver a ver estos botones, "
        "pulsa el botón Menú de Telegram junto al campo de mensaje o escribe /menu."
    )
    keyboard = [
        [{"text": "🎙️ Individual: elegir una voz", "callback_data": "mode:single"}],
        [{"text": "👥 Dúo: 2 voces", "callback_data": "mode:duo"}, {"text": "👥 Trío: 3 voces", "callback_data": "mode:trio"}],
        [{"text": "👥 Cuarteto: 4 voces", "callback_data": "mode:quartet"}, {"text": "👥 Quinteto: 5 voces", "callback_data": "mode:quintet"}],
        [{"text": "👥 Sexteto: 6 voces", "callback_data": "mode:sextet"}, {"text": "👥 Sépteto: 7 voces", "callback_data": "mode:septet"}],
        [{"text": "👥 Octeto: 8 voces", "callback_data": "mode:octet"}, {"text": "👥 Noneto: 9 voces", "callback_data": "mode:nonet"}],
        [{"text": "👥 Deceto: 10 voces", "callback_data": "mode:decet"}, {"text": "📖 Historia: 4 personajes", "callback_data": "mode:story"}],
        [{"text": "🎵 Buscar música", "callback_data": "mode:music"}],
        [{"text": "Amor con aroma a café ☕ 🧉 🧁 ❤️", "callback_data": "mode:games"}],
    ]
    await send_text(chat_id, text, reply_markup={"inline_keyboard": keyboard})
    await send_voice(chat_id, f"Hola, {name}. Ya estoy listo. Elige hasta diez voces o una historia para empezar.")


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
            if action in GROUP_MODE_SIZES:
                await start_group_mode(chat_id, action)
            else:
                await welcome(chat_id, name)
            return
        if text.startswith("/start") or text.startswith("/menu"):
            await welcome(chat_id, message.get("from", {}).get("first_name"))
            return
        if text.startswith("/nombre"):
            await ask_preferred_name(chat_id)
            return
        if text.startswith("/duo"):
            await start_group_mode(chat_id, "duo")
            return
        if text.startswith("/trio"):
            await start_group_mode(chat_id, "trio")
            return
        if text.startswith("/cuarteto"):
            await start_group_mode(chat_id, "quartet")
            return
        if text.startswith("/quinteto"):
            await start_group_mode(chat_id, "quintet")
            return
        if text.startswith("/sexteto"):
            await start_group_mode(chat_id, "sextet")
            return
        if text.startswith("/septeto"):
            await start_group_mode(chat_id, "septet")
            return
        if text.startswith("/octeto"):
            await start_group_mode(chat_id, "octet")
            return
        if text.startswith("/noneto"):
            await start_group_mode(chat_id, "nonet")
            return
        if text.startswith("/deceto"):
            await start_group_mode(chat_id, "decet")
            return
        if text.startswith("/historia"):
            await start_group_mode(chat_id, "story")
            return
        if text.startswith("/juegos"):
            await games_menu(chat_id)
            return
        if text.startswith("/ahorcado"):
            await ahorcado_start(chat_id)
            return
        if text.startswith("/ruleta"):
            group_selection.pop(chat_id, None)
            await trivia_menu(chat_id)
            return
        if text.startswith("/individual"):
            group_selection.pop(chat_id, None)
            clear_group_modes(chat_id)
            await send_text(chat_id, f"Modo individual activado. Tu voz actual es {VOICES[selected_voice[chat_id]]}. Elige otra abajo si quieres cambiarla.")
            await send_voice(chat_id, "Modo individual activado. Seguimos con una sola voz.")
            await show_voices(chat_id)
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
            pending_weather_query.pop(chat_id, None)
            pending_weather_country.pop(chat_id, None)
            pending_music_query.pop(chat_id, None)
            group_selection.pop(chat_id, None)
            trivia_games.pop(chat_id, None)
            ahorcado_games.pop(chat_id, None)
            await send_text(chat_id, "Conversación reiniciada.")
            return
        if text.startswith("/musica") or text.startswith("/music"):
            await search_music(chat_id, text.partition(" ")[2])
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
        if chat_id in pending_music_query and not (chat_id in pending_weather_query or is_weather_query(user_text)):
            if re.search(r"\b(salir|basta|cancelar|terminar)\b", normalized(user_text)):
                pending_music_query.pop(chat_id, None)
                await send_text(chat_id, "Listo, saliste de la búsqueda de música. Escribí /musica para volver.")
                await send_voice(chat_id, "Listo, dejamos la música acá.")
                return
            await search_music(chat_id, user_text)
            return
        ahorcado = ahorcado_games.get(chat_id)
        if ahorcado:
            if re.search(r"\b(salir|basta|cancelar|terminar)\b", normalized(user_text)):
                await ahorcado_end(chat_id)
                return
            await ahorcado_guess(chat_id, user_text)
            return
        game = trivia_games.get(chat_id)
        if game and game.get("phase") == "question":
            if re.search(r"\b(salir|basta|cancelar|terminar)\b", normalized(user_text)):
                await trivia_end(chat_id)
                return
            matched = trivia_match_answer(user_text, game["current"]["options"])
            if matched is None:
                await send_text(
                    chat_id,
                    "No entendí la respuesta. Decí el número o el nombre de la "
                    "opción, o 'salir' para terminar la ruleta.",
                )
                return
            await trivia_handle_answer(chat_id, matched)
            return
        if game and chat_id not in group_selection and re.search(
            r"\b(gira|girar|giralo|girala|ruleta|dale|otra|siguiente|de nuevo)\b",
            normalized(user_text),
        ):
            await trivia_spin(chat_id)
            return
        if not game and chat_id not in group_selection and re.search(
            r"\bruleta\b|preguntados|\bgira\b|\bgirar\b|\bgiralo\b|\bgirala\b",
            normalized(user_text),
        ):
            await trivia_menu(chat_id)
            return
        if chat_id not in group_selection and re.search(
            r"\bahorcado\b", normalized(user_text)
        ):
            await ahorcado_start(chat_id)
            return
        if chat_id not in group_selection and re.search(
            r"\bjuegos\b|\bjuego\b", normalized(user_text)
        ):
            await games_menu(chat_id)
            return
        # Weather follow-ups such as "poné el de Quilmes" must not become music searches.
        if chat_id in pending_weather_query or is_weather_query(user_text):
            status, weather_text, source = await prepare_live_query(chat_id, user_text)
            await send_text(chat_id, weather_text + (f"\n\nFuente: {source}" if source else ""))
            await send_voice(chat_id, weather_text)
            return
        music_query = music_query_from_text(user_text)
        if music_query is not None:
            await search_music(chat_id, music_query)
            return
        status, user_text, source = await prepare_live_query(chat_id, user_text)
        if status == "ask":
            await send_text(chat_id, user_text)
            return
        source_text = f"\n\nFuente: {source}" if source else ""
        pending = group_selection.get(chat_id)
        if pending:
            size = GROUP_MODE_SIZES[pending["kind"]]
            await send_text(
                chat_id,
                f"Estás eligiendo las voces del modo {GROUP_MODE_LABELS[pending['kind']]}: llevas "
                f"{len(pending['voices'])} de {size}. Pulsa la siguiente voz en los botones de arriba "
                "para empezar, o escribe /menu para cancelar.",
            )
            return
        if story_enabled[chat_id]:
            voices = story_pairs[chat_id]
            replies = await answer_story(chat_id, user_text)
            combined = "\n\n".join(
                f"{voice_name(voice)}: {reply}" for voice, reply in zip(voices, replies)
            )
            await send_text(chat_id, combined + source_text)
            await send_group_voice(chat_id, list(zip(voices, replies)))
            return
        for kind in DIALOGUE_KINDS:
            enabled, pairs = GROUP_MODE_FLAGS[kind]
            if enabled[chat_id]:
                voices = pairs[chat_id]
                replies = await answer_dialogue(chat_id, user_text, voices)
                combined = "\n\n".join(
                    f"{voice_name(voice)}: {reply}" for voice, reply in zip(voices, replies)
                )
                await send_text(chat_id, combined + source_text)
                await send_group_voice(chat_id, list(zip(voices, replies)))
                return
        result = await answer(chat_id, user_text)
        await send_text(chat_id, result + source_text)
        await send_voice(chat_id, result)
    except Exception:
        log.exception("Failed to handle message")
        await send_text(chat_id, "Tuve un problema técnico. Probá de nuevo en un momento.")


async def update_selection_message(chat_id: int, callback: dict, text: str, keyboard):
    """Edit the tapped message in place so only one selection keyboard stays live."""
    message = callback.get("message") or {}
    message_id = message.get("message_id")
    if message_id:
        try:
            await telegram(
                "editMessageText", chat_id=chat_id, message_id=message_id,
                text=text, reply_markup={"inline_keyboard": keyboard},
            )
            return
        except Exception:
            log.exception("Could not edit the selection message; sending a new one")
    await send_text(chat_id, text, reply_markup={"inline_keyboard": keyboard})


async def advance_group_selection(chat_id: int, callback: dict, kind: str, voice: str):
    """One tolerant state machine for every group-mode voice pick.

    Any pick button from any step of the same mode advances the pending
    selection, so a tap on an older keyboard never silently restarts it.
    """
    callback_id = callback["id"]
    if voice not in VOICES:
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Esa voz no está disponible.")
        return
    session = group_selection.get(chat_id)
    if not session or session["kind"] != kind:
        session = {"kind": kind, "voices": []}
        group_selection[chat_id] = session
    voices = session["voices"]
    if voice in voices:
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Elige voces distintas.")
        return
    voices.append(voice)
    size = GROUP_MODE_SIZES[kind]
    if len(voices) < size:
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=f"Voz {len(voices)}: {voice_name(voice)}")
        await update_selection_message(
            chat_id, callback,
            f"Modo {GROUP_MODE_LABELS[kind]}: voz {len(voices)}: {voice_name(voice)}. "
            f"Elige la siguiente ({len(voices) + 1} de {size}).",
            voice_keyboard(chat_id, f"gsel:{kind}", exclude=voices),
        )
        return
    group_selection.pop(chat_id, None)
    await complete_group_selection(chat_id, callback, kind, list(voices))


def group_samples(kind: str, names, name: str):
    """Intro lines for a completed selection; dialogue modes show the voices naming each other."""
    if kind == "story":
        return [
            f"{name}, soy {names[0]}, el primer personaje de nuestra historia.",
            f"Yo soy {names[1]}, {name}, y continuaré lo que empiece {names[0]}.",
            f"Soy {names[2]}, {name}. Mi personaje traerá un giro a la escena.",
            f"Y yo soy {names[3]}, {name}. Mi personaje cerrará la escena. Decinos el tema de la historia.",
        ]
    samples = [f"Hola, {name}. Soy {names[0]}. {names[1]}, ¿arrancamos charlando con {name}?"]
    for index in range(1, len(names) - 1):
        samples.append(f"¡Vamos, {names[index - 1]}! {name}, yo soy {names[index]} y sumo otra mirada.")
    samples.append(
        f"¡Vamos, {names[-2]}! Y yo soy {names[-1]}, {name}. "
        "Mandanos un mensaje o un audio y charlamos entre todos."
    )
    return samples


async def complete_group_selection(chat_id: int, callback: dict, kind: str, voices):
    if kind == "trivia":
        await complete_trivia_lineup(chat_id, callback, voices)
        return
    voices = tuple(voices)
    clear_group_modes(chat_id)
    flags, pairs = GROUP_MODE_FLAGS[kind]
    flags[chat_id] = True
    pairs[chat_id] = voices
    selected_voice[chat_id] = voices[0]
    voice_enabled[chat_id] = True
    names = [voice_name(item) for item in voices]
    name = get_preferred_name(chat_id) or callback.get("from", {}).get("first_name") or "amigo"
    samples = group_samples(kind, names, name)
    message = callback.get("message") or {}
    if message.get("message_id"):
        try:
            await telegram(
                "editMessageReplyMarkup", chat_id=chat_id,
                message_id=message["message_id"],
                reply_markup={"inline_keyboard": []},
            )
        except Exception:
            log.exception("Could not clear the selection keyboard")
    await telegram(
        "answerCallbackQuery", callback_query_id=callback["id"],
        text=f"{GROUP_MODE_LABELS[kind].capitalize()}: {', '.join(names)}",
    )
    combined = "\n\n".join(f"{speaker}: {sample}" for speaker, sample in zip(names, samples))
    await send_text(chat_id, combined)
    await send_group_voice(chat_id, list(zip(voices, samples)))


async def handle_callback(callback: dict):
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")
    callback_id = callback["id"]
    if data == "mode:trivia" or data.startswith(("ahorcado:", "trivia:", "tans:")):
        await telegram("answerCallbackQuery", callback_query_id=callback_id,
                       text="Este juego se retiró. Abrí Amor con aroma a café.")
        await games_menu(chat_id)
        return
    if data == "mode:menu":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Menú principal")
        await welcome(chat_id, callback.get("from", {}).get("first_name"))
        return
    if data == "mode:single":
        group_selection.pop(chat_id, None)
        clear_group_modes(chat_id)
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Modo de una voz")
        await show_voices(chat_id)
        return
    mode_kinds = {
        "mode:duo": ("duo", "Modo dúo"),
        "mode:trio": ("trio", "Modo trío"),
        "mode:quartet": ("quartet", "Modo cuarteto"),
        "mode:quintet": ("quintet", "Modo quinteto"),
        "mode:sextet": ("sextet", "Modo sexteto"),
        "mode:septet": ("septet", "Modo sépteto"),
        "mode:octet": ("octet", "Modo octeto"),
        "mode:nonet": ("nonet", "Modo noneto"),
        "mode:decet": ("decet", "Modo deceto"),
        "mode:story": ("story", "Historia"),
    }
    if data in mode_kinds:
        kind, label = mode_kinds[data]
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=label)
        await start_group_mode(chat_id, kind)
        return
    if data.startswith("gself:"):
        _, kind, answer = data.split(":", 2)
        if kind not in GROUP_MODE_SIZES:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Empecemos de nuevo.")
            return
        include_self = answer == "yes"
        await telegram(
            "answerCallbackQuery", callback_query_id=callback_id,
            text="Tu voz participa" if include_self else "Elegís todas las voces",
        )
        await pick_group_voices(chat_id, kind, include_self)
        return
    if data == "mode:music":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Búsqueda de música")
        await search_music(chat_id, "")
        return
    if data == "mode:games":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Juegos")
        await games_menu(chat_id)
        return
    if data == "ahorcado:start":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="El Ahorcado")
        await ahorcado_start(chat_id)
        return
    if data == "ahorcado:quit":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Fin del ahorcado")
        await ahorcado_end(chat_id)
        return
    if data == "mode:trivia":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="La Ruleta")
        group_selection.pop(chat_id, None)
        await trivia_menu(chat_id)
        return
    if data.startswith("tans:"):
        try:
            index = int(data.split(":", 1)[1])
        except ValueError:
            index = -1
        game = trivia_games.get(chat_id)
        if not game or game.get("phase") != "question" or not (0 <= index <= 3):
            await telegram(
                "answerCallbackQuery", callback_query_id=callback_id,
                text="Esa pregunta ya pasó. Escribí /ruleta para jugar de nuevo.",
            )
            return
        await telegram("answerCallbackQuery", callback_query_id=callback_id)
        await trivia_handle_answer(chat_id, index, callback)
        return
    if data.startswith("trivia:"):
        action = data.split(":", 1)[1]
        if action == "start:classic":
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Ruleta clásica")
            await trivia_begin(chat_id, False)
        elif action == "start:countries":
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Ruleta de países")
            await trivia_begin(chat_id, True)
        elif action == "lineup":
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Elegir las voces del juego")
            await start_trivia_lineup(chat_id)
        elif action == "spin":
            if not trivia_games.get(chat_id):
                await telegram(
                    "answerCallbackQuery", callback_query_id=callback_id,
                    text="La ruleta se reinició. Escribí /ruleta para jugar de nuevo.",
                )
                return
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="🎡 Girando...")
            await trivia_spin(chat_id)
        elif action == "menu":
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="La Ruleta")
            await trivia_menu(chat_id)
        elif action == "quit":
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Fin de la ruleta")
            await trivia_end(chat_id)
        else:
            await telegram("answerCallbackQuery", callback_query_id=callback_id)
        return
    legacy_step, _, legacy_voice = data.partition(":")
    if legacy_step in ("duo1", "duo2", "trio1", "trio2", "trio3"):
        kind = "duo" if legacy_step.startswith("duo") else "trio"
        await advance_group_selection(chat_id, callback, kind, legacy_voice)
        return
    if legacy_step == "four":
        session = group_selection.get(chat_id)
        if session and session["kind"] in ("quartet", "story"):
            await advance_group_selection(chat_id, callback, session["kind"], legacy_voice)
        else:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Empecemos de nuevo.")
            await send_text(chat_id, "Esa selección ya no está activa. Elige el modo otra vez desde el menú.")
        return
    if legacy_step == "gsel":
        _, kind, voice = data.split(":", 2)
        if kind not in GROUP_MODE_SIZES:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Empecemos de nuevo.")
            return
        await advance_group_selection(chat_id, callback, kind, voice)
        return
    if not data.startswith("voice:"):
        await telegram("answerCallbackQuery", callback_query_id=callback_id)
        return
    voice = data.split(":", 1)[1]
    if voice not in VOICES:
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Esa voz no está disponible.")
        return
    group_selection.pop(chat_id, None)
    clear_group_modes(chat_id)
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


async def keep_alive():
    """Render free sleeps after ~15 minutes without traffic, and his messages
    then hit a 50+ second cold start (and pending updates get dropped on the
    restart). Ping our own health endpoint so the bot stays warm. Free plan
    covers one always-on service (750 h/month)."""
    while True:
        await asyncio.sleep(600)
        try:
            await http.get(f"{PUBLIC_URL}/", timeout=15)
        except Exception:
            log.exception("Keep-alive ping failed")


@app.on_event("startup")
async def startup():
    try:
        await telegram("setMyCommands", commands=BOT_COMMANDS)
        await telegram("setChatMenuButton", menu_button={"type": "commands"})
        log.info("Telegram command menu configured with %s commands", len(BOT_COMMANDS))
    except Exception:
        log.exception("Could not configure Telegram command menu")
    if PUBLIC_URL:
        payload = {"url": f"{PUBLIC_URL}/webhook", "drop_pending_updates": True}
        if WEBHOOK_SECRET:
            payload["secret_token"] = WEBHOOK_SECRET
        await telegram("setWebhook", **payload)
        log.info("Telegram webhook configured at %s/webhook", PUBLIC_URL)
        asyncio.create_task(keep_alive())


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


# The shared web ruleta ("Amor con aroma a café") lives on the same service:
# page, rooms, websockets and narration audio. Additive only - it never
# touches the Telegram or WhatsApp paths.
try:
    from webapp import router as web_router
    app.include_router(web_router)
    log.info("Web ruleta mounted at /amor-con-aroma-a-cafe")
except Exception:
    log.exception("Could not mount the web ruleta")


# One Render service hosts both bots: when the WhatsApp Cloud API is
# configured, its webhook lives under /whatsapp (verify and receive at
# /whatsapp/webhook) on the same uvicorn process.
if os.getenv("WHATSAPP_ACCESS_TOKEN"):
    try:
        from whatsapp_app import router as whatsapp_router
        app.include_router(whatsapp_router, prefix="/whatsapp")
        log.info("WhatsApp webhook mounted at /whatsapp/webhook")
    except Exception:
        log.exception("Could not mount the WhatsApp webhook router")
