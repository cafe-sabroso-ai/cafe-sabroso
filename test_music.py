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
             patch.object(app, "send_archive_audio", AsyncMock(return_value=False)), \
             patch.object(app, "send_text", capture), \
             patch.object(app, "send_voice", AsyncMock()):
            await app.search_music(123, "Artista")
        self.assertEqual(len(sent), 5)
        for index in range(1, 4):
            keyboard = sent[index][1]["reply_markup"]["inline_keyboard"]
            self.assertEqual(keyboard[0][1]["text"], "Spotify")
            self.assertIn("open.spotify.com/search", keyboard[0][1]["url"])
            self.assertEqual(keyboard[1][0]["text"], "Compartir")
        self.assertIn("CC0", sent[4][0])
        self.assertEqual(sent[4][1]["reply_markup"]["inline_keyboard"][0][0]["url"], download["download_url"])

    async def test_direct_file_sent_for_licensed_download(self):
        download = {
            "title": "Obra abierta", "artist": "Artista", "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "item_url": "https://archive.org/details/open",
            "download_url": "https://archive.org/download/open/song.mp3",
            "file_name": "song.mp3", "format": "MP3", "size": 1024,
        }
        sent = []
        async def capture(chat_id, text, **kwargs):
            sent.append((text, kwargs))
        with patch.object(app, "apple_music_results", AsyncMock(return_value=[])), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[download])), \
             patch.object(app, "send_archive_audio", AsyncMock(return_value=True)) as direct, \
             patch.object(app, "send_text", capture), \
             patch.object(app, "send_voice", AsyncMock()):
            await app.search_music(123, "Artista")
        direct.assert_awaited_once_with(123, download)
        self.assertIn("archivo directo", sent[1][0])
        self.assertIn("CC BY 4.0", sent[1][0])
        keyboard = sent[1][1]["reply_markup"]["inline_keyboard"]
        urls = [button["url"] for row in keyboard for button in row]
        self.assertNotIn(download["download_url"], urls)
        self.assertIn(download["license_url"], urls)
        self.assertIn(download["item_url"], urls)

    async def test_catalog_failure_still_gives_official_search(self):
        sent = []
        async def capture(chat_id, text, **kwargs):
            sent.append((text, kwargs))
        with patch.object(app, "apple_music_results", AsyncMock(side_effect=RuntimeError("down"))), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[])), \
             patch.object(app, "send_text", capture), \
             patch.object(app, "send_voice", AsyncMock()):
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

    async def test_pending_query_stays_armed_for_followups(self):
        """The Música section is sticky: after a search he can name another
        song by voice; 'salir', /menu or a game leaves the section."""
        app.pending_music_query[123] = True
        with patch.object(app, "apple_music_results", AsyncMock(return_value=[])), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[])), \
             patch.object(app, "send_text", AsyncMock()), \
             patch.object(app, "send_voice", AsyncMock()):
            await app.search_music(123, "Artista")
        self.assertIn(123, app.pending_music_query)
        app.pending_music_query.pop(123, None)


class DirectDownloadTests(unittest.IsolatedAsyncioTestCase):
    def download(self, **overrides):
        item = {
            "title": "Obra abierta", "artist": "Artista", "license": "CC0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "item_url": "https://archive.org/details/open",
            "download_url": "https://archive.org/download/open/song.mp3",
            "file_name": "song.mp3", "format": "MP3", "size": 1024,
        }
        item.update(overrides)
        return item

    async def test_known_oversize_track_is_not_downloaded(self):
        item = self.download(size=app.ARCHIVE_AUDIO_LIMIT + 1)
        with patch.object(app, "http", AsyncMock()) as client:
            self.assertFalse(await app.send_archive_audio(123, item))
        client.stream.assert_not_called()

    async def test_mp3_goes_to_send_audio_with_license_caption(self):
        class FakeStream:
            status_code = 200
            headers = {"content-length": "4"}
            def raise_for_status(self):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def aiter_bytes(self, size):
                yield b"mp3!"

        posts = []
        class FakeClient:
            def stream(self, *args, **kwargs):
                return FakeStream()
            async def post(self, url, **kwargs):
                posts.append((url, kwargs))
                return type("Resp", (), {"status_code": 200, "text": ""})()

        item = self.download()
        with patch.object(app, "http", FakeClient()), \
             patch.object(app, "telegram", AsyncMock()):
            self.assertTrue(await app.send_archive_audio(123, item))
        self.assertTrue(posts[0][0].endswith("/sendAudio"))
        data = posts[0][1]["data"]
        self.assertEqual(data["performer"], "Artista")
        self.assertIn("CC0", data["caption"])
        self.assertIn(item["item_url"], data["caption"])
        self.assertEqual(posts[0][1]["files"]["audio"][0], "song.mp3")
        self.assertEqual(posts[0][1]["files"]["audio"][1], b"mp3!")

    async def test_transfer_failure_returns_false(self):
        class FailingClient:
            def stream(self, *args, **kwargs):
                raise RuntimeError("archive down")
        with patch.object(app, "http", FailingClient()), \
             patch.object(app, "telegram", AsyncMock()):
            self.assertFalse(await app.send_archive_audio(123, self.download()))


