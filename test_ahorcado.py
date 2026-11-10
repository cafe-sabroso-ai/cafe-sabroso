import asyncio
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
        "attempts_left": app.ahorcado_attempts_for(word), "board_mid": 11,
        "level": 1, "lives": app.AHORCADO_MAX_LIVES, "used": {word},
        "lock": asyncio.Lock(), "round": 1, "timer": None,
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


class BankTests(unittest.TestCase):
    def test_every_word_is_playable(self):
        speakable = set(app.AHORCADO_SPEAK)
        seen = set()
        for word, hint in app.AHORCADO_BANK:
            self.assertEqual(app.ahorcado_clean(word), word)
            self.assertTrue(4 <= len(word) <= 10)
            self.assertTrue(set(word) <= speakable)
            self.assertTrue(hint.strip())
            self.assertNotIn(word.lower(), app.AHORCADO_EXIT_WORDS)
            self.assertNotIn(word, seen)
            seen.add(word)

    def test_every_level_band_has_words(self):
        for level in (1, 2, 3, 4, 5, 9):
            lo, hi = app.ahorcado_band(level)
            words = [w for w, _ in app.AHORCADO_BANK if lo <= len(w) <= hi]
            self.assertGreaterEqual(len(words), 5, f"nivel {level}")

    def test_bands_rise_with_the_level(self):
        self.assertEqual(app.ahorcado_band(1), (4, 5))
        self.assertEqual(app.ahorcado_band(2), (6, 6))
        self.assertEqual(app.ahorcado_band(3), (7, 7))
        self.assertEqual(app.ahorcado_band(4), (8, 8))
        self.assertEqual(app.ahorcado_band(5), (9, 10))
        self.assertEqual(app.ahorcado_band(12), (9, 10))

    def test_attempts_depend_on_length(self):
        self.assertEqual(app.ahorcado_attempts_for("GUITARRA"), 4)  # 8 letras
        self.assertEqual(app.ahorcado_attempts_for("FACTURA"), 4)   # 7 letras
        self.assertEqual(app.ahorcado_attempts_for("HELADO"), 3)    # 6 letras
        self.assertEqual(app.ahorcado_attempts_for("MATE"), 3)      # 4 letras

    def test_pick_word_respects_the_level_and_avoids_repeats(self):
        game = {"level": 3, "used": set()}
        word, hint = app.ahorcado_pick_word(game)
        self.assertEqual(len(word), 7)
        self.assertIn(word, game["used"])
        other, _ = app.ahorcado_pick_word(game)
        self.assertNotEqual(other, word)


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


