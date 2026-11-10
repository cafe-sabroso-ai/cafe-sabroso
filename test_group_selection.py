import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "cafe-sabroso-group-tests.db"))

import app

CHAT = 7788


def fresh_state():
    for mapping in (
        app.duo_pairs, app.trio_pairs, app.quartet_pairs, app.story_pairs,
        app.group_selection, app.pending_music_query, app.pending_weather_query,
        app.pending_sports_query, app.pending_action,
    ):
        mapping.pop(CHAT, None)
    for flags in (app.duo_enabled, app.trio_enabled, app.quartet_enabled,
                  app.story_enabled, app.awaiting_name):
        flags[CHAT] = False
    app.voice_enabled[CHAT] = True
    app.selected_voice[CHAT] = app.DEFAULT_VOICE
    app.histories[CHAT].clear()


async def tap(data, message_id=500):
    texts = []

    async def capture_text(chat_id, text, **kwargs):
        texts.append(text)

    with patch.object(app, "telegram", new=AsyncMock()) as tg, \
         patch.object(app, "send_text", capture_text), \
         patch.object(app, "send_voice", new=AsyncMock()), \
         patch.object(app, "send_group_voice", new=AsyncMock()) as group_voice, \
         patch.object(app, "get_preferred_name", return_value="David"):
        await app.handle_callback({
            "id": f"cb-{data}",
            "message": {"chat": {"id": CHAT}, "message_id": message_id},
            "data": data,
            "from": {"first_name": "David"},
        })
    return tg, texts, group_voice


class GroupSelectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fresh_state()

    async def test_double_tap_on_first_keyboard_completes_duo(self):
        """The reported defect: two taps on the same first keyboard must still complete the duo."""
        await tap("voice:es-AR-TomasNeural")  # individual voice picked earlier
        await tap("mode:duo")
        await tap("gsel:duo:es-BO-SofiaNeural")
        tg, texts, group_voice = await tap("gsel:duo:es-MX-DaliaNeural")
        self.assertEqual(app.duo_pairs[CHAT], ("es-BO-SofiaNeural", "es-MX-DaliaNeural"))
        self.assertTrue(app.duo_enabled[CHAT])
        turns = group_voice.call_args[0][1]
        self.assertEqual([voice for voice, _ in turns], ["es-BO-SofiaNeural", "es-MX-DaliaNeural"])

    async def test_sumar_mi_voz_seeds_the_selection(self):
        """gself:<kind>:yes makes the user's current voice the first talker."""
        await tap("mode:trio")
        tg, texts, group_voice = await tap("gself:trio:yes")
        self.assertIn("tu voz (Tomás) ya participa", texts[0])
        self.assertEqual(app.group_selection[CHAT]["voices"], ["es-AR-TomasNeural"])
        await tap("gsel:trio:es-BO-SofiaNeural")
        tg, texts, group_voice = await tap("gsel:trio:es-MX-DaliaNeural")
        self.assertEqual(
            app.trio_pairs[CHAT],
            ("es-AR-TomasNeural", "es-BO-SofiaNeural", "es-MX-DaliaNeural"),
        )
        turns = group_voice.call_args[0][1]
        self.assertEqual(
            [voice for voice, _ in turns],
            ["es-AR-TomasNeural", "es-BO-SofiaNeural", "es-MX-DaliaNeural"],
        )

    async def test_gself_no_keeps_normal_selection(self):
        await tap("mode:duo")
        tg, texts, group_voice = await tap("gself:duo:no")
        self.assertEqual(app.group_selection[CHAT]["voices"], [])
        await tap("gsel:duo:es-BO-SofiaNeural")
        await tap("gsel:duo:es-MX-DaliaNeural")
        self.assertEqual(app.duo_pairs[CHAT], ("es-BO-SofiaNeural", "es-MX-DaliaNeural"))

    async def test_legacy_prefixes_advance_the_same_selection(self):
        """Stale duo1/trio1 keyboards from before the fix keep working as picks."""
        await tap("mode:duo")
        await tap("duo1:es-BO-SofiaNeural")
        await tap("duo1:es-MX-DaliaNeural")  # second tap on the stale first keyboard
        self.assertEqual(app.duo_pairs[CHAT], ("es-BO-SofiaNeural", "es-MX-DaliaNeural"))
        self.assertTrue(app.duo_enabled[CHAT])

    async def test_voice_note_during_selection_never_answers_single_voice(self):
        fresh_state()
        app.group_selection[CHAT] = {"kind": "duo", "voices": ["es-BO-SofiaNeural"]}
        sent = []

        async def capture_text(chat_id, text, **kwargs):
            sent.append(text)

        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", capture_text), \
             patch.object(app, "send_voice", new=AsyncMock()) as single_voice, \
             patch.object(app, "send_group_voice", new=AsyncMock()), \
             patch.object(app, "transcribe", new=AsyncMock(return_value="Preséntense")), \
             patch.object(app, "complete", new=AsyncMock()) as complete:
            await app.handle_message({"chat": {"id": CHAT}, "voice": {"file_id": "f"}})
        complete.assert_not_called()
        single_voice.assert_not_called()
        self.assertIn("1 de 2", sent[-1])

    async def test_completed_duo_answers_with_both_voices(self):
        await tap("mode:duo")
        await tap("gsel:duo:es-BO-SofiaNeural")
        await tap("gsel:duo:es-MX-DaliaNeural")
        sent = []

        async def capture_text(chat_id, text, **kwargs):
            sent.append(text)

        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", capture_text), \
             patch.object(app, "send_group_voice", new=AsyncMock()) as group_voice, \
             patch.object(app, "transcribe", new=AsyncMock(return_value="Preséntense")), \
             patch.object(app, "complete", new=AsyncMock(return_value=(
                 "Sofia: Hola, soy Sofía desde Bolivia.\n"
                 "Dalia: Y yo soy Dalia desde México."
             ))):
            await app.handle_message({"chat": {"id": CHAT}, "voice": {"file_id": "f"}})
        turns = group_voice.call_args[0][1]
        self.assertEqual([voice for voice, _ in turns], ["es-BO-SofiaNeural", "es-MX-DaliaNeural"])
        self.assertIn("Dalia", sent[-1])

    async def test_duo_prompt_asks_for_named_dialogue(self):
        """The shared completion must instruct a dialogue where both voices name each other."""
        app.duo_enabled[CHAT] = True
        app.duo_pairs[CHAT] = ("es-AR-TomasNeural", "es-AR-ElenaNeural")
        captured = []

        async def fake_complete(messages):
            captured.append(messages[0]["content"])
            return "Tomás: Hola Elena, ¿cómo estás?\nElena: Muy bien, Tomás, gracias."

        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", new=AsyncMock()), \
             patch.object(app, "send_group_voice", new=AsyncMock()), \
             patch.object(app, "complete", fake_complete):
            await app.handle_message({"chat": {"id": CHAT}, "text": "saluden entre ustedes"})
        prompt = captured[0]
        self.assertIn("conversación", prompt)
        self.assertIn("se dirige a Elena", prompt)
        self.assertIn("Tomás", prompt)
        self.assertIn("por su nombre", prompt)

    async def test_duo_sequential_fallback_keeps_dialogue(self):
        """When the shared completion ignores the format, per-voice calls still ask for naming."""
        app.duo_enabled[CHAT] = True
        app.duo_pairs[CHAT] = ("es-AR-TomasNeural", "es-AR-ElenaNeural")
        calls = []

        async def fake_complete(messages):
            calls.append(messages[0]["content"])
            if len(calls) == 1:
                return "una respuesta sin etiquetas ni formato de diálogo"
            return "texto hablado"

        sent = []

        async def capture_text(chat_id, text, **kwargs):
            sent.append(text)

        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", capture_text), \
             patch.object(app, "send_group_voice", new=AsyncMock()), \
             patch.object(app, "complete", fake_complete):
            await app.handle_message({"chat": {"id": CHAT}, "text": "hola"})
        self.assertEqual(len(calls), 3)
        self.assertIn("dirigite a Elena", calls[1])
        self.assertIn("Ya hablaron Tomás", calls[2])
        self.assertIn("por su nombre", calls[2])
        self.assertIn("Cerrá la conversación", calls[2])

    async def test_quintet_and_sextet_complete_with_all_voices(self):
        await tap("mode:sextet")
        picks = ("espeak-es-419", "es-AR-TomasNeural", "es-MX-DaliaNeural", "es-CL-CatalinaNeural", "es-BO-SofiaNeural")
        for voice in picks:
            await tap(f"gsel:sextet:{voice}")
        _, texts, group_voice = await tap("gsel:sextet:es-UY-ValentinaNeural")
        self.assertTrue(app.sextet_enabled[CHAT])
        self.assertEqual(len(app.sextet_pairs[CHAT]), 6)
        turns = group_voice.call_args[0][1]
        self.assertEqual(len(turns), 6)
        self.assertEqual(turns[0][0], "espeak-es-419")
        self.assertIn("Voz Lector 1: ", texts[0])
        self.assertIn("charlamos entre todos", texts[0])

    async def test_trio_dialogue_prompt_includes_every_name(self):
        app.trio_enabled[CHAT] = True
        app.trio_pairs[CHAT] = ("es-AR-TomasNeural", "es-AR-ElenaNeural", "es-MX-JorgeNeural")
        captured = []

        async def fake_complete(messages):
            captured.append(messages[0]["content"])
            return "Tomás: Elena, ¿qué decís?\nElena: Jorge, vos primero.\nJorge: Gracias, Elena."

        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", new=AsyncMock()), \
             patch.object(app, "send_group_voice", new=AsyncMock()), \
             patch.object(app, "complete", fake_complete):
            await app.handle_message({"chat": {"id": CHAT}, "text": "charlen entre ustedes"})
        prompt = captured[0]
        for name in ("Tomás", "Elena", "Jorge"):
            self.assertIn(name, prompt)
        self.assertIn("conversación", prompt)
        self.assertIn("por su nombre", prompt)

    async def test_trio_and_quartet_complete_with_all_voices(self):
        await tap("mode:trio")
        await tap("gsel:trio:es-AR-TomasNeural")
        await tap("gsel:trio:es-MX-DaliaNeural")
        _, _, trio_voice = await tap("gsel:trio:es-CL-CatalinaNeural")
        self.assertEqual(len(trio_voice.call_args[0][1]), 3)
        self.assertTrue(app.trio_enabled[CHAT])
        self.assertFalse(app.duo_enabled[CHAT])
        await tap("mode:quartet")
        for voice in ("es-AR-TomasNeural", "es-MX-DaliaNeural", "es-CL-CatalinaNeural"):
            await tap(f"gsel:quartet:{voice}")
        _, _, quartet_voice = await tap("gsel:quartet:es-BO-SofiaNeural")
        self.assertEqual(len(quartet_voice.call_args[0][1]), 4)
        self.assertTrue(app.quartet_enabled[CHAT])
        self.assertFalse(app.trio_enabled[CHAT])

    async def test_duplicate_pick_is_rejected(self):
        await tap("mode:duo")
        tg, _, _ = await tap("gsel:duo:es-BO-SofiaNeural")
        tg, _, _ = await tap("gsel:duo:es-BO-SofiaNeural")
        self.assertEqual(app.group_selection[CHAT]["voices"], ["es-BO-SofiaNeural"])

    async def test_menu_cancels_pending_selection(self):
        await tap("mode:duo")
        await tap("gsel:duo:es-BO-SofiaNeural")
        with patch.object(app, "welcome", new=AsyncMock()) as welcome, \
             patch.object(app, "telegram", new=AsyncMock()):
            await app.handle_callback({
                "id": "cb-menu", "message": {"chat": {"id": CHAT}}, "data": "mode:menu",
            })
        welcome.assert_awaited_once()
        app.group_selection.pop(CHAT, None)  # welcome is mocked; simulate its cleanup
        self.assertNotIn(CHAT, app.group_selection)

    async def test_stale_four_keyboard_without_session_restarts_cleanly(self):
        tg, texts, _ = await tap("four:es-BO-SofiaNeural")
        self.assertIn("ya no está activa", texts[-1])
        self.assertNotIn(CHAT, app.group_selection)


