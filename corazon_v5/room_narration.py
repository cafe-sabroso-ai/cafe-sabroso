"""Room-only natural narration, bounded by text length and returned as MP3.
No new provider, key or charge. The original bot synthesis is unchanged.
"""
import asyncio
import logging
import time
from collections import OrderedDict
import edge_tts

log = logging.getLogger('room-natural-voice')
FALLBACK = ('es-AR-ElenaNeural', 'es-AR-TomasNeural', 'es-UY-ValentinaNeural')
_cache = OrderedDict()
_gate = None
_loop = None
MAX_AUDIO = 6 * 1024 * 1024

def timeout_for(text):
    return min(90, max(25, 20 + len(text) / 40))

def gate():
    global _gate, _loop
    loop = asyncio.get_running_loop()
    if loop is not _loop:
        _loop, _gate = loop, asyncio.Semaphore(2)
    return _gate

async def synthesize_room_mp3(text, voice, convert_local):
    import app
    text = app.speech_text(text)
    retired = getattr(app, 'RETIRED_READER_VOICES', ())
    voice = FALLBACK[0] if voice in retired else voice
    key = (text, voice)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < 1800:
        _cache.move_to_end(key)
        return cached[1]
    candidates = tuple(dict.fromkeys((voice,) + FALLBACK))
    local = set(getattr(app, 'PIPER_VOICES', {})) | set(getattr(app, 'RHVOICE_VOICES', {}))
    async def build(candidate):
        if candidate in local:
            return await convert_local(await app.synthesize_once(text, candidate))
        # Edge already returns MP3. Avoid converting MP3 -> OGG -> MP3 on the
        # small shared instance, especially for full rules and case readings.
        data = bytearray()
        async for chunk in edge_tts.Communicate(text, candidate).stream():
            if chunk['type'] == 'audio':
                data.extend(chunk['data'])
                if len(data) > MAX_AUDIO:
                    raise ValueError('natural audio exceeds room limit')
        if not data:
            raise ValueError('natural service returned no audio')
        return bytes(data)
    async with gate():
        # Another room may have completed the same intro while this queued.
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 1800:
            return cached[1]
        for candidate in candidates:
            start = time.monotonic()
            try:
                data = await asyncio.wait_for(build(candidate), timeout_for(text))
                _cache[key] = (time.monotonic(), data)
                _cache.move_to_end(key)
                while len(_cache) > 48 or sum(len(v[1]) for v in _cache.values()) > 8*1024*1024:
                    _cache.popitem(last=False)
                log.info('Natural room voice ready chars=%d seconds=%.1f', len(text), time.monotonic()-start)
                return data
            except Exception as error:
                log.warning('Natural room voice failed voice=%s reason=%s chars=%d seconds=%.1f', candidate, type(error).__name__, len(text), time.monotonic()-start)
    raise RuntimeError('Natural room narration unavailable; retry required')
