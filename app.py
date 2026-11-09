import asyncio
import logging
import os
import re
import sqlite3
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
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
    "pasos, listas de consignas ni explicaciones sobre cómo respondiste."
)

app = FastAPI(title="Telegram Spanish Voice AI Bot")
selected_voice = defaultdict(lambda: DEFAULT_VOICE)
voice_enabled = defaultdict(lambda: True)
histories = defaultdict(lambda: deque(maxlen=12))
duo_enabled = defaultdict(lambda: False)
duo_first = {}
duo_pairs = {}
trio_enabled = defaultdict(lambda: False)
trio_selection = {}
trio_pairs = {}
quartet_enabled = defaultdict(lambda: False)
quartet_pairs = {}
story_enabled = defaultdict(lambda: False)
story_pairs = {}
four_selection = {}
pending_weather_query = {}
pending_sports_query = {}
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


def voice_name(voice: str) -> str:
    return VOICES[voice].split(" - ", 1)[0]


def clean_turn(text: str, names) -> str:
    label = "(?:" + "|".join(re.escape(name) for name in names) + ")"
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


async def answer_group(chat_id: int, user_text: str, voices):
    history = histories[chat_id]
    name = get_preferred_name(chat_id)
    name_instruction = f" La persona prefiere que la llamen {name}. Empezá tu turno usando ese nombre de forma natural." if name else ""
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
            SYSTEM_PROMPT + name_instruction
            + f" En esta conversación de {len(voices)} voces sos {speaker}. {role} "
            "Podés reaccionar naturalmente a los comentarios anteriores. Escribí únicamente "
            "el texto final hablado de tu turno, sin análisis ni rótulos. Usá un máximo "
            "de 60 palabras y no te presentes ni anuncies que sos una IA."
        )
        messages = [{"role": "system", "content": prompt}]
        messages.extend(history)
        previous = "\n\n".join(f"{speaker_name} respondió: {reply}" for speaker_name, reply in zip(names, replies))
        content = user_text
        if previous:
            content += f"\n\n{previous}\n\nAhora respondé vos como {speaker}."
        messages.append({"role": "user", "content": content})
        replies.append(clean_turn(await complete(messages), names))
    history.append({"role": "user", "content": user_text})
    history.append({
        "role": "assistant",
        "content": "\n".join(f"{speaker}: {reply}" for speaker, reply in zip(names, replies)),
    })
    return replies


async def answer_duo(chat_id: int, user_text: str):
    return await answer_group(chat_id, user_text, duo_pairs[chat_id])


async def answer_trio(chat_id: int, user_text: str):
    return await answer_group(chat_id, user_text, trio_pairs[chat_id])


async def answer_quartet(chat_id: int, user_text: str):
    return await answer_group(chat_id, user_text, quartet_pairs[chat_id])


async def answer_story(chat_id: int, theme: str):
    voices = story_pairs[chat_id]
    names = [voice_name(voice) for voice in voices]
    history = histories[chat_id]
    name = get_preferred_name(chat_id)
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
            + f" La persona que escucha prefiere que la llamen {name}. "
            f"Estamos contando una historia con cuatro personajes. Vos sos {speaker}. {stage} "
            "Escribí únicamente el diálogo hablado de tu personaje, en primera persona, sin rótulos ni narración "
            "entre comillas. Mencioná el nombre de quien escucha de forma natural. Usá entre 35 y 55 palabras "
            "y mantené continuidad con los diálogos anteriores. No hables como asistente ni como IA."
        )
        messages = [{"role": "system", "content": prompt}]
        messages.extend(history)
        previous = "\n".join(f"{character}: {dialogue}" for character, dialogue in zip(names, replies))
        content = f"Tema de la historia: {theme}"
        if previous:
            content += f"\nDiálogos anteriores:\n{previous}"
        messages.append({"role": "user", "content": content})
        replies.append(clean_turn(await complete(messages), names))
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


async def start_trio(chat_id: int):
    if not get_preferred_name(chat_id):
        await ask_preferred_name(chat_id, "trio")
        return
    trio_selection[chat_id] = []
    await send_text(
        chat_id,
        "Modo trío: elegí la primera de tres voces. Después elegís la segunda y la tercera; responderán por turnos en un solo audio.",
        reply_markup={"inline_keyboard": voice_keyboard(chat_id, "trio1")},
    )


async def start_four_mode(chat_id: int, kind: str):
    if not get_preferred_name(chat_id):
        await ask_preferred_name(chat_id, kind)
        return
    four_selection[chat_id] = {"kind": kind, "voices": []}
    if kind == "quartet":
        text = "Modo cuarteto: elegí la primera de cuatro voces distintas. Responderán por turnos en un solo audio."
    else:
        text = "Modo historia: elegí la primera de cuatro voces distintas. Serán cuatro personajes que continúan una misma escena."
    await send_text(
        chat_id, text,
        reply_markup={"inline_keyboard": voice_keyboard(chat_id, "four")},
    )


