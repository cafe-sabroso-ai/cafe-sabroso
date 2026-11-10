import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "cafe-sabroso-trivia-tests.db"))

import app

QUESTION_TEXT = (
    "PREGUNTA: ¿Qué país ganó el Mundial 2022?\n"
    "OPCION 1: Brasil\n"
    "OPCION 2: Argentina\n"
    "OPCION 3: Francia\n"
    "OPCION 4: Alemania\n"
    "CORRECTA: 2"
)


def fresh_game(chat_id=7101, countries=False):
    app.trivia_games.pop(chat_id, None)
    app.trivia_lineups.pop(chat_id, None)
    app.trivia_games[chat_id] = {
        "phase": "ready", "countries": countries, "lives": 3,
        "streak": 0, "level": 1,
        "score": {}, "won": [],
        "country": None, "country_won": [], "countries_done": [],
        "sprint": None, "timer_gen": 0, "deadline": None,
        "asked": app.deque(maxlen=80), "current": None,
    }
    return app.trivia_games[chat_id]


def current_question(game):
    game["phase"] = "question"
    game["current"] = {
        "category": "fútbol mundial", "country": None,
        "question": "¿Qué país ganó el Mundial 2022?",
        "options": ["Brasil", "Argentina", "Francia", "Alemania"],
        "correct": 1,
        "voices": ("es-AR-TomasNeural", "es-MX-DaliaNeural", "es-CU-ManuelNeural"),
        "message_id": 555,
    }


class ParseTests(unittest.TestCase):
    def test_parse_exact_format(self):
        parsed = app.parse_trivia_question(QUESTION_TEXT)
        self.assertEqual(parsed["question"], "¿Qué país ganó el Mundial 2022?")
        self.assertEqual(parsed["options"], ["Brasil", "Argentina", "Francia", "Alemania"])
        self.assertEqual(parsed["correct"], 1)

    def test_parse_rejects_malformed(self):
        self.assertIsNone(app.parse_trivia_question("no sé, invento yo las preguntas"))
        self.assertIsNone(app.parse_trivia_question(
            "PREGUNTA: ¿Algo?\nOPCION 1: una\nOPCION 2: dos\nCORRECTA: 1"
        ))


class MatchAnswerTests(unittest.TestCase):
    options = ["Brasil", "Argentina", "Francia", "Alemania"]

    def match(self, text):
        return app.trivia_match_answer(text, self.options)

    def test_number(self):
        self.assertEqual(self.match("la 2"), 1)
        self.assertEqual(self.match("2"), 1)

    def test_letter(self):
        self.assertEqual(self.match("b"), 1)
        self.assertEqual(self.match("c"), 2)
        self.assertIsNone(self.match("la banda"))

    def test_number_words(self):
        self.assertEqual(self.match("la dos", ), 1)
        self.assertEqual(self.match("digo que la cuatro"), 3)

    def test_ordinal(self):
        self.assertEqual(self.match("la primera"), 0)
        self.assertEqual(self.match("la última"), 3)
        self.assertEqual(self.match("la tercera"), 2)

    def test_fuzzy_option_text(self):
        self.assertEqual(self.match("Argentina, obvio"), 1)
        self.assertEqual(self.match("digo que alemania"), 3)

    def test_no_match(self):
        self.assertIsNone(self.match("no tengo idea"))
        self.assertIsNone(self.match("9"))


class VoiceRotationTests(unittest.TestCase):
    def test_random_lineup_is_distinct(self):
        for _ in range(25):
            lineup = app.trivia_round_voices(7999)
            self.assertEqual(len(lineup), 3)
            self.assertEqual(len(set(lineup)), 3)

    def test_picked_lineup_wins(self):
        app.trivia_lineups[7999] = ["es-AR-TomasNeural", "es-MX-DaliaNeural", "es-CU-ManuelNeural"]
        self.assertEqual(
            app.trivia_round_voices(7999),
            ("es-AR-TomasNeural", "es-MX-DaliaNeural", "es-CU-ManuelNeural"),
        )
        app.trivia_lineups.pop(7999, None)


