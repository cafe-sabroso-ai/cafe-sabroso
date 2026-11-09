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
            self.assertNotIn("jefe 22", prompt)
            self.assertNotIn("Empezá tu turno", prompt)
            self.assertIn("las pida", prompt)

    def test_group_turn_parser_rejects_missing_voice(self):
        self.assertIsNone(app.parse_group_turns("Tomás: Solo una respuesta.", ["Tomás", "Elena"]))


if __name__ == "__main__":
    unittest.main()