async def welcome(chat_id: int):
    name = get_preferred_name(chat_id)
    if not name:
        await ask_preferred_name(chat_id)
        return
    text = (
        f"Hola, {name}. Escribime o mandame una nota de voz y te respondo en texto y audio. "
        "Elegí una voz, un dúo, un trío, un cuarteto o una historia con cuatro personajes. "
        "En los modos grupales, las voces responden por turnos en un mismo audio. "
        "Podés preguntar por clima actual indicando un lugar, o por deportes y resultados indicando deporte y fecha. "
        "Con /individual volvés al modo normal y con /nombre cambiás tu nombre. "
        "Con /solo_texto apagás el audio y con /con_voz lo volvés a activar."
    )
    keyboard = [
        [{"text": "Una voz", "callback_data": "mode:single"}],
        [{"text": "Modo dúo", "callback_data": "mode:duo"}, {"text": "Modo trío", "callback_data": "mode:trio"}],
        [{"text": "Cuarteto", "callback_data": "mode:quartet"}, {"text": "Historia", "callback_data": "mode:story"}],
    ]
    await send_text(chat_id, text, reply_markup={"inline_keyboard": keyboard})
    await send_voice(chat_id, f"Hola, {name}. Ya estoy listo. Elegí hasta cuatro voces o una historia para empezar.")


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
            elif action == "trio":
                await start_trio(chat_id)
            elif action in ("quartet", "story"):
                await start_four_mode(chat_id, action)
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
        if text.startswith("/trio"):
            await start_trio(chat_id)
            return
        if text.startswith("/cuarteto"):
            await start_four_mode(chat_id, "quartet")
            return
        if text.startswith("/historia"):
            await start_four_mode(chat_id, "story")
            return
        if text.startswith("/individual"):
            duo_enabled[chat_id] = False
            trio_enabled[chat_id] = False
            quartet_enabled[chat_id] = False
            story_enabled[chat_id] = False
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
        status, user_text, source = await prepare_live_query(chat_id, user_text)
        if status == "ask":
            await send_text(chat_id, user_text)
            return
        source_text = f"\n\nFuente: {source}" if source else ""
        if story_enabled[chat_id]:
            voices = story_pairs[chat_id]
            replies = await answer_story(chat_id, user_text)
            combined = "\n\n".join(
                f"{voice_name(voice)}: {reply}" for voice, reply in zip(voices, replies)
            )
            await send_text(chat_id, combined + source_text)
            await send_group_voice(chat_id, list(zip(voices, replies)))
            return
        if quartet_enabled[chat_id]:
            voices = quartet_pairs[chat_id]
            replies = await answer_quartet(chat_id, user_text)
            combined = "\n\n".join(
                f"{voice_name(voice)}: {reply}" for voice, reply in zip(voices, replies)
            )
            await send_text(chat_id, combined + source_text)
            await send_group_voice(chat_id, list(zip(voices, replies)))
            return
        if trio_enabled[chat_id]:
            voices = trio_pairs[chat_id]
            replies = await answer_trio(chat_id, user_text)
            combined = "\n\n".join(
                f"{voice_name(voice)}: {reply}" for voice, reply in zip(voices, replies)
            )
            await send_text(chat_id, combined + source_text)
            await send_group_voice(chat_id, list(zip(voices, replies)))
            return
        if duo_enabled[chat_id]:
            voices = duo_pairs[chat_id]
            replies = await answer_duo(chat_id, user_text)
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


