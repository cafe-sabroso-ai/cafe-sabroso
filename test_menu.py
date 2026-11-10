import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "cafe-sabroso-menu-tests.db"))

import app


class MenuTests(unittest.IsolatedAsyncioTestCase):
    async def test_menu_command_reopens_main_buttons(self):
        sent = []
        async def capture(chat_id, text, **kwargs):
            sent.append((text, kwargs))
        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "send_text", capture), \
             patch.object(app, "send_voice", AsyncMock()):
            await app.handle_message({"chat": {"id": 123}, "text": "/menu"})
        self.assertIn("MENÚ PRINCIPAL", sent[0][0])
        buttons = sent[0][1]["reply_markup"]["inline_keyboard"]
        self.assertEqual(buttons[0][0]["callback_data"], "mode:single")
        self.assertIn("Dúo: 2 voces", buttons[1][0]["text"])

    async def test_individual_immediately_shows_voice_buttons(self):
        sent = []
        async def capture(chat_id, text, **kwargs):
            sent.append((text, kwargs))
        with patch.object(app, "send_text", capture), \
             patch.object(app, "send_voice", AsyncMock()):
            await app.handle_message({"chat": {"id": 123}, "text": "/individual"})
        self.assertEqual(len(sent), 2)
        self.assertIn("ELEGIR UNA VOZ", sent[1][0])
        self.assertEqual(len(sent[1][1]["reply_markup"]["inline_keyboard"]), 49)

    async def test_menu_callback_returns_to_main_buttons(self):
        with patch.object(app, "welcome", AsyncMock()) as welcome, \
             patch.object(app, "telegram", AsyncMock()):
            await app.handle_callback({
                "id": "callback-1",
                "message": {"chat": {"id": 123}},
                "data": "mode:menu",
            })
        welcome.assert_awaited_once_with(123, None)

    async def test_startup_registers_commands_and_default_menu(self):
        calls = []
        async def capture(method, **kwargs):
            calls.append((method, kwargs))
            return True
        with patch.object(app, "telegram", capture), \
             patch.object(app, "PUBLIC_URL", "https://example.com"):
            await app.startup()
        self.assertEqual(calls[0][0], "setMyCommands")
        self.assertEqual(calls[0][1]["commands"], app.BOT_COMMANDS)
        self.assertEqual(calls[1][0], "setChatMenuButton")
        self.assertEqual(calls[1][1]["menu_button"], {"type": "commands"})
        self.assertEqual(calls[2][0], "setWebhook")


class GroupCapTests(unittest.TestCase):
    def test_group_modes_go_up_to_ten_voices(self):
        self.assertEqual(app.GROUP_MODE_SIZES["decet"], 10)
        for kind in ("septet", "octet", "nonet", "decet"):
            self.assertIn(kind, app.GROUP_MODE_LABELS)
            self.assertIn(kind, app.GROUP_MODE_FLAGS)
            self.assertIn(kind, app.DIALOGUE_KINDS)
        commands = {entry["command"] for entry in app.BOT_COMMANDS}
        self.assertTrue({"septeto", "octeto", "noneto", "deceto"} <= commands)


if __name__ == "__main__":
    unittest.main()