class GenerationPromptTests(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_carries_category_country_and_exclusions(self):
        with patch.object(app, "complete", new=AsyncMock(return_value=QUESTION_TEXT)) as complete:
            parsed = await app.trivia_generate_question(
                "ciencia", "Argentina", app.deque(["¿Pregunta vieja uno?"], maxlen=80)
            )
        self.assertIsNotNone(parsed)
        prompt = complete.await_args.args[0][0]["content"]
        self.assertIn('"ciencia"', prompt)
        self.assertIn("Argentina", prompt)
        self.assertIn("¿Pregunta vieja uno?", prompt)

    async def test_deportes_hint_excludes_football(self):
        with patch.object(app, "complete", new=AsyncMock(return_value=QUESTION_TEXT)) as complete:
            await app.trivia_generate_question("deportes", None, app.deque(maxlen=80))
        prompt = complete.await_args.args[0][0]["content"]
        self.assertIn("MENOS fútbol", prompt)
        self.assertIn("bochas", prompt)

    async def test_generation_failure_returns_none(self):
        with patch.object(app, "complete", new=AsyncMock(return_value="texto sin formato")):
            self.assertIsNone(await app.trivia_generate_question("arte", None, app.deque(maxlen=80)))

    async def test_prompt_difficulty_scales_with_level(self):
        with patch.object(app, "complete", new=AsyncMock(return_value=QUESTION_TEXT)) as complete:
            await app.trivia_generate_question("arte", None, app.deque(maxlen=80), level=3)
        self.assertIn("fácil", complete.await_args.args[0][0]["content"])
        with patch.object(app, "complete", new=AsyncMock(return_value=QUESTION_TEXT)) as complete:
            await app.trivia_generate_question("arte", None, app.deque(maxlen=80), level=100)
        self.assertIn("de experto", complete.await_args.args[0][0]["content"])


class SpinTests(unittest.IsolatedAsyncioTestCase):
    async def spin(self, chat_id=7201, countries=False):
        game = fresh_game(chat_id, countries)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 999})), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice", new=AsyncMock()), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "send_spin_animation", new=AsyncMock()), \
             patch.object(app, "trivia_sfx_ogg", new=AsyncMock(return_value=b"sfx")), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "join_ogg", new=AsyncMock(return_value=b"joined")), \
             patch.object(app, "trivia_start_timer"), \
             patch.object(app, "complete", new=AsyncMock(return_value=QUESTION_TEXT)):
            await app.trivia_spin(chat_id)
        return game, sent_text

    async def test_spin_sets_question_phase(self):
        game, sent_text = await self.spin()
        self.assertEqual(game["phase"], "question")
        self.assertEqual(game["current"]["correct"], 1)
        self.assertEqual(game["current"]["question"], "¿Qué país ganó el Mundial 2022?")

    async def test_countries_mode_picks_a_country(self):
        game, _ = await self.spin(countries=True)
        self.assertIn(game["current"]["country"], app.TRIVIA_COUNTRIES)

    async def test_won_category_never_spins_again(self):
        chat_id = 7202
        game = fresh_game(chat_id)
        game["won"] = list(app.TRIVIA_CATEGORIES[1:])  # only "deportes" left
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 1})), \
             patch.object(app, "send_text", new=AsyncMock()), \
             patch.object(app, "send_voice", new=AsyncMock()), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "send_spin_animation", new=AsyncMock()), \
             patch.object(app, "trivia_sfx_ogg", new=AsyncMock(return_value=b"s")), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"o")), \
             patch.object(app, "join_ogg", new=AsyncMock(return_value=b"j")), \
             patch.object(app, "complete", new=AsyncMock(return_value=QUESTION_TEXT)):
            await app.trivia_spin(chat_id)
        self.assertEqual(game["current"]["category"], "deportes")

    async def test_all_categories_won_ends_champion(self):
        chat_id = 7203
        game = fresh_game(chat_id)
        game["won"] = list(app.TRIVIA_CATEGORIES)
        sent = []
        with patch.object(app, "send_text", side_effect=lambda c, t, **k: sent.append(t)):
            await app.trivia_spin(chat_id)
        self.assertIn("campeón absoluto", sent[0])
        self.assertNotIn(chat_id, app.trivia_games)

    async def test_question_is_tracked_for_no_repeat(self):
        game, _ = await self.spin()
        self.assertIn("¿Qué país ganó el Mundial 2022?", list(game["asked"]))