async def handle_callback(callback: dict):
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")
    callback_id = callback["id"]
    if data == "mode:single":
        duo_enabled[chat_id] = False
        trio_enabled[chat_id] = False
        quartet_enabled[chat_id] = False
        story_enabled[chat_id] = False
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Modo de una voz")
        await show_voices(chat_id)
        return
    if data == "mode:duo":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Modo dúo")
        await start_duo(chat_id)
        return
    if data == "mode:trio":
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Modo trío")
        await start_trio(chat_id)
        return
    if data in ("mode:quartet", "mode:story"):
        kind = "quartet" if data == "mode:quartet" else "story"
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Cuarteto" if kind == "quartet" else "Historia")
        await start_four_mode(chat_id, kind)
        return
    if data.startswith("four:"):
        voice = data.split(":", 1)[1]
        session = four_selection.get(chat_id)
        if voice not in VOICES or not session:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Empecemos de nuevo.")
            return
        selected = session["voices"]
        if voice in selected:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Elegí cuatro voces distintas.")
            return
        selected.append(voice)
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=f"Voz {len(selected)}: {voice_name(voice)}")
        if len(selected) < 4:
            await send_text(
                chat_id,
                f"Voz {len(selected)}: {voice_name(voice)}. Elegí la siguiente.",
                reply_markup={"inline_keyboard": voice_keyboard(chat_id, "four", exclude=selected)},
            )
            return
        voices = tuple(selected)
        names = [voice_name(item) for item in voices]
        kind = session["kind"]
        four_selection.pop(chat_id, None)
        duo_enabled[chat_id] = False
        trio_enabled[chat_id] = False
        quartet_enabled[chat_id] = kind == "quartet"
        story_enabled[chat_id] = kind == "story"
        selected_voice[chat_id] = voices[0]
        voice_enabled[chat_id] = True
        name = get_preferred_name(chat_id)
        if kind == "quartet":
            quartet_pairs[chat_id] = voices
            samples = [
                f"Hola, {name}. Soy {names[0]} y empiezo el cuarteto.",
                f"{name}, yo soy {names[1]} y sigo después de {names[0]}.",
                f"Soy {names[2]}, {name}. Voy a aportar otra mirada.",
                f"Y yo soy {names[3]}, {name}. Cierro con una recomendación. Mandanos tu pregunta.",
            ]
        else:
            story_pairs[chat_id] = voices
            samples = [
                f"{name}, soy {names[0]}, el primer personaje de nuestra historia.",
                f"Yo soy {names[1]}, {name}, y continuaré lo que empiece {names[0]}.",
                f"Soy {names[2]}, {name}. Mi personaje traerá un giro a la escena.",
                f"Y yo soy {names[3]}, {name}. Mi personaje cerrará la escena. Decinos el tema de la historia.",
            ]
        combined = "\n\n".join(f"{speaker}: {sample}" for speaker, sample in zip(names, samples))
        await send_text(chat_id, combined)
        await send_group_voice(chat_id, list(zip(voices, samples)))
        return
    if data.startswith("trio1:"):
        voice = data.split(":", 1)[1]
        if voice not in VOICES:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Esa voz no está disponible.")
            return
        trio_selection[chat_id] = [voice]
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=f"Primera voz: {voice_name(voice)}")
        await send_text(
            chat_id, f"Primera voz: {voice_name(voice)}. Elegí la segunda.",
            reply_markup={"inline_keyboard": voice_keyboard(chat_id, "trio2", exclude=[voice])},
        )
        return
    if data.startswith("trio2:"):
        voice = data.split(":", 1)[1]
        selection = trio_selection.get(chat_id, [])
        if voice not in VOICES or len(selection) != 1:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Empecemos de nuevo.")
            await start_trio(chat_id)
            return
        selection.append(voice)
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=f"Segunda voz: {voice_name(voice)}")
        await send_text(
            chat_id, f"Segunda voz: {voice_name(voice)}. Ahora elegí la tercera.",
            reply_markup={"inline_keyboard": voice_keyboard(chat_id, "trio3", exclude=selection)},
        )
        return
    if data.startswith("trio3:"):
        voice = data.split(":", 1)[1]
        selection = trio_selection.get(chat_id, [])
        if voice not in VOICES or len(selection) != 2:
            await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Empecemos de nuevo.")
            await start_trio(chat_id)
            return
        voices = tuple(selection + [voice])
        trio_pairs[chat_id] = voices
        trio_enabled[chat_id] = True
        duo_enabled[chat_id] = False
        quartet_enabled[chat_id] = False
        story_enabled[chat_id] = False
        selected_voice[chat_id] = voices[0]
        voice_enabled[chat_id] = True
        names = [voice_name(item) for item in voices]
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=f"Trío: {', '.join(names)}")
        name = get_preferred_name(chat_id)
        samples = [
            f"Hola, {name}. Soy {names[0]} y vamos a conversar entre los tres.",
            f"{name}, yo soy {names[1]}. Voy a sumar otra mirada después de {names[0]}.",
            f"Y yo soy {names[2]}, {name}. Cierro el turno con una idea práctica. Mandanos tu pregunta.",
        ]
        combined = "\n\n".join(f"{speaker}: {sample}" for speaker, sample in zip(names, samples))
        await send_text(chat_id, combined)
        await send_group_voice(chat_id, list(zip(voices, samples)))
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
        trio_enabled[chat_id] = False
        quartet_enabled[chat_id] = False
        story_enabled[chat_id] = False
        selected_voice[chat_id] = first
        voice_enabled[chat_id] = True
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text=f"Dúo: {voice_name(first)} y {voice_name(voice)}")
        name = get_preferred_name(chat_id)
        first_sample = f"Hola, {name}. Soy {voice_name(first)} y vamos a responder juntos, por turnos."
        second_sample = f"{name}, yo soy {voice_name(voice)}. Mandanos un mensaje o un audio para probar el modo dúo."
        await send_text(chat_id, f"{voice_name(first)}: {first_sample}\n\n{voice_name(voice)}: {second_sample}")
        await send_group_voice(chat_id, [(first, first_sample), (voice, second_sample)])
        return
    if not data.startswith("voice:"):
        await telegram("answerCallbackQuery", callback_query_id=callback_id)
        return
    voice = data.split(":", 1)[1]
    if voice not in VOICES:
        await telegram("answerCallbackQuery", callback_query_id=callback_id, text="Esa voz no está disponible.")
        return
    duo_enabled[chat_id] = False
    trio_enabled[chat_id] = False
    quartet_enabled[chat_id] = False
    story_enabled[chat_id] = False
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
