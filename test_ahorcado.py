import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "cafe-sabroso-ahorcado-tests.db"))

import app


def fresh_game(chat_id=8101, word="MATE", hint="Infusión con bombilla.", **overrides):
    app.ahorcado_games.pop(chat_id, None)
    game = {
        "word": word, "hint": hint, "guessed": set(), "wrong": set(),
        "attempts_left": app.AHORCADO_ATTEMPTS, "board_mid": 11,
    }
    game.update(overrides)
    app.ahorcado_games[chat_id] = game
    return game


class CleanTests(unittest.TestCase):
    def test_accents_dropped_enie_kept(self):
        self.assertEqual(app.ahorcado_clean("canción"), "CANCION")
        self.assertEqual(app.ahorcado_clean("güey"), "GUEY")
        self.assertEqual(app.ahorcado_clean("Ñandú"), "ÑANDU")

    def test_strips_non_letters(self):
        self.assertEqual(app.ahorcado_clean("hola! 123"), "HOLA")


class ParseGuessTests(unittest.TestCase):
    def test_single_letters(self):
        self.assertEqual(app.ahorcado_parse_guess("e"), ("letter", "E"))
        self.assertEqual(app.ahorcado_parse_guess("E"), ("letter", "E"))

    def test_spoken_letter_names(self):
        self.assertEqual(app.ahorcado_parse_guess("la e"), ("letter", "E"))
        self.assertEqual(app.ahorcado_parse_guess("es la e"), ("letter", "E"))
        self.assertEqual(app.ahorcado_parse_guess("ese"), ("letter", "S"))
        self.assertEqual(app.ahorcado_parse_guess("jota"), ("letter", "J"))
        self.assertEqual(app.ahorcado_parse_guess("ele"), ("letter", "L"))
        self.assertEqual(app.ahorcado_parse_guess("eñe"), ("letter", "Ñ"))
        self.assertEqual(app.ahorcado_parse_guess("i griega"), ("letter", "Y"))

    def test_full_word(self):
        self.assertEqual(app.ahorcado_parse_guess("mate"), ("word", "MATE"))
        self.assertEqual(app.ahorcado_parse_guess("¿es mate?"), ("word", "MATE"))

    def test_rejects_noise(self):
        self.assertIsNone(app.ahorcado_parse_guess("   "))


class ParseWordTests(unittest.TestCase):
    def test_valid_format(self):
        parsed = app.parse_ahorcado_word("PALABRA: GUITARRA\nPISTA: Instrumento de cuerdas.")
        self.assertEqual(parsed, ("GUITARRA", "Instrumento de cuerdas."))

    def test_accents_cleaned(self):
        parsed = app.parse_ahorcado_word("PALABRA: canción\nPISTA: Se canta.")
        self.assertEqual(parsed[0], "CANCION")

    def test_rejects_malformed(self):
        self.assertIsNone(app.parse_ahorcado_word("no sé, no tengo palabra"))
        self.assertIsNone(app.parse_ahorcado_word("PALABRA: MATE"))

    def test_rejects_exit_words_and_long_words(self):
        self.assertIsNone(app.parse_ahorcado_word("PALABRA: SALIR\nPISTA: Irse."))
        self.assertIsNone(app.parse_ahorcado_word("PALABRA: ELECTROENCEFALOGRAMA\nPISTA: Muy larga."))


