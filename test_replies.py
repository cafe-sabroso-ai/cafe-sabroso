import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "cafe-sabroso-reply-tests.db"))

import app


class ReplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_answer_does_not_force_name_or_greeting(self):
        with patch.object(app, "get_preferred_name", return_value="jefe 22") as get_name, \
             patch.object(app, "complete", new=AsyncMock(return_value="La capital de Francia es París.")) as complete:
            result = await app.answer(9101, "¿Cuál es la capital de Francia?")

        self.assertEqual(result, "La capital de Francia es París.")
        get_name.assert_not_called()
        prompt = complete.await_args.args[0][0]["content"]
        self.assertIn("no saludes", prompt)
        self.assertNotIn("jefe 22", prompt)

    async def test_duo_voice_note_answers_and_allows_requested_introductions(self):
        chat_id = 9102
        app.duo_enabled[chat_id] = True
        app.trio_enabled[chat_id] = False
        app.quartet_enabled[chat_id] = False
        app.story_enabled[chat_id] = False
        app.duo_pairs[chat_id] = ("es-AR-TomasNeural", "es-AR-ElenaNeural")
        app.histories[chat_id].clear()
        sent_text = []
        sent_voice = []

        async def capture_text(target, text, **kwargs):
            sent_text.append(text)

        async def capture_voice(target, turns):
            sent_voice.extend(turns)

        with patch.object(app, "get_preferred_name", return_value="jefe 22"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "transcribe", new=AsyncMock(return_value="Preséntense y digan quiénes son.")), \
             patch.object(app, "prepare_live_query", new=AsyncMock(return_value=("ok", "Preséntense y digan quiénes son.", None))), \
             patch.object(app, "complete", new=AsyncMock(return_value=(
                 "Tomás: Soy Tomás. Puedo ayudarte con respuestas claras y concretas.\n"
                 "Elena: Soy Elena. Sumo otra mirada para conversar y resolver tus preguntas."
             ))) as complete, \
             patch.object(app, "send_text", capture_text), \
             patch.object(app, "send_group_voice", capture_voice):
            await app.handle_message({"chat": {"id": chat_id}, "voice": {"file_id": "voice-1"}})

        self.assertEqual(complete.await_count, 1)
        self.assertIn("Tomás: Soy Tomás.", sent_text[0])
        self.assertIn("Elena: Soy Elena.", sent_text[0])
        self.assertEqual(len(sent_voice), 2)
        for call in complete.await_args_list:
            prompt = call.args[0][0]["content"]
            self.assertIn("jefe 22", prompt)
            self.assertIn("nombró a una voz", prompt)
            self.assertNotIn("Empezá tu turno", prompt)
            self.assertIn("las pida", prompt)

    def test_group_turn_parser_accepts_bold_labels(self):
        turns = app.parse_group_turns("**Tomás:** Una respuesta.\n**Elena:** Otra respuesta.", ["Tomás", "Elena"])
        self.assertEqual(turns, ["Una respuesta.", "Otra respuesta."])

    def test_group_turn_parser_rejects_missing_voice(self):
        self.assertIsNone(app.parse_group_turns("Tomás: Solo una respuesta.", ["Tomás", "Elena"]))


class EspeakVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_screen_reader_voice_routes_to_espeak_ng(self):
        """The Voz Lector voice synthesizes locally with espeak-ng, not Edge TTS."""
        from pathlib import Path
        calls = []

        class FakeProcess:
            def __init__(self, args):
                self.args = args
                self.returncode = 0

            async def communicate(self, input=None):
                Path(self.args[-1]).write_bytes(b"RIFF")
                return (b"", b"")

        async def fake_exec(*args, **kwargs):
            calls.append(args)
            return FakeProcess(args)

        with patch.object(app.asyncio, "create_subprocess_exec", fake_exec), \
             patch.object(app.edge_tts, "Communicate", side_effect=AssertionError("must not use Edge TTS")):
            audio = await app.synthesize("Hola Elena, ¿cómo estás?", "espeak-es-419")
        self.assertEqual(calls[0][0], "espeak-ng")
        self.assertIn("es-419", calls[0])
        self.assertEqual(calls[1][0], "ffmpeg")
        self.assertEqual(audio, b"RIFF")

    def test_screen_reader_voice_is_listed_first_with_name(self):
        self.assertEqual(app.VOICE_ITEMS[0][0] if hasattr(app, "VOICE_ITEMS") else list(app.VOICES)[0], "espeak-es-419")
        self.assertEqual(app.voice_name("espeak-es-419"), "Voz Lector 1")

    async def test_piper_voice_routes_to_local_piper(self):
        """The Piper voices synthesize locally with piper, not Edge TTS."""
        from pathlib import Path
        calls = []

        class FakeProcess:
            def __init__(self, args):
                self.args = list(args)
                self.returncode = 0

            async def communicate(self, input=None):
                if "-m" in self.args and "piper" in self.args:
                    Path(self.args[self.args.index("--output_file") + 1]).write_bytes(b"RIFF")
                else:
                    Path(self.args[-1]).write_bytes(b"RIFF")
                return (b"", b"")

        async def fake_exec(*args, **kwargs):
            calls.append(args)
            return FakeProcess(args)

        with patch.object(app.asyncio, "create_subprocess_exec", fake_exec), \
             patch.object(app.edge_tts, "Communicate", side_effect=AssertionError("must not use Edge TTS")):
            audio = await app.synthesize("Hola, soy Davefx.", "piper-es-es-davefx")
        self.assertEqual(calls[0][1], "-m")
        self.assertIn("piper", calls[0])
        self.assertIn("es_ES-davefx-medium.onnx", calls[0][calls[0].index("--model") + 1])
        self.assertEqual(calls[1][0], "ffmpeg")
        self.assertEqual(audio, b"RIFF")

    async def test_piper_synth_unloads_cached_whisper_to_free_memory(self):
        """On Render's 512 MB free plan, whisper must be dropped before piper runs."""
        from pathlib import Path

        class FakeProcess:
            def __init__(self, args):
                self.args = list(args)
                self.returncode = 0

            async def communicate(self, input=None):
                Path(self.args[-1]).write_bytes(b"RIFF")
                return (b"", b"")

        async def fake_exec(*args, **kwargs):
            proc = FakeProcess(args)
            if "-m" in args and "piper" in args:
                Path(args[args.index("--output_file") + 1]).write_bytes(b"RIFF")
            return proc

        app.whisper_model = object()
        try:
            with patch.object(app.asyncio, "create_subprocess_exec", fake_exec):
                await app.synthesize("Hola.", "piper-es-mx-ald")
            self.assertIsNone(app.whisper_model)
        finally:
            app.whisper_model = None

    def test_piper_voices_are_listed_after_the_screen_reader_voices(self):
        # Only medium piper models ship: the high ones OOMed on Render's 512 MB.
        piper_keys = ["piper-es-mx-ald", "piper-es-es-davefx", "piper-es-es-sharvard"]
        self.assertEqual(list(app.VOICES)[5:8], piper_keys)
        for key in piper_keys:
            self.assertIn(key, app.PIPER_VOICES)
        self.assertEqual(app.voice_name("piper-es-es-davefx"), "Davefx")
        self.assertNotIn("piper-es-ar-daniela", app.VOICES)
        self.assertNotIn("piper-es-mx-claude", app.VOICES)
        self.assertEqual(list(app.VOICES)[8], "rhvoice-mateo")
        self.assertEqual(app.voice_name("rhvoice-mateo"), "Mateo RH")
        self.assertEqual(len(app.VOICES), 50)

    async def test_failed_voice_falls_back_to_another_engine(self):
        """A crashing voice (piper OOM on Render) must never silence a beat."""
        from pathlib import Path

        class FakeProcess:
            def __init__(self, args):
                self.args = list(args)
                self.returncode = 1 if ("-m" in args and "piper" in args) else 0

            async def communicate(self, input=None):
                if self.returncode == 0:
                    Path(self.args[-1]).write_bytes(b"RIFF")
                    return (b"", b"")
                return (b"", b"piper exploded: out of memory")

        async def fake_edge(text, voice):
            class FakeComm:
                async def save(self, path):
                    Path(path).write_bytes(b"RIFF")
            return FakeComm()

        with patch.object(app.asyncio, "create_subprocess_exec", side_effect=lambda *a, **k: FakeProcess(a)), \
             patch.object(app.edge_tts, "Communicate", side_effect=lambda text, voice: fake_edge(text, voice)):
            audio = await app.synthesize("Te salió geografía.", "piper-es-es-davefx")
        self.assertEqual(audio, b"RIFF")

    async def test_all_engines_failing_raises_loudly(self):
        from pathlib import Path

        class FakeProcess:
            def __init__(self, args):
                self.args = list(args)
                self.returncode = 1

            async def communicate(self, input=None):
                return (b"", b"boom")

        with patch.object(app.asyncio, "create_subprocess_exec", side_effect=lambda *a, **k: FakeProcess(a)), \
             patch.object(app.edge_tts, "Communicate", side_effect=RuntimeError("no network")):
            with self.assertRaises(RuntimeError):
                await app.synthesize("Hola.", "piper-es-es-davefx")

    async def test_rhvoice_voice_routes_to_local_rhvoice(self):
        """The Mateo RHVoice voice synthesizes locally with RHVoice-test."""
        from pathlib import Path
        calls = []

        class FakeProcess:
            def __init__(self, args):
                self.args = list(args)
                self.returncode = 0

            async def communicate(self, input=None):
                if "RHVoice-test" in self.args[0]:
                    Path(self.args[self.args.index("-o") + 1]).write_bytes(b"RIFF")
                else:
                    Path(self.args[-1]).write_bytes(b"RIFF")
                return (b"", b"")

        async def fake_exec(*args, **kwargs):
            calls.append(args)
            return FakeProcess(args)

        with patch.object(app, "RHVOICE_BIN", "/opt/rhvoice/bin/RHVoice-test"), \
             patch.object(app.asyncio, "create_subprocess_exec", fake_exec), \
             patch.object(app.edge_tts, "Communicate", side_effect=AssertionError("must not use Edge TTS")):
            audio = await app.synthesize("Hola, soy Mateo.", "rhvoice-mateo")
        self.assertIn("RHVoice-test", calls[0][0])
        self.assertIn("Mateo", calls[0])

    def test_spain_voices_are_listed(self):
        self.assertEqual(app.VOICES["es-ES-ElviraNeural"], "Elvira - España")
        self.assertEqual(app.VOICES["es-ES-XimenaNeural"], "Ximena - España")
        self.assertEqual(app.VOICES["es-GQ-TeresaNeural"], "Teresa - España (Guinea Ecuatorial)")
        self.assertEqual(app.voice_name("es-GQ-TeresaNeural"), "Teresa")

    def test_all_screen_reader_variants_are_listed_first(self):
        expected = ["espeak-es-419", "espeak-es-419-m1", "espeak-es-419-m3", "espeak-es-419-f1", "espeak-es-419-f2"]
        self.assertEqual(list(app.VOICES)[:5], expected)
        for key in expected:
            self.assertIn(key, app.ESPEAK_VOICES)
            self.assertTrue(app.voice_name(key).startswith("Voz Lector"))

    def test_dialogue_samples_name_each_other(self):
        samples = app.group_samples("trio", ["Tomás", "Elena", "Jorge"], "David")
        self.assertEqual(len(samples), 3)
        self.assertIn("Elena", samples[0])
        self.assertIn("Tomás", samples[1])
        self.assertIn("Jorge", samples[2])


if __name__ == "__main__":
    unittest.main()
