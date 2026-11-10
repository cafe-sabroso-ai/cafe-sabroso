import asyncio
import logging
import os
import re
import sqlite3
import tempfile
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
VOICES = {
    "espeak-es-419": "Voz Lector - estilo NVDA",
    "espeak-es-419-m1": "Voz Lector Masculina - estilo NVDA",
    "espeak-es-419-m3": "Voz Lector Grave - estilo NVDA",
    "espeak-es-419-f1": "Voz Lector Femenina - estilo NVDA",
    "espeak-es-419-f2": "Voz Lector Aguda - estilo NVDA",
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
story_enabled = defaultdict(lambda: False)
story_pairs = {}
GROUP_MODE_SIZES = {"duo": 2, "trio": 3, "quartet": 4, "quintet": 5, "sextet": 6, "story": 4}
GROUP_MODE_LABELS = {
    "duo": "dúo", "trio": "trío", "quartet": "cuarteto",
    "quintet": "quinteto", "sextet": "sexteto", "story": "historia",
}
GROUP_MODE_FLAGS = {
    "duo": (duo_enabled, duo_pairs),
    "trio": (trio_enabled, trio_pairs),
    "quartet": (quartet_enabled, quartet_pairs),
    "quintet": (quintet_enabled, quintet_pairs),
    "sextet": (sextet_enabled, sextet_pairs),
    "story": (story_enabled, story_pairs),
}
# Conversation modes where the voices address each other by name; story is a
# narration with its own prompt.
DIALOGUE_KINDS = ("duo", "trio", "quartet", "quintet", "sextet")


def clear_group_modes(chat_id: int):
    for flags, _ in GROUP_MODE_FLAGS.values():
        flags[chat_id] = False
group_selection = {}
pending_weather_query = {}
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
    {"command": "historia", "description": "Crear una historia con cuatro personajes"},
    {"command": "musica", "description": "Buscar un artista o una canción"},
    {"command": "nombre", "description": "Cambiar cómo te llama el bot"},
    {"command": "solo_texto", "description": "Desactivar las respuestas de audio"},
    {"command": "con_voz", "description": "Activar las respuestas de audio"},
    {"command": "reset", "description": "Reiniciar la conversación"},
]
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
                raise RuntimeError(f"espeak-ng failed: {stderr.decode()[:300]}")
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
        log.info("Sent individual voice message for chat %s", chat_id)
    except Exception:
        log.exception("Could not synthesize or send voice")


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
    word_limit = 60 if len(voices) <= 2 else 45
    prompt = (
        SYSTEM_PROMPT
        + f" En esta conversación participan {len(voices)} voces: {labels}. "
        "Respondé al pedido como una conversación entre ellas: cada una habla exactamente "
        f"una vez, en ese orden. {names[0]} responde al pedido y se dirige a {names[1]} "
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
        prompt = (
            SYSTEM_PROMPT
            + f" En esta conversación de {len(voices)} voces ({', '.join(names)}) sos {speaker}. {role} "
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
    match = re.search(r"(?:en|para|de)\s+([^?!\n]{2,80})", text, re.IGNORECASE)
    if not match:
        return None
    place = match.group(1)
    place = re.sub(r"\b(hoy|manana|ahora|actualmente|esta semana)\b", "", place, flags=re.IGNORECASE)
    return place.strip(" ,.;") or None


async def weather_context(place: str, question: str):
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
    response = await http.get(
        geocoding_url,
        params={"name": place[:80], "count": 1, "language": "es", "format": "json"},
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise ValueError("No encontré ese lugar. Probá con ciudad y país.")
    location = results[0]
    response = await http.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": location["latitude"], "longitude": location["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": 1,
        },
    )
    response.raise_for_status()
    data = response.json()
    current = data["current"]
    daily = data["daily"]
    location_name = ", ".join(str(value) for value in (
        location.get("name"), location.get("admin1"), location.get("country")
    ) if value)
    condition = WEATHER_CODES.get(current.get("weather_code"), f"código meteorológico {current.get('weather_code')}")
    current_time = datetime.fromisoformat(current["time"]).strftime("%H horas %M")
    precipitation = (
        "sin precipitación registrada" if not current.get("precipitation")
        else f"precipitación de {current['precipitation']} milímetros"
    )
    context = (
        f"Datos reales consultados ahora en Open-Meteo para {location_name}, "
        f"actualizados a las {current_time}, hora local de {location.get('name')}: {condition}; "
        f"temperatura de {current.get('temperature_2m')} grados Celsius; "
        f"sensación térmica de {current.get('apparent_temperature')} grados; "
        f"humedad del {current.get('relative_humidity_2m')} por ciento; {precipitation}; "
        f"viento de {current.get('wind_speed_10m')} kilómetros por hora. "
        f"Para hoy: mínima de {daily['temperature_2m_min'][0]} grados, "
        f"máxima de {daily['temperature_2m_max'][0]} grados y probabilidad máxima de precipitación "
        f"del {daily['precipitation_probability_max'][0]} por ciento.\n"
        f"Pregunta original: {question}\n"
        "Para el clima usá únicamente estos valores y esta fecha; no agregues condiciones ni cifras no incluidas. "
        "La primera voz debe mencionar que los datos son de Open-Meteo."
    )
    return context, "https://open-meteo.com/"


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
    response = await http.get(
        "https://itunes.apple.com/search",
        params={"term": query[:120], "entity": "song", "limit": 10, "country": "AR"},
        timeout=20,
    )
    response.raise_for_status()
    tracks = []
    for item in response.json().get("results", []):
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
    query_normalized = normalized(query)
    tracks.sort(key=lambda track: (
        normalized(track["artist"]) != query_normalized,
        query_normalized not in normalized(track["artist"]),
        query_normalized not in normalized(track["title"]),
    ))
    return tracks[:5]


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
        return
    pending_music_query.pop(chat_id, None)
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
        await send_text(chat_id, text, reply_markup={"inline_keyboard": [
            [{"text": "Buscar en Spotify", "url": spotify_music_url(query)}],
            [{"text": "Buscar en Internet Archive", "url": archive_music_url(query)}],
        ]})
        return
    summary = f"Resultados de música para “{query}”."
    if tracks:
        summary += " Las fichas y muestras son de Apple Music; Spotify abre su búsqueda oficial."
    if downloads:
        summary += " Las descargas de Internet Archive tienen una licencia explícita y llegan como archivo MP3 directo."
    await send_text(chat_id, summary)
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
    if chat_id in pending_weather_query:
        original = pending_weather_query.pop(chat_id)
        try:
            context, source = await weather_context(user_text, original)
            return "ready", context, source
        except ValueError as error:
            return "ask", str(error), None
        except Exception:
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
    if is_weather_query(user_text):
        place = weather_place(user_text)
        if not place:
            pending_weather_query[chat_id] = user_text
            return "ask", "¿Para qué ciudad o lugar querés saber el clima?", None
        try:
            context, source = await weather_context(place, user_text)
            return "ready", context, source
        except ValueError as error:
            return "ask", str(error), None
        except Exception:
            log.exception("Open-Meteo lookup failed")
            return "ask", "No pude consultar Open-Meteo ahora. Probá de nuevo en un momento.", None
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
    group_selection[chat_id] = {"kind": kind, "voices": []}
    size = GROUP_MODE_SIZES[kind]
    numbers = {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis"}
    if kind == "story":
        text = "Modo historia: elige la primera de cuatro voces distintas. Serán cuatro personajes que continúan una misma escena."
    elif kind == "duo":
        text = "Modo dúo: elige la primera voz. Después elegirás la segunda y conversarán entre ellas en un solo audio."
    else:
        text = (
            f"Modo {GROUP_MODE_LABELS[kind]}: elige la primera de {numbers[size]} voces distintas. "
            "Conversarán entre ellas en un solo audio."
        )
    await send_text(
        chat_id, text,
        reply_markup={"inline_keyboard": voice_keyboard(chat_id, f"gsel:{kind}")},
    )


async def welcome(chat_id: int, fallback_name=None):
    # A free Render filesystem is replaced on deploy. Never block the bot on a
    # saved preference that may no longer exist; /nombre remains available.
    group_selection.pop(chat_id, None)
    name = get_preferred_name(chat_id) or fallback_name or "amigo"
    text = (
        f"📋 MENÚ PRINCIPAL\nHola, {name}. Pulsa uno de estos botones para empezar. "
        "En los modos dúo, trío, cuarteto, quinteto y sexteto, las voces conversan entre ellas "
        "y se llaman por su nombre en un mismo audio. "
        "Después de elegir el modo, pulsa las voces en los botones que aparecen.\n\n"
        "También puedes escribirme o enviarme una nota de voz. Para volver a ver estos botones, "
        "pulsa el botón Menú de Telegram junto al campo de mensaje o escribe /menu."
    )
    keyboard = [
        [{"text": "🎙️ Individual: elegir una voz", "callback_data": "mode:single"}],
        [{"text": "👥 Dúo: 2 voces", "callback_data": "mode:duo"}, {"text": "👥 Trío: 3 voces", "callback_data": "mode:trio"}],
        [{"text": "👥 Cuarteto: 4 voces", "callback_data": "mode:quartet"}, {"text": "👥 Quinteto: 5 voces", "callback_data": "mode:quintet"}],
        [{"text": "👥 Sexteto: 6 voces", "callback_data": "mode:sextet"}, {"text": "📖 Historia: 4 personajes", "callback_data": "mode:story"}],
        [{"text": "🎵 Buscar música", "callback_data": "mode:music"}],
    ]
    await send_text(chat_id, text, reply_markup={"inline_keyboard": keyboard})
    await send_voice(chat_id, f"Hola, {name}. Ya estoy listo. Elige hasta seis voces o una historia para empezar.")


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
        if text.startswith("/historia"):
            await start_group_mode(chat_id, "story")
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
            pending_music_query.pop(chat_id, None)
            group_selection.pop(chat_id, None)
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
        if chat_id in pending_music_query:
            await search_music(chat_id, user_text)
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
        "mode:story": ("story", "Historia"),
    }
    if data in mode_kinds:
        kind, label = mode_kinds[data]
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=label)
        await start_group_mode(chat_id, kind)
        return
    if data == "mode:music":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Búsqueda de música")
        await search_music(chat_id, "")
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