class AnswerTests(unittest.IsolatedAsyncioTestCase):
    async def answer(self, chat_id=7301, index=1):
        game = fresh_game(chat_id)
        current_question(game)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock(return_value="Ay, che, erraste feo.")):
            await app.trivia_handle_answer(chat_id, index)
        return game, sent_text

    async def test_correct_answer_scores(self):
        game, sent_text = await self.answer(index=1)
        self.assertEqual(game["score"]["fútbol mundial"], 1)
        self.assertEqual(game["lives"], 3)
        self.assertTrue(any("1 de 5" in text for text in sent_text))

    async def test_wrong_answer_costs_a_life_and_mocks(self):
        game, sent_text = await self.answer(index=0)
        self.assertEqual(game["lives"], 2)
        self.assertTrue(any("La correcta era Argentina" in text for text in sent_text))
        self.assertTrue(any("erraste feo" in text for text in sent_text))

    async def test_third_error_ends_the_game(self):
        chat_id = 7302
        game = fresh_game(chat_id)
        game["lives"] = 1
        current_question(game)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock(return_value="uff")):
            await app.trivia_handle_answer(chat_id, 0)
        self.assertTrue(any("Fin de la partida" in text for text in sent_text))
        self.assertNotIn(chat_id, app.trivia_games)

    async def test_fifth_correct_wins_category(self):
        chat_id = 7303
        game = fresh_game(chat_id)
        game["score"]["fútbol mundial"] = 4
        current_question(game)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock()):
            await app.trivia_handle_answer(chat_id, 1)
        self.assertIn("fútbol mundial", game["won"])
        self.assertTrue(any("ganaste la categoría" in text for text in sent_text))

    async def test_answer_marks_message_in_place(self):
        chat_id = 7304
        game = fresh_game(chat_id)
        current_question(game)
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()) as telegram, \
             patch.object(app, "send_text", new=AsyncMock()), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock(return_value="jja")):
            await app.trivia_handle_answer(chat_id, 3)
        edits = [c for c in telegram.await_args_list if c.args and c.args[0] == "editMessageText"]
        self.assertEqual(len(edits), 1)
        body = edits[0].kwargs["text"]
        self.assertIn("🟢 Argentina", body)
        self.assertIn("❌ Alemania", body)

    async def test_mock_llm_failure_falls_back(self):
        chat_id = 7305
        game = fresh_game(chat_id)
        current_question(game)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock(side_effect=RuntimeError("down"))):
            await app.trivia_handle_answer(chat_id, 0)
        self.assertTrue(any("La correcta era Argentina" in text for text in sent_text))


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_answer_routes_to_game(self):
        chat_id = 7401
        game = fresh_game(chat_id)
        current_question(game)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "transcribe", new=AsyncMock(return_value="la dos")), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock(return_value="ok")):
            await app.handle_message({"chat": {"id": chat_id}, "voice": {"file_id": "v1"}})
        self.assertEqual(game["score"].get("fútbol mundial"), 1)

    async def test_unclear_answer_keeps_question_open(self):
        chat_id = 7402
        game = fresh_game(chat_id)
        current_question(game)
        sent_text = []
        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)):
            await app.handle_message({"chat": {"id": chat_id}, "text": "no tengo idea"})
        self.assertEqual(game["phase"], "question")
        self.assertIn("No entendí la respuesta", sent_text[0])

    async def test_salir_quits_the_game(self):
        chat_id = 7403
        fresh_game(chat_id)
        app.trivia_games[chat_id]["phase"] = "question"
        app.trivia_games[chat_id]["current"] = {"options": ["a", "b", "c", "d"], "correct": 0}
        sent_text = []
        with patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)):
            await app.handle_message({"chat": {"id": chat_id}, "text": "salir"})
        self.assertNotIn(chat_id, app.trivia_games)
        self.assertIn("TERMINÓ LA RULETA", sent_text[0])

    async def test_gira_respins(self):
        chat_id = 7404
        fresh_game(chat_id)
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 1})), \
             patch.object(app, "send_text", new=AsyncMock()), \
             patch.object(app, "send_voice", new=AsyncMock()), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "send_spin_animation", new=AsyncMock()), \
             patch.object(app, "trivia_sfx_ogg", new=AsyncMock(return_value=b"s")), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"o")), \
             patch.object(app, "join_ogg", new=AsyncMock(return_value=b"j")), \
             patch.object(app, "trivia_start_timer"), \
             patch.object(app, "complete", new=AsyncMock(return_value=QUESTION_TEXT)):
            await app.handle_message({"chat": {"id": chat_id}, "text": "girá la ruleta"})
        self.assertEqual(app.trivia_games[chat_id]["phase"], "question")

    async def test_stale_answer_button_is_tolerated(self):
        chat_id = 7405
        app.trivia_games.pop(chat_id, None)
        callback = {
            "id": "cb1", "data": "tans:2",
            "message": {"chat": {"id": chat_id}, "message_id": 1},
            "from": {"first_name": "Escorpio"},
        }
        with patch.object(app, "telegram", new=AsyncMock()) as telegram:
            await app.handle_callback(callback)
        acks = [c for c in telegram.await_args_list if c.args and c.args[0] == "answerCallbackQuery"]
        self.assertIn("ya pasó", acks[0].kwargs["text"])

    async def test_trivia_begin_clears_group_modes(self):
        chat_id = 7406
        app.trio_enabled[chat_id] = True
        app.trio_pairs[chat_id] = ("es-AR-TomasNeural", "es-MX-DaliaNeural", "es-CU-ManuelNeural")
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", new=AsyncMock()), \
             patch.object(app, "send_voice", new=AsyncMock()):
            await app.trivia_begin(chat_id, False)
        self.assertFalse(app.trio_enabled[chat_id])

    async def test_lineup_completion_uses_three_voices(self):
        chat_id = 7407
        callback = {
            "id": "cb2", "data": "gsel:trivia:es-CU-ManuelNeural",
            "message": {"chat": {"id": chat_id}, "message_id": 77},
            "from": {"first_name": "Escorpio"},
        }
        app.group_selection[chat_id] = {
            "kind": "trivia",
            "voices": ["es-AR-TomasNeural", "es-MX-DaliaNeural"],
        }
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)):
            await app.handle_callback(callback)
        self.assertEqual(
            app.trivia_lineups[chat_id],
            ["es-AR-TomasNeural", "es-MX-DaliaNeural", "es-CU-ManuelNeural"],
        )
        self.assertTrue(any("presenta" in text for text in sent_text))
        app.trivia_lineups.pop(chat_id, None)