class GuessFlowTests(unittest.IsolatedAsyncioTestCase):
    async def guess(self, raw, chat_id=8101, game=None, **game_kwargs):
        game = game or fresh_game(chat_id, **game_kwargs)
        app.ahorcado_games[chat_id] = game
        texts = []

        async def capture_text(cid, text, **kwargs):
            texts.append(text)
            return {"message_id": 900}

        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 900})), \
             patch.object(app, "send_text", side_effect=capture_text), \
             patch.object(app, "send_voice", new=AsyncMock(return_value=901)) as voice:
            await app.ahorcado_guess(chat_id, raw)
        return game, voice, texts

    def spoken(self, voice, index=0):
        args = voice.await_args_list[index]
        return args[0][1], args[1].get("voice")

    async def test_hit_reveals_and_keeps_attempts(self):
        game, voice, _ = await self.guess("la a")
        self.assertEqual(game["guessed"], {"A"})
        self.assertEqual(game["attempts_left"], app.ahorcado_attempts_for("MATE"))
        text, voice_name = self.spoken(voice)
        self.assertIn("aparece una vez", text)
        self.assertEqual(voice_name, app.AHORCADO_GAME_VOICE)

    async def test_miss_costs_an_attempt(self):
        game, voice, _ = await self.guess("z")
        self.assertEqual(game["wrong"], {"Z"})
        self.assertEqual(game["attempts_left"], app.ahorcado_attempts_for("MATE") - 1)
        self.assertIn("no está", self.spoken(voice)[0])

    async def test_repeated_letter_is_free(self):
        game, _, _ = await self.guess("z")
        _, voice, _ = await self.guess("zeta", game=game)
        self.assertEqual(game["attempts_left"], app.ahorcado_attempts_for("MATE") - 1)
        self.assertIn("Ya probaste", self.spoken(voice)[0])

    async def test_wrong_word_costs_an_attempt(self):
        game, voice, _ = await self.guess("perro")
        self.assertEqual(game["attempts_left"], app.ahorcado_attempts_for("MATE") - 1)
        self.assertIn("no es", self.spoken(voice)[0])

    async def test_correct_word_levels_up_and_continues(self):
        game, voice, _ = await self.guess("mate")
        self.assertIn(8101, app.ahorcado_games)  # la partida sigue
        self.assertEqual(game["level"], 2)
        text, voice_name = self.spoken(voice)
        self.assertIn("Acertaste", text)
        self.assertIn("Pasaste al nivel 2", text)
        self.assertEqual(voice_name, app.AHORCADO_LEVEL_VOICE)
        # y ya hay una palabra nueva del nivel 2 (6 letras)
        self.assertEqual(len(game["word"]), 6)
        app.ahorcado_cancel_timer(game)
        app.ahorcado_games.pop(8101, None)

    async def test_last_letter_wins_and_levels_up(self):
        game, voice, _ = await self.guess("e", guessed={"M", "A", "T"})
        self.assertEqual(game["level"], 2)
        self.assertIn("eme, a, te, e", self.spoken(voice)[0])
        app.ahorcado_cancel_timer(game)
        app.ahorcado_games.pop(8101, None)

    async def test_win_gives_back_one_life_announced(self):
        game, voice, _ = await self.guess("mate", lives=2)
        self.assertEqual(game["lives"], 3)
        self.assertIn("Ganaste una vida", self.spoken(voice)[0])
        app.ahorcado_cancel_timer(game)
        app.ahorcado_games.pop(8101, None)

    async def test_win_with_full_lives_gives_no_extra(self):
        game, voice, _ = await self.guess("mate")
        self.assertEqual(game["lives"], 3)
        self.assertIn("Seguís con 3 vidas", self.spoken(voice)[0])
        app.ahorcado_cancel_timer(game)
        app.ahorcado_games.pop(8101, None)

    async def test_losing_a_word_costs_a_life_and_continues(self):
        game, voice, _ = await self.guess("z", attempts_left=1, wrong={"X"})
        self.assertIn(8101, app.ahorcado_games)
        self.assertEqual(game["lives"], 2)
        text, voice_name = self.spoken(voice)
        self.assertIn("sin intentos", text)
        self.assertIn("La palabra era MATE: eme, a, te, e", text)
        self.assertIn("te quedan dos vidas", text)
        self.assertEqual(voice_name, app.AHORCADO_LEVEL_VOICE)
        app.ahorcado_cancel_timer(game)
        app.ahorcado_games.pop(8101, None)

    async def test_losing_all_lives_sends_you_back_to_level_1(self):
        game, voice, _ = await self.guess(
            "z", attempts_left=1, wrong={"X"}, lives=1, level=4,
        )
        self.assertEqual(game["level"], 1)
        self.assertEqual(game["lives"], 3)
        text, _ = self.spoken(voice)
        self.assertIn("volvés al nivel 1", text)
        self.assertIn("vidas nuevas", text)
        app.ahorcado_cancel_timer(game)
        app.ahorcado_games.pop(8101, None)