if __name__ == "__main__":
    unittest.main()


class MusicVoiceStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_found_status_is_spoken(self):
        tracks = [
            {"title": "Tema 1", "artist": "Artista", "album": "", "url": "https://music.apple.com/ar/song/1", "preview": None},
            {"title": "Tema 2", "artist": "Artista", "album": "", "url": "https://music.apple.com/ar/song/2", "preview": None},
        ]
        with patch.object(app, "apple_music_results", AsyncMock(return_value=tracks)), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[])), \
             patch.object(app, "send_text", AsyncMock()), \
             patch.object(app, "send_voice", AsyncMock()) as voice:
            await app.search_music(123, "Artista")
        spoken = voice.await_args[0][1]
        self.assertIn("2 canciones", spoken)
        self.assertIn("Artista", spoken)

    async def test_not_found_status_is_spoken(self):
        with patch.object(app, "apple_music_results", AsyncMock(return_value=[])), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[])), \
             patch.object(app, "send_text", AsyncMock()), \
             patch.object(app, "send_voice", AsyncMock()) as voice:
            await app.search_music(123, "xyz inexistente")
        spoken = voice.await_args[0][1]
        self.assertIn("No encontré nada", spoken)
        self.assertIn("xyz inexistente", spoken)

    async def test_catalog_failure_status_is_spoken(self):
        with patch.object(app, "apple_music_results", AsyncMock(side_effect=RuntimeError("down"))), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[])), \
             patch.object(app, "send_text", AsyncMock()), \
             patch.object(app, "send_voice", AsyncMock()) as voice:
            await app.search_music(123, "Artista")
        self.assertIn("No pude consultar el catálogo", voice.await_args[0][1])

    async def test_empty_query_prompts_by_voice(self):
        with patch.object(app, "send_text", AsyncMock()), \
             patch.object(app, "send_voice", AsyncMock()) as voice:
            await app.search_music(123, "")
        self.assertIn("artista o la canción", voice.await_args[0][1])


class MusicStickyAndRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_rearms_pending_query(self):
        app.pending_music_query.pop(125, None)
        with patch.object(app, "apple_music_results", AsyncMock(return_value=[])), \
             patch.object(app, "licensed_music_downloads", AsyncMock(return_value=[])), \
             patch.object(app, "send_text", AsyncMock()), \
             patch.object(app, "send_voice", AsyncMock()):
            await app.search_music(125, "Los Piojos Como Alí")
        self.assertIn(125, app.pending_music_query)
        app.pending_music_query.pop(125, None)

    async def test_salir_leaves_the_music_section(self):
        app.pending_music_query[126] = True
        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", new=AsyncMock()) as text, \
             patch.object(app, "send_voice", new=AsyncMock()):
            await app.handle_message({"chat": {"id": 126}, "text": "salir"})
        self.assertNotIn(126, app.pending_music_query)
        self.assertIn("saliste de la búsqueda de música", text.await_args[0][1])

    async def test_menu_exits_the_music_section(self):
        app.pending_music_query[127] = True
        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", new=AsyncMock()), \
             patch.object(app, "send_voice", new=AsyncMock()):
            await app.handle_message({"chat": {"id": 127}, "text": "/menu"})
        self.assertNotIn(127, app.pending_music_query)

    async def test_apple_retries_without_country_when_empty(self):
        calls = []

        class FakeResponse:
            def __init__(self, results):
                self._results = results
            def raise_for_status(self):
                pass
            def json(self):
                return {"results": self._results}

        async def fake_get(url, params=None, timeout=None):
            calls.append(params)
            if len(calls) == 1:
                return FakeResponse([])
            return FakeResponse([{
                "kind": "song", "trackName": "Como Alí", "artistName": "Los Piojos",
                "collectionName": "Civilización",
                "trackViewUrl": "https://music.apple.com/ar/album/como-ali/1?i=2",
                "previewUrl": "https://example.com/preview.m4a",
            }])

        with patch.object(app.http, "get", fake_get):
            tracks = await app.apple_music_results("Los Piojos, Como Alí")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("country", calls[1])
        self.assertEqual(tracks[0]["title"], "Como Alí")

    async def test_apple_raises_after_both_attempts_fail(self):
        async def failing_get(url, params=None, timeout=None):
            raise RuntimeError("down")
        with patch.object(app.http, "get", failing_get):
            with self.assertRaises(RuntimeError):
                await app.apple_music_results("algo")