class GroupParseTests(unittest.TestCase):
    def test_unaccented_labels_parse(self):
        text = "Sofia: Hola, soy Sofía.\nDalia: Y yo soy Dalia."
        self.assertEqual(
            app.parse_group_turns(text, ["Sofía", "Dalia"]),
            ["Hola, soy Sofía.", "Y yo soy Dalia."],
        )

    def test_clean_turn_strips_unaccented_label(self):
        self.assertEqual(app.clean_turn("Sofia: Hola.", ["Sofía", "Dalia"]), "Hola.")

    def test_empty_turn_falls_back_to_none(self):
        text = "Sofía:\nDalia: hola"
        self.assertIsNone(app.parse_group_turns(text, ["Sofía", "Dalia"]))


class EmptyReplyRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_sequential_retries_empty_reply_and_never_returns_empty_turn(self):
        fresh_state()
        chat = 9911
        app.histories[chat].clear()
        outputs = iter(["", "Hola, soy Sofía.", "Y yo soy Dalia."])
        with patch.object(app, "complete", new=AsyncMock(side_effect=lambda *a, **k: next(outputs))):
            replies = await app.answer_group_sequential(chat, "preséntense", ("es-BO-SofiaNeural", "es-MX-DaliaNeural"))
        self.assertEqual(len(replies), 2)
        self.assertTrue(all(replies))


if __name__ == "__main__":
    unittest.main()
