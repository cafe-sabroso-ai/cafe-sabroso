import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test-wa-token")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123456")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "verify-me")
os.environ.setdefault("WHATSAPP_APP_SECRET", "secret")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "cafe-sabroso-wa-tests.db"))

import app as cafe
import whatsapp_app as wa

KEY = "5491100000000"


def message(text, message_id="wamid-1"):
    return {"id": message_id, "from": KEY, "type": "text", "text": {"body": text}}


def fresh_state():
    for mapping in (
        cafe.duo_pairs, cafe.trio_pairs, cafe.quartet_pairs, cafe.story_pairs,
        cafe.pending_music_query, cafe.pending_weather_query, cafe.pending_sports_query,
        cafe.pending_action, wa.group_selection,
    ):
        mapping.pop(KEY, None)
    for flags in (cafe.duo_enabled, cafe.trio_enabled, cafe.quartet_enabled,
                  cafe.story_enabled, cafe.awaiting_name):
        flags[KEY] = False
    cafe.voice_enabled[KEY] = True
    cafe.selected_voice[KEY] = cafe.DEFAULT_VOICE
    cafe.histories[KEY].clear()


async def send(text, message_id="wamid-1"):
    """Run one inbound WhatsApp text through the handler and capture the output."""
    texts = []

    async def capture_text(user, body, **kwargs):
        texts.append(body)

    with patch.object(wa, "send_text", capture_text), \
         patch.object(wa, "send_voice", new=AsyncMock()) as voice, \
         patch.object(wa, "send_group_voice", new=AsyncMock()) as group_voice, \
         patch.object(wa, "mark_read", new=AsyncMock()), \
         patch.object(wa, "get_preferred_name", return_value="David"):
        await wa.handle_message(message(text, message_id), {})
    return texts, voice, group_voice


class CommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fresh_state()

    async def test_voices_lists_all_50_numbered(self):
        texts, _, _ = await send("/voces")
        listing = "\n".join(texts)
        self.assertIn("1. Voz Lector 1 - estilo NVDA", listing)
        self.assertIn("10. Tomás - argentino", listing)
        self.assertIn("47. Lorena - El Salvador", listing)
        self.assertIn("/voz", listing)

    async def test_individual_voice_pick(self):
        texts, voice, _ = await send("/voz 11")
        self.assertEqual(cafe.selected_voice[KEY], "es-AR-ElenaNeural")
        self.assertIn("Elegiste Elena - argentina", texts[0])
        voice.assert_awaited_once()

    async def test_espeak_voice_pick(self):
        texts, voice, _ = await send("/voz 1")
        self.assertEqual(cafe.selected_voice[KEY], "espeak-es-419")
        self.assertIn("Elegiste Voz Lector 1 - estilo NVDA", texts[0])
        voice.assert_awaited_once()

    async def test_invalid_voice_number(self):
        texts, _, _ = await send("/voz 99")
        self.assertIn("1 al 50", texts[0])

    async def test_menu_shows_commands(self):
        texts, _, _ = await send("/menu")
        menu = texts[0]
        for command in ("/duo", "/trio", "/cuarteto", "/historia", "/musica", "/nombre"):
            self.assertIn(command, menu)

    async def test_solo_texto_disables_voice(self):
        await send("/solo_texto")
        self.assertFalse(cafe.voice_enabled[KEY])
        texts, voice, _ = await send("/con_voz")
        self.assertTrue(cafe.voice_enabled[KEY])


class GroupSelectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fresh_state()

    async def test_duo_flow_with_numbered_picks(self):
        texts, _, _ = await send("/duo")
        self.assertIn("SUMAR o NO", texts[0])
        texts, _, _ = await send("no")
        self.assertIn("elegís todas las voces", texts[0])
        texts, _, _ = await send("/voz 10")
        self.assertIn("voz 1: Tomás", texts[0])
        self.assertIn("2 de 2", texts[0])
        texts, voice, group_voice = await send("/voz 15")
        self.assertEqual(cafe.duo_pairs[KEY], ("es-AR-TomasNeural", "es-CO-SalomeNeural"))
        self.assertTrue(cafe.duo_enabled[KEY])
        combined = texts[0]
        self.assertIn("Tomás:", combined)
        self.assertIn("Salome:", combined)
        turns = group_voice.call_args[0][1]
        self.assertEqual([v for v, _ in turns], ["es-AR-TomasNeural", "es-CO-SalomeNeural"])

    async def test_sumar_mi_voz_participates(self):
        texts, _, _ = await send("/duo")
        self.assertIn("SUMAR o NO", texts[0])
        texts, _, _ = await send("sumar")
        self.assertIn("ya participa (1 de 2)", texts[0])
        texts, _, group_voice = await send("/voz 15")
        self.assertEqual(cafe.duo_pairs[KEY], ("es-AR-TomasNeural", "es-CO-SalomeNeural"))
        turns = group_voice.call_args[0][1]
        self.assertEqual([v for v, _ in turns], ["es-AR-TomasNeural", "es-CO-SalomeNeural"])

    async def test_duplicate_pick_is_rejected(self):
        await send("/trio")
        await send("no")
        await send("/voz 2")
        texts, _, _ = await send("/voz 2")
        self.assertIn("voces distintas", texts[0])
        self.assertEqual(len(wa.group_selection[KEY]["voices"]), 1)

    async def test_story_flow_needs_four_picks(self):
        await send("/historia")
        await send("no")
        for index in (2, 3, 4):
            await send(f"/voz {index}")
        self.assertFalse(cafe.story_enabled[KEY])
        await send("/voz 5")
        self.assertTrue(cafe.story_enabled[KEY])
        self.assertEqual(len(cafe.story_pairs[KEY]), 4)

    async def test_sextet_flow_needs_six_picks(self):
        await send("/sexteto")
        await send("no")
        for index in (2, 3, 4, 5, 6):
            await send(f"/voz {index}")
        self.assertFalse(cafe.sextet_enabled[KEY])
        texts, _, group_voice = await send("/voz 7")
        self.assertTrue(cafe.sextet_enabled[KEY])
        self.assertEqual(len(cafe.sextet_pairs[KEY]), 6)
        turns = group_voice.call_args[0][1]
        self.assertEqual(len(turns), 6)
        self.assertIn("charlamos entre todos", texts[0])

    async def test_menu_cancels_pending_selection(self):
        await send("/duo")
        await send("/menu")
        self.assertNotIn(KEY, wa.group_selection)

    async def test_plain_text_during_selection_reminds(self):
        await send("/duo")
        texts, _, _ = await send("hola")
        self.assertIn("Escribí SUMAR", texts[0])
        await send("no")
        texts, _, _ = await send("hola")
        self.assertIn("Estás eligiendo las voces del modo dúo", texts[0])

    async def test_individual_clears_group_modes(self):
        await send("/duo")
        await send("no")
        await send("/voz 2")
        await send("/voz 7")
        self.assertTrue(cafe.duo_enabled[KEY])
        texts, _, _ = await send("/individual")
        self.assertFalse(cafe.duo_enabled[KEY])
        self.assertIn("Modo individual activado", texts[0])


class GroupAnswerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fresh_state()

    async def test_duo_answer_uses_both_voices_and_joined_audio(self):
        cafe.duo_enabled[KEY] = True
        cafe.duo_pairs[KEY] = ("es-AR-TomasNeural", "es-AR-ElenaNeural")
        replies = []

        async def fake_complete(messages):
            return "Tomás: primera respuesta\nElena: segunda respuesta"

        texts = []

        async def capture_text(user, body, **kwargs):
            texts.append(body)

        with patch.object(cafe, "complete", fake_complete), \
             patch.object(wa, "send_text", capture_text), \
             patch.object(wa, "send_voice", new=AsyncMock()), \
             patch.object(wa, "send_group_voice", new=AsyncMock()) as group_voice, \
             patch.object(wa, "mark_read", new=AsyncMock()):
            await wa.handle_message(message("¿qué me recomendás para merendar?"), {})
        combined = texts[0]
        self.assertIn("Tomás: primera respuesta", combined)
        self.assertIn("Elena: segunda respuesta", combined)
        turns = group_voice.call_args[0][1]
        self.assertEqual([v for v, _ in turns], ["es-AR-TomasNeural", "es-AR-ElenaNeural"])
        self.assertEqual(replies, [])

    async def test_single_answer_path(self):
        async def fake_complete(messages):
            return "una respuesta individual"

        texts = []

        async def capture_text(user, body, **kwargs):
            texts.append(body)

        with patch.object(cafe, "complete", fake_complete), \
             patch.object(wa, "send_text", capture_text), \
             patch.object(wa, "send_voice", new=AsyncMock()) as voice, \
             patch.object(wa, "mark_read", new=AsyncMock()):
            await wa.handle_message(message("contame algo"), {})
        self.assertEqual(texts[0], "una respuesta individual")
        voice.assert_awaited_once()


class MusicTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fresh_state()

    async def test_musica_without_query_asks(self):
        texts, _, _ = await send("/musica")
        self.assertIn("Decime el artista", texts[0])
        self.assertIn(KEY, cafe.pending_music_query)

    async def test_music_query_from_text_reuses_telegram_detection(self):
        with patch.object(wa, "search_music", new=AsyncMock()) as search, \
             patch.object(wa, "mark_read", new=AsyncMock()):
            await wa.handle_message(message("buscá la canción Alfonsina y el mar"), {})
        search.assert_awaited_once()
        self.assertIn("Alfonsina", search.call_args[0][2])

    async def test_music_results_render_links(self):
        track = {
            "title": "Alfonsina y el mar", "artist": "Mercedes Sosa",
            "album": "", "url": "https://music.apple.com/ar/song/1", "preview": None,
        }
        texts = []

        async def capture_text(user, body, **kwargs):
            texts.append(body)

        with patch.object(cafe, "apple_music_results", new=AsyncMock(return_value=[track])), \
             patch.object(cafe, "licensed_music_downloads", new=AsyncMock(return_value=[])), \
             patch.object(wa, "send_text", capture_text):
            await wa.search_music({"wa_id": KEY}, KEY, "alfonsina")
        body = "\n".join(texts)
        self.assertIn("🎵 Alfonsina y el mar", body)
        self.assertIn("https://music.apple.com/ar/song/1", body)
        self.assertIn("open.spotify.com/search/", body)


class WebhookTests(unittest.TestCase):
    def test_verify_accepts_matching_token(self):
        from fastapi.testclient import TestClient

        client = TestClient(wa.app)
        response = client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "abc123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "abc123")

    def test_verify_rejects_wrong_token(self):
        from fastapi.testclient import TestClient

        client = TestClient(wa.app)
        response = client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "abc123"},
        )
        self.assertEqual(response.status_code, 403)

    def test_mounted_router_reachable_under_app(self):
        """The merged service exposes the WhatsApp webhook at /whatsapp/webhook."""
        self.assertTrue(os.getenv("WHATSAPP_ACCESS_TOKEN"))
        routes = {getattr(route, "path", "") for route in cafe.app.routes}
        # app.py mounts the router only when WHATSAPP_ACCESS_TOKEN is set at
        # import time; the standalone app always serves the same router.
        wa_paths = {getattr(route, "path", "") for route in wa.app.routes}
        self.assertIn("/webhook", wa_paths)


if __name__ == "__main__":
    unittest.main()
