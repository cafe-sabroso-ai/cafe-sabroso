import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "cafe-sabroso-tests.db"))

import app


class MusicQueryTests(unittest.TestCase):
    def test_natural_artist_and_song_requests(self):
        cases = {
            "buscá música de Mercedes Sosa": "Mercedes Sosa",
            "Buscar canción Alfonsina y el mar": "Alfonsina y el mar",
            "quiero escuchar Mercedes Sosa": "Mercedes Sosa",
            "poné el tema Alfonsina y el mar": "Alfonsina y el mar",
            "buscá Mercedes Sosa en Spotify": "Mercedes Sosa",
            "buscame varias canciones de Mercedes Sosa": "Mercedes Sosa",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(app.music_query_from_text(text), expected)

    def test_unrelated_chat_is_not_music(self):
        self.assertIsNone(app.music_query_from_text("contame una historia sobre música"))
        self.assertIsNone(app.music_query_from_text("¿qué canción escribió Mercedes Sosa?"))
        self.assertIsNone(app.music_query_from_text("quiero escuchar una historia sobre una caja misteriosa"))

    def test_empty_music_request_asks_for_query(self):
        self.assertEqual(app.music_query_from_text("buscá música"), "")


class LicenseTests(unittest.TestCase):
    def test_explicit_licenses(self):
        self.assertEqual(app.archive_license("http://creativecommons.org/publicdomain/zero/1.0/"), "CC0")
        self.assertEqual(app.archive_license("https://creativecommons.org/licenses/by-nc-sa/4.0/"), "CC BY-NC-SA 4.0")
        self.assertEqual(app.archive_license("https://creativecommons.org/publicdomain/mark/1.0/"), "Dominio público")

    def test_missing_or_unknown_license_is_not_downloadable(self):
        self.assertIsNone(app.archive_license(""))
        self.assertIsNone(app.archive_license("https://example.com/free-download"))
        self.assertIsNone(app.archive_license("https://creativecommons.org/licenses/"))

    def test_official_search_urls_escape_query(self):
        spotify = app.spotify_music_url("Mercedes Sosa & Alfonsina")
        archive = app.archive_music_url("Mercedes Sosa & Alfonsina")
        self.assertIn("Mercedes%20Sosa%20%26%20Alfonsina", spotify)
        self.assertIn("Mercedes+Sosa+%26+Alfonsina", archive)


class MusicFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_several_choices_and_licensed_download(self):
        tracks = [
            {"title": f"Tema {n}", "artist": "Artista", "album": "Álbum", "url": f"https://music.apple.com/ar/song/{n}", "preview": None}
            for n in range(3)
        ]
        download = {
            "title": "Obra abierta", "artist": "Artista", "license": "CC0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "item_url": "https://archive.org/details/open", "download_url": "https://archive.org/download/open/song.mp3",
        }
        sent = []
        async def capture(chat_id, text, **kwargs):
            sent.append((text, kwargs))
        with patch.object(app, "apple_music_results", AsyncMock(return_value=tracks)), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[download])), \
             patch.object(app, "send_text", capture):
            await app.search_music(123, "Artista")
        self.assertEqual(len(sent), 5)
        for index in range(1, 4):
            keyboard = sent[index][1]["reply_markup"]["inline_keyboard"]
            self.assertEqual(keyboard[0][1]["text"], "Spotify")
            self.assertIn("open.spotify.com/search", keyboard[0][1]["url"])
            self.assertEqual(keyboard[1][0]["text"], "Compartir")
        self.assertIn("CC0", sent[4][0])
        self.assertEqual(sent[4][1]["reply_markup"]["inline_keyboard"][0][0]["url"], download["download_url"])

    async def test_catalog_failure_still_gives_official_search(self):
        sent = []
        async def capture(chat_id, text, **kwargs):
            sent.append((text, kwargs))
        with patch.object(app, "apple_music_results", AsyncMock(side_effect=RuntimeError("down"))), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[])), \
             patch.object(app, "send_text", capture):
            await app.search_music(123, "Artista")
        self.assertIn("No pude consultar", sent[0][0])
        self.assertEqual(sent[0][1]["reply_markup"]["inline_keyboard"][0][0]["text"], "Buscar en Spotify")

    async def test_natural_message_preserves_selected_mode(self):
        app.duo_enabled[321] = True
        app.duo_pairs[321] = ("es-AR-TomasNeural", "es-AR-ElenaNeural")
        music = AsyncMock()
        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "telegram", AsyncMock()), \
             patch.object(app, "search_music", music):
            await app.handle_message({"chat": {"id": 321}, "text": "buscá música de Mercedes Sosa"})
        music.assert_awaited_once_with(321, "Mercedes Sosa")
        self.assertTrue(app.duo_enabled[321])
        self.assertEqual(app.duo_pairs[321], ("es-AR-TomasNeural", "es-AR-ElenaNeural"))

    async def test_pending_query_is_used_once(self):
        app.pending_music_query[123] = True
        with patch.object(app, "apple_music_results", AsyncMock(return_value=[])), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[])), \
             patch.object(app, "send_text", AsyncMock()):
            await app.search_music(123, "Artista")
        self.assertNotIn(123, app.pending_music_query)


if __name__ == "__main__":
    unittest.main()