class ClockTests(unittest.IsolatedAsyncioTestCase):
    async def test_warnings_then_timeout_costs_a_life(self):
        chat_id = 8401
        game = fresh_game(chat_id)
        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 1})), \
             patch.object(app, "ahorcado_new_word", new=AsyncMock()) as new_word, \
             patch("asyncio.sleep", new=AsyncMock()), \
             patch.object(app, "send_voice", new=AsyncMock(return_value=2)) as voice:
            await app.ahorcado_clock(chat_id, game, game["round"])
        calls = voice.await_args_list
        avisos = [c for c in calls if c[1].get("voice") == app.AHORCADO_CLOCK_VOICE]
        self.assertEqual(len(avisos), 2)
        self.assertIn("5 minutos", avisos[0][0][1])
        self.assertIn("Último minuto", avisos[1][0][1])
        # timeout: perdió la palabra y una vida, anunciado por la voz de niveles
        self.assertEqual(game["lives"], 2)
        nivel = [c for c in calls if c[1].get("voice") == app.AHORCADO_LEVEL_VOICE]
        self.assertIn("Se acabaron los diez minutos", nivel[0][0][1])
        new_word.assert_awaited_once()
        app.ahorcado_games.pop(chat_id, None)

    async def test_clock_stops_when_the_round_moved_on(self):
        chat_id = 8402
        game = fresh_game(chat_id)
        with patch.object(app, "send_voice", new=AsyncMock()) as voice, \
             patch("asyncio.sleep", new=AsyncMock()):
            await app.ahorcado_clock(chat_id, game, game["round"] + 99)
        voice.assert_not_awaited()
        self.assertEqual(game["lives"], 3)
        app.ahorcado_games.pop(chat_id, None)

    async def test_winning_cancels_the_timer(self):
        chat_id = 8403
        game = fresh_game(chat_id)

        async def never_ending(*args, **kwargs):
            await asyncio.sleep(9999)

        old_timer = asyncio.create_task(never_ending())
        game["timer"] = old_timer
        texts = []

        async def capture_text(cid, text, **kwargs):
            texts.append(text)
            return {"message_id": 900}

        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 900})), \
             patch.object(app, "send_text", side_effect=capture_text), \
             patch.object(app, "send_voice", new=AsyncMock(return_value=901)):
            await app.ahorcado_guess(chat_id, "mate")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertTrue(old_timer.cancelled() or old_timer.done())
        app.ahorcado_cancel_timer(game)
        app.ahorcado_games.pop(chat_id, None)


class StartEndTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_sets_game_voice_first_and_one_keyboard(self):
        chat_id = 8201
        app.ahorcado_games.pop(chat_id, None)
        order = []

        async def capture_text(cid, text, **kwargs):
            order.append(("text", text))
            return {"message_id": 700}

        async def capture_voice(cid, text, **kwargs):
            order.append(("voice", text))
            return 701

        with patch.object(app, "get_preferred_name", return_value="Rocky"), \
             patch.object(app, "send_text", side_effect=capture_text), \
             patch.object(app, "send_voice", side_effect=capture_voice), \
             patch.object(app, "complete", new=AsyncMock(side_effect=AssertionError("no debe llamar al modelo"))):
            await app.ahorcado_start(chat_id)
        game = app.ahorcado_games[chat_id]
        self.assertEqual(game["level"], 1)
        self.assertEqual(game["lives"], 3)
        self.assertTrue(4 <= len(game["word"]) <= 5)
        self.assertEqual(game["attempts_left"], 3)
        # la primera nota de voz llega ANTES del tablero y lleva la pista
        self.assertEqual(order[0][0], "voice")
        self.assertIn("Pista:", order[0][1])
        self.assertIn("empieza el ahorcado", order[0][1])
        self.assertIn("10 minutos", order[0][1].replace("diez minutos", "10 minutos"))
        self.assertIn("EMPIEZA EL AHORCADO", order[1][1])
        self.assertIn("NIVEL 1", order[1][1])
        self.assertIn("❤️❤️❤️", order[1][1])
        self.assertEqual(app.trivia_last_keyboard[chat_id], game["board_mid"])
        self.assertIsNotNone(game["timer"])
        app.ahorcado_cancel_timer(game)
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
        self.assertIn("Llegaste al nivel 1", texts[0])
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