class AssetTests(unittest.TestCase):
    def test_spin_gif_builds_small_and_animated(self):
        data = app.build_spin_gif()
        self.assertTrue(data.startswith(b"GIF89a"))
        self.assertLess(len(data), 2_000_000)

    def test_spin_sfx_builds_wav(self):
        data = app.build_spin_sfx()
        self.assertTrue(data.startswith(b"RIFF"))
        self.assertGreater(len(data), 50_000)


class MechanicsTests(unittest.TestCase):
    def test_lives_line_in_words(self):
        self.assertEqual(app.trivia_lives_line(3), "Te quedan tres vidas.")
        self.assertEqual(app.trivia_lives_line(2), "Te quedan dos vidas.")
        self.assertEqual(app.trivia_lives_line(1), "Te queda una vida.")
        self.assertEqual(app.trivia_lives_line(0), "Te quedaste sin vidas.")

    def test_difficulty_tiers(self):
        self.assertEqual(app.trivia_difficulty(1), "fácil")
        self.assertEqual(app.trivia_difficulty(10), "fácil")
        self.assertEqual(app.trivia_difficulty(11), "media")
        self.assertEqual(app.trivia_difficulty(30), "media")
        self.assertEqual(app.trivia_difficulty(31), "difícil")
        self.assertEqual(app.trivia_difficulty(60), "difícil")
        self.assertEqual(app.trivia_difficulty(61), "de experto")
        self.assertEqual(app.trivia_difficulty(150), "de experto")

    def test_level_up_and_cap(self):
        game = {"level": 1}
        self.assertEqual(app.trivia_level_up(game), 2)
        self.assertEqual(game["level"], 2)
        game["level"] = app.TRIVIA_MAX_LEVEL
        self.assertEqual(app.trivia_level_up(game), 0)
        self.assertEqual(game["level"], app.TRIVIA_MAX_LEVEL)

    def test_streak_gifts_a_life(self):
        game = {"streak": 3, "lives": 2}
        self.assertTrue(app.trivia_apply_gift(game))
        self.assertEqual(game["lives"], 3)

    def test_gift_respects_the_cap(self):
        game = {"streak": 3, "lives": app.TRIVIA_MAX_LIVES}
        self.assertFalse(app.trivia_apply_gift(game))
        self.assertEqual(game["lives"], app.TRIVIA_MAX_LIVES)

    def test_gift_only_on_full_streaks(self):
        self.assertFalse(app.trivia_apply_gift({"streak": 2, "lives": 3}))
        self.assertFalse(app.trivia_apply_gift({"streak": 4, "lives": 3}))
        self.assertTrue(app.trivia_apply_gift({"streak": 6, "lives": 3}))

    def test_timeout_costs_a_life(self):
        game = {"lives": 3, "streak": 2}
        self.assertFalse(app.trivia_timeout_life(game))
        self.assertEqual(game["lives"], 2)
        self.assertEqual(game["streak"], 0)

    def test_timeout_on_last_life_ends_the_game(self):
        game = {"lives": 1, "streak": 5}
        self.assertTrue(app.trivia_timeout_life(game))

    def test_country_prize_known_and_default(self):
        self.assertIn("mate", app.trivia_country_prize("Argentina"))
        self.assertIn("café", app.trivia_country_prize("Colombia"))
        self.assertIn("Liechtenstein", app.trivia_country_prize("Liechtenstein"))

    def test_all_american_countries_present(self):
        for country in ("Guatemala", "Costa Rica", "Panamá", "México",
                        "Estados Unidos", "Canadá", "El Salvador", "Belice",
                        "Nicaragua", "Honduras", "Cuba", "Jamaica", "Haití",
                        "Bahamas", "Barbados", "Guyana", "Surinam"):
            self.assertIn(country, app.TRIVIA_COUNTRIES)


class CountryModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_completing_a_country_awards_its_prize(self):
        chat_id = 7501
        game = fresh_game(chat_id, countries=True)
        game["country"] = "Argentina"
        game["country_won"] = list(app.TRIVIA_CATEGORIES)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")):
            await app.trivia_spin(chat_id)
        self.assertTrue(any("completaste TODAS" in text for text in sent_text))
        self.assertTrue(any("mate" in text for text in sent_text))
        self.assertIn("Argentina", game["countries_done"])
        self.assertIsNone(game["country"])
        self.assertIn(chat_id, app.trivia_games)  # the run continues

    async def test_all_countries_done_crowns_world_champion(self):
        chat_id = 7502
        game = fresh_game(chat_id, countries=True)
        game["countries_done"] = list(app.TRIVIA_COUNTRIES)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)):
            await app.trivia_spin(chat_id)
        self.assertTrue(any("CAMPEÓN MUNDIAL" in text for text in sent_text))
        self.assertNotIn(chat_id, app.trivia_games)

    async def test_completed_country_never_spins_again(self):
        chat_id = 7503
        game = fresh_game(chat_id, countries=True)
        game["countries_done"] = [c for c in app.TRIVIA_COUNTRIES if c != "Chile"]
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 1})), \
             patch.object(app, "send_text", new=AsyncMock()), \
             patch.object(app, "send_voice", new=AsyncMock()), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "send_spin_animation", new=AsyncMock()), \
             patch.object(app, "trivia_sfx_ogg", new=AsyncMock(return_value=b"s")), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"o")), \
             patch.object(app, "join_ogg", new=AsyncMock(return_value=b"j")), \
             patch.object(app, "trivia_start_timer"), \
             patch.object(app, "complete", new=AsyncMock(return_value=QUESTION_TEXT)):
            await app.trivia_spin(chat_id)
        self.assertEqual(game["current"]["country"], "Chile")

    async def test_category_win_counts_toward_the_country(self):
        chat_id = 7504
        game = fresh_game(chat_id, countries=True)
        game["country"] = "Colombia"
        game["score"]["fútbol mundial"] = 4
        current_question(game)
        game["current"]["country"] = "Colombia"
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock()):
            await app.trivia_handle_answer(chat_id, 1)
        self.assertIn("fútbol mundial", game["country_won"])
        self.assertEqual(game["won"], [])
        self.assertTrue(any("de Colombia" in text for text in sent_text))

    async def test_correct_answer_levels_up(self):
        chat_id = 7505
        game = fresh_game(chat_id)
        current_question(game)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock(return_value="bien")):
            await app.trivia_handle_answer(chat_id, 1)
        self.assertEqual(game["level"], 2)
        self.assertTrue(any("nivel 2" in text for text in sent_text))

    async def test_streak_of_three_gifts_a_life_in_game(self):
        chat_id = 7506
        game = fresh_game(chat_id)
        game["streak"] = 2
        current_question(game)
        sent_text = []
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock(return_value="bien")):
            await app.trivia_handle_answer(chat_id, 1)
        self.assertEqual(game["lives"], 4)
        self.assertTrue(any("te regalamos una vida" in text for text in sent_text))


class TimerTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_costs_a_life_and_forfeits_the_question(self):
        chat_id = 7601
        game = fresh_game(chat_id)
        current_question(game)
        game["timer_gen"] = 7
        game["deadline"] = 123.0
        sent_text = []
        with patch.object(app, "TRIVIA_TIMER_SECONDS", 0), \
             patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")):
            await app.trivia_timer_timeout(chat_id, 7)
        self.assertEqual(game["lives"], 2)
        self.assertEqual(game["phase"], "ready")
        self.assertIsNone(game["current"])
        self.assertIsNone(game["sprint"])
        self.assertTrue(any("Se acabó el cronómetro" in text for text in sent_text))

    async def test_timeout_on_last_life_ends_the_game(self):
        chat_id = 7602
        game = fresh_game(chat_id)
        game["lives"] = 1
        game["timer_gen"] = 3
        sent_text = []
        with patch.object(app, "TRIVIA_TIMER_SECONDS", 0), \
             patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock()), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)):
            await app.trivia_timer_timeout(chat_id, 3)
        self.assertNotIn(chat_id, app.trivia_games)
        self.assertTrue(any("Fin de la partida" in text for text in sent_text))

    async def test_stale_timer_generation_is_ignored(self):
        chat_id = 7603
        game = fresh_game(chat_id)
        game["timer_gen"] = 5
        with patch.object(app, "TRIVIA_TIMER_SECONDS", 0), \
             patch.object(app, "send_text", new=AsyncMock()) as send_text:
            await app.trivia_timer_timeout(chat_id, 4)
        self.assertEqual(game["lives"], 3)
        send_text.assert_not_awaited()

    async def test_warning_hurries_him_along(self):
        chat_id = 7604
        game = fresh_game(chat_id)
        game["timer_gen"] = 2
        game["deadline"] = 123.0
        sent_text = []
        with patch.object(app, "TRIVIA_TIMER_SECONDS", 0), \
             patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")):
            await app.trivia_timer_warning(chat_id, 2, 30)
        self.assertTrue(any("30 segundos" in text for text in sent_text))

    async def test_cancelled_timer_warns_nothing(self):
        chat_id = 7605
        game = fresh_game(chat_id)
        game["timer_gen"] = 2
        app.trivia_cancel_timer(game)
        with patch.object(app, "TRIVIA_TIMER_SECONDS", 0), \
             patch.object(app, "send_text", new=AsyncMock()) as send_text:
            await app.trivia_timer_warning(chat_id, 3, 30)
        send_text.assert_not_awaited()


class TidyChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_keyboard_retires_the_first(self):
        chat_id = 7701
        app.trivia_last_keyboard.pop(chat_id, None)
        ids = iter([100, 101])
        with patch.object(app, "telegram", new=AsyncMock(
                side_effect=lambda *a, **k: {"message_id": next(ids)}
                if a and a[0] == "sendMessage" else {})) as telegram:
            await app.trivia_menu(chat_id)
            await app.trivia_menu(chat_id)
        clears = [c for c in telegram.await_args_list
                  if c.args and c.args[0] == "editMessageReplyMarkup"]
        self.assertEqual(len(clears), 1)
        self.assertEqual(clears[0].kwargs["message_id"], 100)
        self.assertEqual(clears[0].kwargs["reply_markup"], {"inline_keyboard": []})
        self.assertEqual(app.trivia_last_keyboard[chat_id], 101)
        app.trivia_last_keyboard.pop(chat_id, None)

    async def test_salir_deletes_the_game_flow(self):
        chat_id = 7702
        game = fresh_game(chat_id)
        game["sent_ids"] = [11, 12, 13]
        game["phase"] = "question"
        game["current"] = {"options": ["a", "b", "c", "d"], "correct": 0}
        sent_text = []
        with patch.object(app, "telegram", new=AsyncMock()) as telegram, \
             patch.object(app, "send_text", side_effect=lambda c, t, **k: sent_text.append(t)):
            await app.handle_message({"chat": {"id": chat_id}, "text": "salir"})
        deletes = [c for c in telegram.await_args_list
                   if c.args and c.args[0] == "deleteMessage"]
        self.assertEqual([c.kwargs["message_id"] for c in deletes], [11, 12, 13])
        self.assertNotIn(chat_id, app.trivia_games)
        self.assertIn("TERMINÓ LA RULETA", sent_text[0])

    async def test_game_over_deletes_the_flow(self):
        chat_id = 7703
        game = fresh_game(chat_id)
        game["lives"] = 1
        game["sent_ids"] = [21, 22]
        current_question(game)
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 30})) as telegram, \
             patch.object(app, "send_text", new=AsyncMock(return_value={"message_id": 30})), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock(return_value="uff")):
            await app.trivia_handle_answer(chat_id, 0)
        deletes = [c.kwargs["message_id"] for c in telegram.await_args_list
                   if c.args and c.args[0] == "deleteMessage"]
        # 21/22 = seeded flow; 30 = the feedback message (mocked id), also flow.
        self.assertEqual(deletes, [21, 22, 30])
        self.assertNotIn(chat_id, app.trivia_games)

    async def test_menu_message_is_deleted_when_game_ends(self):
        chat_id = 7705
        with patch.object(app, "trivia_clear_keyboard", new=AsyncMock()), \
             patch.object(app, "send_text", new=AsyncMock(return_value={"message_id": 88})):
            await app.trivia_menu(chat_id)
        self.assertEqual(app.trivia_pending_menu[chat_id], 88)
        game = fresh_game(chat_id)
        menu_mid = app.trivia_pending_menu.pop(chat_id, None)
        app.trivia_track(game, menu_mid)
        game["sent_ids"] = [88, 91]
        game["phase"] = "question"
        game["current"] = {"options": ["a", "b", "c", "d"], "correct": 0}
        with patch.object(app, "telegram", new=AsyncMock()) as telegram, \
             patch.object(app, "send_text", new=AsyncMock(return_value={"message_id": 99})):
            await app.handle_message({"chat": {"id": chat_id}, "text": "salir"})
        deletes = [c.kwargs["message_id"] for c in telegram.await_args_list
                   if c.args and c.args[0] == "deleteMessage"]
        self.assertIn(88, deletes)
        self.assertNotIn(chat_id, app.trivia_pending_menu)

    async def test_answer_leaves_one_live_keyboard(self):
        chat_id = 7704
        game = fresh_game(chat_id)
        current_question(game)
        app.trivia_last_keyboard[chat_id] = 555  # the question's keyboard
        with patch.object(app, "get_preferred_name", return_value="Escorpio"), \
             patch.object(app, "telegram", new=AsyncMock(return_value={"message_id": 42})), \
             patch.object(app, "send_text", new=AsyncMock(return_value={"message_id": 42})), \
             patch.object(app, "send_voice_audio", new=AsyncMock()), \
             patch.object(app, "synthesize", new=AsyncMock(return_value=b"ogg")), \
             patch.object(app, "complete", new=AsyncMock(return_value="bien")):
            await app.trivia_handle_answer(chat_id, 1)
        # The question keyboard was retired; the seguimos keyboard is the live one.
        self.assertEqual(app.trivia_last_keyboard[chat_id], 42)
        self.assertIn(42, game["sent_ids"])
        app.trivia_last_keyboard.pop(chat_id, None)


if __name__ == "__main__":
    unittest.main()