class GuessFlowTests(unittest.IsolatedAsyncioTestCase):
    async def guess(self, raw, chat_id=8101, game=None, **game_kwargs):
        game = game or fresh_game(chat_id, **game_kwargs)
        app.ahorcado_games[chat_id] = game
        edits, voices, texts = [], [], []
        async def capture_text(cid, text, **kwargs):
            texts.append(text)
            return {"message_id": 900}
        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 900})), \
             patch.object(app, "send_text", side_effect=capture_text), \
             patch.object(app, "send_voice", new=AsyncMock(return_value=901, side_effect=None)) as voice:
            await app.ahorcado_guess(chat_id, raw)
        return game, voice, texts

    async def test_hit_reveals_and_keeps_attempts(self):
        game, voice, _ = await self.guess("la a")
        self.assertEqual(game["guessed"], {"A"})
        self.assertEqual(game["attempts_left"], app.AHORCADO_ATTEMPTS)
        spoken = voice.await_args[0][1]
        self.assertIn("aparece una vez", spoken)

    async def test_miss_costs_an_attempt(self):
        game, voice, _ = await self.guess("z")
        self.assertEqual(game["wrong"], {"Z"})
        self.assertEqual(game["attempts_left"], app.AHORCADO_ATTEMPTS - 1)
        self.assertIn("no está", voice.await_args[0][1])

    async def test_repeated_letter_is_free(self):
        game, _, _ = await self.guess("z")
        _, voice, _ = await self.guess("zeta", game=game)
        self.assertEqual(game["attempts_left"], app.AHORCADO_ATTEMPTS - 1)
        self.assertIn("Ya probaste", voice.await_args[0][1])

    async def test_wrong_word_costs_an_attempt(self):
        game, voice, _ = await self.guess("perro")
        self.assertEqual(game["attempts_left"], app.AHORCADO_ATTEMPTS - 1)
        self.assertIn("no es", voice.await_args[0][1])

    async def test_correct_word_wins(self):
        _, voice, texts = await self.guess("mate")
        self.assertNotIn(8101, app.ahorcado_games)
        self.assertTrue(any("GANASTE" in text for text in texts))
        self.assertIn("Ganaste", voice.await_args[0][1])

    async def test_last_letter_wins(self):
        _, voice, texts = await self.guess("e", guessed={"M", "A", "T"})
        self.assertNotIn(8101, app.ahorcado_games)
        self.assertTrue(any("GANASTE" in text for text in texts))
        self.assertIn("eme, a, te, e", voice.await_args[0][1])

    async def test_losing_reveals_the_word(self):
        _, voice, texts = await self.guess("z", attempts_left=1, wrong={"X"})
        self.assertNotIn(8101, app.ahorcado_games)
        self.assertTrue(any("sin intentos" in text for text in texts))
        self.assertIn("La palabra era MATE: eme, a, te, e", voice.await_args[0][1])


class StartEndTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_sets_game_and_one_keyboard(self):
        chat_id = 8201
        app.ahorcado_games.pop(chat_id, None)
        sent = []
        async def capture_text(cid, text, **kwargs):
            sent.append((text, kwargs))
            return {"message_id": 700}
        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "send_text", side_effect=capture_text), \
             patch.object(app, "send_voice", new=AsyncMock(return_value=701)), \
             patch.object(app, "complete", new=AsyncMock(
                 return_value="PALABRA: GUITARRA\nPISTA: Instrumento de seis cuerdas.")):
            await app.ahorcado_start(chat_id)
        game = app.ahorcado_games[chat_id]
        self.assertEqual(game["word"], "GUITARRA")
        self.assertEqual(game["attempts_left"], app.AHORCADO_ATTEMPTS)
        self.assertIn("EMPIEZA EL AHORCADO", sent[0][0])
        keyboard = sent[0][1]["reply_markup"]["inline_keyboard"]
        self.assertEqual(keyboard[0][0]["callback_data"], "ahorcado:quit")
        self.assertEqual(app.trivia_last_keyboard[chat_id], game["board_mid"])
        app.ahorcado_games.pop(chat_id, None)

    async def test_start_falls_back_to_the_bank(self):
        chat_id = 8202
        app.ahorcado_games.pop(chat_id, None)
        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "send_text", new=AsyncMock(return_value={"message_id": 1})), \
             patch.object(app, "send_voice", new=AsyncMock(return_value=2)), \
             patch.object(app, "complete", new=AsyncMock(side_effect=RuntimeError("sin red"))):
            await app.ahorcado_start(chat_id)
        game = app.ahorcado_games[chat_id]
        bank_words = {word for word, _ in app.AHORCADO_FALLBACK_WORDS}
        self.assertIn(game["word"], bank_words)
        app.ahorcado_games.pop(chat_id, None)

    async def test_end_deletes_the_flow_and_lands_a_marker(self):
        chat_id = 8203
        game = fresh_game(chat_id)
        app.trivia_track(game, 50, 51)
        calls = []
        async def capture(method, **kwargs):
            calls.append((method, kwargs))
            return {"message_id": 1}
        texts = []
        with patch.object(app, "telegram", side_effect=capture), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: texts.append(t) or {"message_id": 2}):
            await app.ahorcado_end(chat_id, "Resumen de la partida.")
        deleted = {c[1]["message_id"] for c in calls if c[0] == "deleteMessage"}
        self.assertEqual(deleted, {50, 51})
        self.assertIn("TERMINÓ EL AHORCADO", texts[0])
        self.assertIn("Resumen de la partida.", texts[0])
        self.assertNotIn(chat_id, app.ahorcado_games)


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_letter_routes_to_the_game(self):
        chat_id = 8301
        fresh_game(chat_id)
        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "ahorcado_guess", new=AsyncMock()) as guess:
            await app.handle_message({"chat": {"id": chat_id}, "text": "la e"})
        guess.assert_awaited_once_with(chat_id, "la e")
        app.ahorcado_games.pop(chat_id, None)

    async def test_salir_exits_the_game(self):
        chat_id = 8302
        fresh_game(chat_id)
        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "ahorcado_end", new=AsyncMock()) as end:
            await app.handle_message({"chat": {"id": chat_id}, "text": "salir"})
        end.assert_awaited_once_with(chat_id)
        app.ahorcado_games.pop(chat_id, None)

    async def test_voice_intent_starts_the_game(self):
        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "ahorcado_start", new=AsyncMock()) as start:
            await app.handle_message({"chat": {"id": 8303}, "text": "quiero jugar al ahorcado"})
        start.assert_awaited_once_with(8303)

    async def test_juegos_opens_the_games_menu(self):
        sent = []
        async def capture(cid, text, **kwargs):
            sent.append((text, kwargs))
            return {"message_id": 1}
        with patch.object(app, "send_text", side_effect=capture):
            await app.handle_message({"chat": {"id": 8304}, "text": "/juegos"})
        self.assertIn("JUEGOS", sent[0][0])
        buttons = sent[0][1]["reply_markup"]["inline_keyboard"]
        callbacks = {button["callback_data"] for row in buttons for button in row}
        self.assertEqual(callbacks, {"mode:trivia", "ahorcado:start", "mode:menu"})

    async def test_main_menu_has_a_games_button(self):
        sent = []
        async def capture(cid, text, **kwargs):
            sent.append((text, kwargs))
        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "send_text", capture), \
             patch.object(app, "send_voice", AsyncMock()):
            await app.handle_message({"chat": {"id": 8305}, "text": "/menu"})
        buttons = sent[0][1]["reply_markup"]["inline_keyboard"]
        callbacks = {button["callback_data"] for row in buttons for button in row}
        self.assertIn("mode:games", callbacks)

    async def test_ahorcado_callback_starts_and_quit_ends(self):
        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "ahorcado_start", new=AsyncMock()) as start:
            await app.handle_callback({
                "id": "cb-1", "message": {"chat": {"id": 8306}}, "data": "ahorcado:start",
            })
        start.assert_awaited_once_with(8306)
        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "ahorcado_end", new=AsyncMock()) as end:
            await app.handle_callback({
                "id": "cb-2", "message": {"chat": {"id": 8306}}, "data": "ahorcado:quit",
            })
        end.assert_awaited_once_with(8306)


if __name__ == "__main__":
    unittest.main()
