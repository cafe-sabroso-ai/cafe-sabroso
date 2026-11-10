import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

import os
import tempfile

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "cafe-sabroso-webapp-tests.db"))

import webapp


class FakeWS:
    def __init__(self):
        self.messages = []
        self.closed = None

    async def send_text(self, data):
        self.messages.append(json.loads(data))

    async def accept(self):
        pass

    async def close(self, code=1000):
        self.closed = code


def make_room(*names, mode="sala", capacity=None):
    room = {
        "players": [], "next_id": 1, "mode": mode, "capacity": capacity,
        "starter": 0, "turn": 0, "match": 1, "phase": "lobby", "spinning": False,
        "question": None, "scores": {}, "timer_task": None, "audio_lock": asyncio.Lock(),
        "used_retos": set(), "used_verdades": set(),
        "voice": "es-AR-ElenaNeural", "question_voice": "es-UY-ValentinaNeural",
        "game": ("paises" if mode in ("solo_paises", "paises")
                 else "ahorcado" if mode in ("solo_ahorcado", "ahorcado")
                 else "bomba" if mode in ("solo_bomba", "bomba")
                 else "misterio" if mode in ("solo_misterio", "misterio")
                 else None if mode == "sala"
                 else "categorias"),
        "country": None, "country_done": set(), "countries_won": {},
        "ahorcado": {"levels": {}, "used": set(), "word": None, "hint": "",
                     "guessed": set(), "wrong": set(), "attempts": 0},
        "cat_progress": {},
        "chat_voices": {},
        "bomba": {"lives": {}, "prompt": None, "keywords": [], "said": set(),
                  "used": set(), "fuse": 0},
        "misterio": {"lives": {}, "solved": {}, "used": set(), "case": None,
                     "case_idx": -1},
        "teams": None,
    }
    for key in webapp.MC_USED_KEYS.values():
        room[key] = set()
    for name in names:
        pid = room["next_id"]
        room["next_id"] += 1
        room["players"].append({"id": pid, "name": name, "ws": FakeWS()})
        room["scores"][pid] = 0
    return room


def says(ws):
    return [m for m in ws.messages if m["event"] == "say"]


async def fake_clock(room, player_id):
    return None


class BankTests(unittest.TestCase):
    def test_banks_are_big_and_unique(self):
        self.assertGreaterEqual(len(webapp.RETOS), 25)
        self.assertGreaterEqual(len(webapp.VERDADES), 25)
        self.assertEqual(len(webapp.RETOS), len(set(webapp.RETOS)))
        self.assertEqual(len(webapp.VERDADES), len(set(webapp.VERDADES)))

    def test_cards_are_short_and_harmless(self):
        for item in webapp.RETOS + webapp.VERDADES:
            self.assertLessEqual(len(item), 200)
            lowered = item.lower()
            for banned in ("http", "www.", "desnud", "menor de edad"):
                self.assertNotIn(banned, lowered)

    def test_mc_banks_are_well_formed(self):
        for bank in (webapp.TRIVIA_MC, webapp.REFRANES_MC, webapp.PAISES_MC):
            self.assertGreaterEqual(len(bank), 24)
            questions = set()
            for q, options, correct in bank:
                self.assertEqual(len(options), 3)
                self.assertIn(correct, (0, 1, 2))
                self.assertNotIn(q, questions)
                questions.add(q)

    def test_every_mc_category_has_a_bank_and_label(self):
        for cat, bank in webapp.MC_BANKS.items():
            self.assertIn(cat, webapp.CATEGORIES)
            self.assertIn(cat, webapp.MC_USED_KEYS)
            self.assertTrue(bank)


class RoomTests(unittest.TestCase):
    def test_codes_are_four_chars_and_unique(self):
        webapp.rooms["AAAA"] = {}
        try:
            for _ in range(20):
                code = webapp.new_room_code()
                self.assertEqual(len(code), 4)
                self.assertTrue(code.isalnum())
                self.assertNotEqual(code, "AAAA")
        finally:
            webapp.rooms.pop("AAAA", None)

    def test_room_state_reports_turn_and_scores(self):
        room = make_room("Ana", "Beto")
        state = webapp.room_state(room)
        self.assertEqual(state["turn"], 1)
        self.assertEqual(state["turn_name"], "Ana")
        room["scores"][2] = 3
        state = webapp.room_state(room)
        beto = [p for p in state["players"] if p["name"] == "Beto"][0]
        self.assertEqual(beto["score"], 3)

    def test_capacity_is_capped(self):
        self.assertEqual(webapp.MAX_PLAYERS, 100)


class SpinTests(unittest.IsolatedAsyncioTestCase):
    async def test_spin_announces_verdad_reto_and_waits_for_done(self):
        room = make_room("Ana", "Beto")
        room["phase"] = "verdad_reto_ready"
        player = room["players"][0]
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.do_spin(room, player)
        self.assertEqual(room["phase"], "verdad_reto")
        starts = [m for m in room["players"][0]["ws"].messages if m["event"] == "spin_start"]
        self.assertEqual(len(starts), 1)
        self.assertIn(starts[0], room["players"][1]["ws"].messages)
        waits = [m for m in room["players"][0]["ws"].messages if m["event"] == "await_done"]
        self.assertEqual(len(waits), 1)
        self.assertIn("te salió", narr.await_args_list[0][0][1])


class CategorySpinTests(unittest.IsolatedAsyncioTestCase):
    async def test_category_spin_lands_and_asks_a_question(self):
        room = make_room("Ana", "Beto")
        room["phase"] = "spin_ready"
        player = room["players"][0]
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.do_category_spin(room, player, chosen="cultura")
        self.assertEqual(room["phase"], "question")
        self.assertEqual(room["question"]["category"], "cultura")
        starts = [m for m in room["players"][1]["ws"].messages if m["event"] == "spin_start"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(starts[0]["labels"]), len(webapp.CATEGORIES))

    async def test_category_spin_can_land_on_verdad_reto(self):
        room = make_room("Ana", "Beto")
        room["phase"] = "spin_ready"
        player = room["players"][0]
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.do_category_spin(room, player, chosen="verdad_reto")
        self.assertEqual(room["phase"], "verdad_reto")
        waits = [m for m in player["ws"].messages if m["event"] == "await_done"]
        self.assertEqual(len(waits), 1)


    async def test_paises_wheel_never_lands_on_verdad_reto(self):
        room = make_room("Ana", mode="solo_paises", capacity=1)
        room["phase"] = "spin_ready"
        player = room["players"][0]
        pools = []
        real_choice = webapp.random.choice

        def spy(seq):
            pools.append(list(seq))
            return real_choice(seq)

        with patch.object(webapp.random, "choice", side_effect=spy), \
             patch.object(webapp, "narrate", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.do_category_spin(room, player)
        self.assertNotIn("verdad_reto", pools[0])
        self.assertEqual(len(pools[0]), len(webapp.MC_BANKS))
        self.assertEqual(room["phase"], "question")


class CountryModeTests(unittest.IsolatedAsyncioTestCase):
    FAKE_COUNTRIES = ["Argentina", "Chile", "Brasil"]

    def stub_countries(self):
        import sys, types
        return patch.dict(sys.modules, {"app": types.SimpleNamespace(TRIVIA_COUNTRIES=self.FAKE_COUNTRIES)})

    async def spin_country(self, room):
        player = webapp.current_player(room)
        room["phase"] = "country_spin_ready"
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch("asyncio.sleep", new=AsyncMock()), \
             self.stub_countries():
            await webapp.do_country_spin(room, player)
        return player, narr

    async def test_country_spin_picks_a_country_and_starts_categories(self):
        room = make_room("Ana", "Beto", mode="paises", capacity=2)
        player, narr = await self.spin_country(room)
        self.assertIn(room["country"], self.FAKE_COUNTRIES)
        self.assertEqual(room["phase"], "spin_ready")
        self.assertIn(room["country"], narr.await_args_list[0][0][1])
        turns = [m for m in player["ws"].messages if m["event"] == "your_turn"]
        self.assertEqual(turns[-1]["kind"], "category")

    async def test_correct_answer_keeps_the_player_and_levels_up(self):
        room = make_room("Ana", "Beto", mode="paises", capacity=2)
        await self.spin_country(room)
        player = webapp.current_player(room)
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "begin_turn", new=AsyncMock()):
            await webapp.ask_question(room, player, "cultura", f", por {room['country']}")
            for _ in range(5):
                await webapp.resolve_answer(room, player, room["question"]["correct"])
        self.assertIn("cultura", room["country_done"])
        self.assertEqual(webapp.current_player(room)["name"], player["name"])
        self.assertIn("Pasó al nivel 2", narr.await_args_list[-1][0][1])

    async def test_wrong_answer_loses_life_but_keeps_category(self):
        room = make_room("Ana", "Beto", mode="paises", capacity=2)
        await self.spin_country(room)
        player = webapp.current_player(room)
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "begin_turn", new=AsyncMock()):
            await webapp.ask_question(room, player, "cultura")
            await webapp.resolve_answer(room, player, (room["question"]["correct"] + 1) % 3)
        self.assertEqual(webapp.current_player(room)["name"], "Ana")
        self.assertEqual(webapp.quiz_lives(room, player), 3)
        texts = [c[0][1] for c in narr.await_args_list]
        self.assertTrue(any("Perdiste una vida, te quedan tres" in t for t in texts))

    async def test_completing_all_categories_wins_the_country(self):
        room = make_room("Ana", mode="solo_paises", capacity=1)
        await self.spin_country(room)
        player = webapp.current_player(room)
        done = set(webapp.MC_BANKS) - {"cultura"}
        room["country_done"] = done
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "begin_turn", new=AsyncMock()):
            await webapp.ask_question(room, player, "cultura")
            for _ in range(5):
                await webapp.resolve_answer(room, player, room["question"]["correct"])
        self.assertEqual(room["countries_won"].get(player["id"]), 1)
        self.assertIsNone(room["country"])
        texts = [c[0][1] for c in narr.await_args_list]
        self.assertTrue(any("completó" in t for t in texts))

    async def test_two_countries_win_the_game(self):
        room = make_room("Ana", "Beto", mode="paises", capacity=2)
        await self.spin_country(room)
        player = webapp.current_player(room)
        room["countries_won"][player["id"]] = webapp.COUNTRIES_TO_WIN - 1
        room["country_done"] = set(webapp.MC_BANKS) - {"cultura"}
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "start_match", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.ask_question(room, player, "cultura")
            for _ in range(5):
                await webapp.resolve_answer(room, player, room["question"]["correct"])
        self.assertEqual(room["phase"], "gameover")
        texts = [c[0][1] for c in narr.await_args_list]
        self.assertTrue(any("Ganó Ana" in t and "Le ganó a Beto" in t for t in texts))


class AhorcadoTests(unittest.IsolatedAsyncioTestCase):
    def make_ahorcado_room(self, *names):
        room = make_room(*names, mode="ahorcado" if len(names) > 1 else "solo_ahorcado",
                         capacity=max(1, len(names)))
        room["ahorcado"].update(word="MATE", hint="Infusión con bombilla.",
                                guessed=set(), wrong=set(), attempts=3)
        room["phase"] = "ahorcado"
        return room

    def test_positions_are_spoken_with_casilleros(self):
        speak = {"A": "a", "M": "eme", "T": "te", "E": "e"}
        self.assertEqual(webapp.ah_positions_text("MATE", "A", speak),
                         "La palabra lleva una letra a, en el segundo casillero.")
        self.assertEqual(webapp.ah_positions_text("MAMÁ".replace("Á", "A"), "A", speak),
                         "La palabra lleva 2 letras a: una en el segundo casillero "
                         "y otra en el cuarto casillero.")

    def test_adjacent_revealed_letters_are_called_out(self):
        speak = {"A": "a", "M": "eme", "T": "te", "E": "e"}
        self.assertEqual(webapp.ah_adjacency_text("MATE", "A", {"M", "A"}, speak),
                         "La eme y la a están juntas.")
        self.assertEqual(webapp.ah_adjacency_text("MATE", "E", {"A"}, speak), "")

    async def test_correct_letter_keeps_the_turn(self):
        room = self.make_ahorcado_room("Ana", "Beto")
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr:
            await webapp.ah_guess(room, room["players"][0], ("letter", "M"))
        self.assertEqual(webapp.current_player(room)["name"], "Ana")
        self.assertIn("primer casillero", narr.await_args_list[0][0][1])
        self.assertIn("Seguís, Ana", narr.await_args_list[0][0][1])

    async def test_a_miss_passes_the_turn(self):
        room = self.make_ahorcado_room("Ana", "Beto")
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.ah_guess(room, room["players"][0], ("letter", "Z"))
        texts = [c[0][1] for c in narr.await_args_list]
        self.assertTrue(any("No hay zeta" in t and "Ahora sigue Beto" in t for t in texts))
        self.assertEqual(webapp.current_player(room)["name"], "Beto")
        self.assertEqual(room["ahorcado"]["attempts"], 3)  # new word, fresh attempts

    async def test_running_out_of_attempts_reveals_the_word(self):
        room = self.make_ahorcado_room("Ana")
        room["ahorcado"]["attempts"] = 1
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.ah_guess(room, room["players"][0], ("letter", "Z"))
        self.assertTrue(any("La palabra era eme, a, te, e" in t for t in
                            (c[0][1] for c in narr.await_args_list)))

    async def test_solving_levels_up_and_tells_the_room(self):
        room = self.make_ahorcado_room("Ana", "Beto")
        room["ahorcado"]["guessed"] = {"M", "A", "T"}
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.ah_guess(room, room["players"][0], ("letter", "E"))
        texts = [c[0][1] for c in narr.await_args_list]
        self.assertTrue(any("Ana pasó al nivel 2" in t and "ustedes están en el nivel 1" in t
                            for t in texts))
        self.assertEqual(room["ahorcado"]["levels"][1], 2)

    async def test_winning_the_top_level_ends_the_game(self):
        room = self.make_ahorcado_room("Ana", "Beto")
        room["ahorcado"]["levels"][1] = webapp.AHORCADO_WIN_LEVEL
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "start_match", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.ah_guess(room, room["players"][0], ("word", "MATE"))
        self.assertEqual(room["phase"], "gameover")
        self.assertTrue(any("Ganó Ana" in c[0][1] for c in narr.await_args_list))


class CategoryLevelTests(unittest.IsolatedAsyncioTestCase):
    async def test_five_correct_answers_pass_the_category(self):
        room = make_room("Ana", mode="solo", capacity=1)
        player = room["players"][0]
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "turn_clock", new=fake_clock):
            for _ in range(5):
                room["phase"] = "spin_ready"
                room["turn"] = 0
                await webapp.ask_question(room, player, "cultura")
                await webapp.resolve_answer(room, player, room["question"]["correct"])
        texts = [c[0][1] for c in narr.await_args_list]
        self.assertTrue(any("pasó el nivel de Cultura" in t for t in texts))
        self.assertEqual(room["scores"][1], 1)

    async def test_passed_categories_leave_the_wheel_pool(self):
        room = make_room("Ana", mode="solo", capacity=1)
        room["cat_progress"] = {1: {"cultura": 5, "historia": 1}}
        pools = []
        real_choice = webapp.random.choice

        def spy(seq):
            pools.append(list(seq))
            return real_choice(seq)

        with patch.object(webapp.random, "choice", side_effect=spy), \
             patch.object(webapp, "narrate", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.do_category_spin(room, room["players"][0])
        self.assertNotIn("cultura", pools[0])
        self.assertIn("historia", pools[0])
        self.assertIn("verdad_reto", pools[0])

    async def test_passing_three_categories_wins_the_game(self):
        room = make_room("Ana", "Beto", mode="solo", capacity=2)
        player = room["players"][0]
        room["cat_progress"] = {1: {"cultura": 5, "historia": 5}}
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "start_match", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.ask_question(room, player, "ciencia")
            for _ in range(5):
                await webapp.resolve_answer(room, player, room["question"]["correct"])
        self.assertEqual(room["phase"], "gameover")
        self.assertTrue(any("Ganó Ana" in c[0][1] for c in narr.await_args_list))


class VoiceAnswerTests(unittest.TestCase):
    def test_match_option_letters_and_ordinals(self):
        opts = ["Londres", "París", "Madrid"]
        self.assertEqual(webapp.match_option("la B", opts), 1)
        self.assertEqual(webapp.match_option("opción c", opts), 2)
        self.assertEqual(webapp.match_option("la tercera", opts), 2)
        self.assertEqual(webapp.match_option("digo que París", opts), 1)
        self.assertIsNone(webapp.match_option("no lo sé", opts))
        self.assertIsNone(webapp.match_option("", opts))


class QuestionTests(unittest.IsolatedAsyncioTestCase):
    async def ask(self, room, cat="cultura"):
        player = webapp.current_player(room)
        room["phase"] = "spin_ready"
        with patch.object(webapp, "narrate", new=AsyncMock()):
            await webapp.ask_question(room, player, cat)
        return player

    async def test_question_broadcasts_options(self):
        room = make_room("Ana", "Beto")
        player = await self.ask(room)
        qs = [m for m in room["players"][1]["ws"].messages if m["event"] == "question"]
        self.assertEqual(len(qs), 1)
        self.assertEqual(len(qs[0]["options"]), 4)
        self.assertEqual(qs[0]["player"], player["id"])
        self.assertEqual(room["phase"], "question")

    async def test_mc_cards_do_not_repeat_until_exhausted(self):
        room = make_room("Ana")
        one = webapp.pick_mc(room, "cultura")
        two = webapp.pick_mc(room, "cultura")
        self.assertNotEqual(one[0], two[0])

    async def test_correct_answer_keeps_run_and_turn(self):
        room = make_room("Ana", "Beto")
        player = await self.ask(room)
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.resolve_answer(room, player, room["question"]["correct"])
        self.assertEqual(room["quiz_run"]["correct"], 1)
        self.assertEqual(webapp.current_player(room)["name"], "Ana")

    async def test_wrong_answer_says_the_right_one_and_scores_nothing(self):
        room = make_room("Ana", "Beto")
        player = await self.ask(room)
        wrong = (room["question"]["correct"] + 1) % 3
        expected = question_right_letter_and_text(room)
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.resolve_answer(room, player, wrong)
        self.assertEqual(room["scores"][player["id"]], 0)
        self.assertIn("no es la correcta", narr.await_args_list[0][0][1])
        self.assertIn(expected, narr.await_args_list[0][0][1])


def question_right_letter_and_text(room):
    letters = ["A", "B", "C", "D"]
    q = room["question"]
    return f"Es la {letters[q['correct']]}: {q['options'][q['correct']]}."


class ScoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_listo_scores_and_pasar_does_not(self):
        room = make_room("Ana", "Beto")
        room["phase"] = "verdad_reto"
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.complete_verdad_reto(room, room["players"][0], done=True)
            await webapp.complete_verdad_reto(room, room["players"][1], done=False)
        self.assertEqual(room["scores"][1], 1)
        self.assertEqual(room["scores"][2], 0)

    async def test_winner_announced_and_rematch_rotates_the_starter(self):
        room = make_room("Ana", "Beto", mode="solo", capacity=2)
        room["scores"][1] = webapp.WIN_SCORE - 1
        room["phase"] = "verdad_reto"
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "turn_clock", new=fake_clock), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.complete_verdad_reto(room, room["players"][0], done=True)
        # Ganó Ana, se anunció, y arrancó la partida 2 con otro que empieza.
        self.assertTrue(any("Ganó Ana" in c[0][1] for c in narr.await_args_list))
        self.assertEqual(room["match"], 2)
        self.assertEqual(room["starter"], 1)
        self.assertEqual(room["scores"], {1: 0, 2: 0})
        self.assertEqual(webapp.current_player(room)["name"], "Beto")


class TimerTests(unittest.IsolatedAsyncioTestCase):
    async def test_frequent_chatter_sleeps_six_seconds_and_timeout_passes(self):
        room = make_room("Ana", "Beto")
        room["phase"] = "spin_ready"
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "begin_turn", new=AsyncMock()), \
             patch.object(webapp, "turn_chatter", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()) as sleep:
            await webapp.turn_clock(room, 1)
        self.assertEqual(room["turn"], 1)
        self.assertEqual(sleep.await_count, 10)
        self.assertTrue(all(c.args == (6,) for c in sleep.await_args_list))
        self.assertTrue(any("Se acabó el tiempo" in c.args[1] for c in narr.await_args_list))

    async def test_chatter_suppressed_while_capturing(self):
        room = make_room("Ana")
        room["mic_until"] = asyncio.get_running_loop().time() + 15
        with patch.object(webapp, "broadcast", new=AsyncMock()) as out:
            await webapp.turn_chatter(room, room["players"][0])
        out.assert_not_awaited()

    def test_four_options_and_d_match(self):
        for bank in webapp.MC_BANKS.values():
            for q, options, correct in bank:
                self.assertEqual(len(options), 4, q)
                self.assertEqual(len(set(options)), 4, q)
                self.assertIn(correct, range(4))
        for phrase in ("D", "la D", "opción d", "la cuarta"):
            self.assertEqual(webapp.match_option(phrase, ["uno", "dos", "tres", "cuatro"]), 3)


class JoinTests(unittest.IsolatedAsyncioTestCase):
    async def join(self, room, name="", mode=None):
        from fastapi import WebSocketDisconnect

        ws = FakeWS()

        async def receive():
            raise WebSocketDisconnect()

        ws.receive_text = receive
        code = "TEST"
        room["code"] = code
        webapp.rooms[code] = room
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "say", new=AsyncMock()), \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.sala_ws(ws, code, name=name)
        return ws, narr

    async def test_first_solo_player_starts_the_match(self):
        room = make_room(mode="solo", capacity=1)
        try:
            ws, narr = await self.join(room)
            welcome = [m for m in ws.messages if m["event"] == "welcome"]
            self.assertEqual(welcome[0]["name"], "Jugador 1")
            self.assertTrue(any("Arranca la partida" in c[0][1] for c in narr.await_args_list))
        finally:
            webapp.rooms.pop("TEST", None)

    async def test_joins_are_announced_by_name_with_the_headcount(self):
        room = make_room("Ana", capacity=5)
        try:
            _, narr = await self.join(room, name="Pepe")
            self.assertTrue(any("Se unió Pepe. Ahora son 2 en la sala." == c[0][1]
                                for c in narr.await_args_list))
        finally:
            webapp.rooms.pop("TEST", None)

    async def test_a_full_sala_joins_overflow_as_spectator(self):
        room = make_room("Ana", "Beto", capacity=2)
        room["phase"] = "spin_ready"
        try:
            ws, _ = await self.join(room, name="Pepe")
            self.assertIsNone(ws.closed)
            welcome = next(m for m in ws.messages if m["event"] == "welcome")
            self.assertTrue(welcome["spectator"])
            self.assertTrue(room["players"][-1]["spectator"])
            self.assertIsNot(webapp.current_player(room), room["players"][-1])
        finally:
            webapp.rooms.pop("TEST", None)

    async def test_a_sala_waits_for_the_host_to_pick_the_game(self):
        room = make_room("Ana", capacity=2)
        try:
            _, narr = await self.join(room, name="Beto")
            self.assertFalse(any("Arranca la partida" in c[0][1] for c in narr.await_args_list))
            # The host picks: now the match starts.
            room["game"] = "categorias"
            with patch.object(webapp, "narrate", new=AsyncMock()) as narr2, \
                 patch.object(webapp, "turn_clock", new=fake_clock):
                await webapp.start_match(room)
            self.assertTrue(any("Arranca la partida" in c[0][1] for c in narr2.await_args_list))
            self.assertEqual(room["phase"], "spin_ready")
        finally:
            webapp.rooms.pop("TEST", None)

    async def test_a_comeback_retakes_the_seat_and_keeps_points(self):
        room = make_room("Ana", "Beto", capacity=3)
        room["players"][1]["ws"] = None
        room["scores"][2] = 3
        try:
            ws, _ = await self.join(room, name="Beto")
            welcome = [m for m in ws.messages if m["event"] == "welcome"]
            self.assertEqual(welcome[0]["id"], 2)
            self.assertEqual(room["scores"][2], 3)
            self.assertEqual(len(room["players"]), 2)
        finally:
            webapp.rooms.pop("TEST", None)


class AudioRouteTests(unittest.TestCase):
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(webapp.router)
        return TestClient(app)

    def test_cached_audio_is_served_as_mp3(self):
        key = webapp.cache_audio(b"fake-mp3-bytes")
        res = self.client().get(f"/amor-con-aroma-a-cafe/audio/{key}.mp3")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, b"fake-mp3-bytes")
        self.assertEqual(res.headers["content-type"], "audio/mpeg")

    def test_unknown_audio_is_a_404(self):
        res = self.client().get("/amor-con-aroma-a-cafe/audio/nope123.mp3")
        self.assertEqual(res.status_code, 404)


class CrearSalaTests(unittest.TestCase):
    def create(self, payload):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(webapp.router)
        res = TestClient(app).post("/amor-con-aroma-a-cafe/api/salas", json=payload)
        self.assertEqual(res.status_code, 200)
        code = res.json()["code"]
        room = webapp.rooms.pop(code)
        return room

    def test_paises_modes_create_paises_games(self):
        for mode in ("solo_paises", "paises"):
            room = self.create({"mode": mode, "capacity": 3})
            self.assertEqual(room["game"], "paises")
            self.assertEqual(room["mode"], mode)
        self.assertEqual(self.create({"mode": "solo_paises"})["capacity"], 1)

    def test_category_modes_create_categorias_games(self):
        self.assertEqual(self.create({"mode": "solo"})["game"], "categorias")
        # a sala starts gameless: the host picks the game in the lobby
        self.assertIsNone(self.create({"mode": "sala", "capacity": 4})["game"])

    def test_ahorcado_modes_create_ahorcado_games(self):
        for mode in ("solo_ahorcado", "ahorcado"):
            room = self.create({"mode": mode, "capacity": 3})
            self.assertEqual(room["game"], "ahorcado")
        self.assertEqual(self.create({"mode": "solo_ahorcado"})["capacity"], 1)


class PageTests(unittest.TestCase):
    def test_start_screen_buttons_are_labeled(self):
        self.assertIn('aria-label="Jugar solo, sin amigos"', webapp.PAGE)
        self.assertIn('aria-label="Sala de juegos, para jugar con amigos"', webapp.PAGE)
        self.assertIn('aria-label="Ruleta de Países, para jugar con amigos"', webapp.PAGE)

    def test_capacity_picker_goes_from_2_to_20(self):
        self.assertIn("for (let n = 2; n <= 20; n++)", webapp.PAGE)

    def test_every_beat_is_announced_to_screen_readers(self):
        self.assertIn('role="status"', webapp.PAGE)
        self.assertIn('aria-live="assertive"', webapp.PAGE)
        self.assertIn('aria-live="polite"', webapp.PAGE)
        self.assertIn('role="timer"', webapp.PAGE)
        self.assertIn('lang="es"', webapp.PAGE)

    def test_ahorcado_is_offerend_and_labeled(self):
        self.assertIn('aria-label="El ahorcado, adivinar la palabra"', webapp.PAGE)
        self.assertIn('aria-label="Jugar al ahorcado"', webapp.PAGE)
        self.assertIn('aria-label="Decir una letra o la palabra por voz"', webapp.PAGE)
        self.assertIn('action: "juego", game: "ahorcado"', webapp.PAGE)
        self.assertIn('action: "guess"', webapp.PAGE)

    def test_options_have_distinct_high_contrast_colors(self):
        for idx, color in ((0, "#f9a825"), (1, "#00c853"), (2, "#29b6f6")):
            self.assertIn(f'.opcion[data-idx="{idx}"] {{ background: {color}; color: #000;', webapp.PAGE)

    def test_every_category_is_in_the_picker(self):
        for key, label in webapp.CATEGORIES.items():
            self.assertIn(f'"{label}|{key}"', webapp.PAGE)

    def test_wheel_is_decorative_and_the_button_is_the_control(self):
        self.assertIn('aria-hidden="true"></canvas>', webapp.PAGE)
        self.assertIn('id="btn-girar-text">Girar la ruleta</span>', webapp.PAGE)

    def test_nothing_steals_focus_or_navigates(self):
        self.assertNotIn("location.href", webapp.PAGE)
        self.assertIn("history.pushState", webapp.PAGE)
        self.assertNotIn("autofocus", webapp.PAGE)

    def test_he_keeps_his_name_across_visits(self):
        self.assertIn('localStorage.getItem("cafe_nombre")', webapp.PAGE)
        self.assertIn('localStorage.setItem("cafe_nombre", myName)', webapp.PAGE)
        self.assertIn("?name=", webapp.PAGE)

    def test_chat_text_and_voice_are_present_and_labeled(self):
        self.assertIn('aria-label="Mandar el mensaje de texto"', webapp.PAGE)
        self.assertIn('aria-label="Grabar una nota de voz"', webapp.PAGE)
        self.assertIn('aria-label="Destinatario del mensaje"', webapp.PAGE)
        self.assertIn("MediaRecorder", webapp.PAGE)

    def test_audio_is_queued_never_overlapping(self):
        self.assertIn("audioQueue", webapp.PAGE)
        self.assertIn("player.onended", webapp.PAGE)

    def test_audio_unlocks_on_tap_with_context_and_primed_element(self):
        self.assertIn("SILENT_MP3", webapp.PAGE)
        self.assertIn('ctx.state === "suspend', webapp.PAGE.replace("suspended", "suspend"))
        self.assertIn("audioCtx.resume()", webapp.PAGE)
        self.assertIn("audioQueue.unshift(item)", webapp.PAGE)


if __name__ == "__main__":
    unittest.main()


class BundleTests(unittest.IsolatedAsyncioTestCase):
    async def test_descripcion_speaks_game_summary_to_the_asker(self):
        from fastapi import WebSocketDisconnect
        room = make_room("Ana", capacity=5)
        room["code"] = "TEST"
        webapp.rooms["TEST"] = room
        try:
            ws = FakeWS()
            sent = [False]

            async def receive():
                if not sent[0]:
                    sent[0] = True
                    return json.dumps({"action": "descripcion", "game": "ahorcado"})
                raise WebSocketDisconnect()

            ws.receive_text = receive
            with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
                 patch.object(webapp, "say", new=AsyncMock()), \
                 patch.object(webapp, "turn_clock", new=fake_clock):
                await webapp.sala_ws(ws, "TEST", name="Pepe")
            calls = [c for c in narr.await_args_list if "ahorcado" in c[0][1].lower()]
            self.assertTrue(calls, narr.await_args_list)
            self.assertTrue(all(c.kwargs.get("to") is not None for c in calls))
        finally:
            webapp.rooms.pop("TEST", None)

    def test_empty_transcription_is_narrated_not_silent(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(webapp.router)
        room = make_room("Ana", capacity=5)
        room["code"] = "TESTV"
        room["phase"] = "question"
        webapp.rooms["TESTV"] = room
        try:
            with patch.object(webapp, "transcribe_clip", new=AsyncMock(return_value="")), \
                 patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
                 patch.object(webapp, "say", new=AsyncMock()):
                res = TestClient(app).post(
                    "/amor-con-aroma-a-cafe/api/voz-respuesta/TESTV?sender=" + str(room["players"][0]["id"]),
                    content=b"RIFF" + b"\x00" * 100)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json(), {"heard": False})
            self.assertTrue(any("No te escuché" in c[0][1] for c in narr.await_args_list),
                            narr.await_args_list)
        finally:
            webapp.rooms.pop("TESTV", None)


class VozTextoTests(unittest.IsolatedAsyncioTestCase):
    async def drive(self, room, text, narr, res):
        from fastapi import WebSocketDisconnect
        ws = FakeWS()
        sent = [False]

        async def receive():
            if not sent[0]:
                sent[0] = True
                room["phase"] = "question"
                room["question"] = {"category": "Capitales", "q": "¿Capital de Francia?",
                                    "options": ["Londres", "París", "Madrid"], "correct": 1}
                return json.dumps({"action": "voz-texto", "text": text})
            raise WebSocketDisconnect()

        ws.receive_text = receive
        room["code"] = "TESTV"
        webapp.rooms["TESTV"] = room
        try:
            with patch.object(webapp, "resolve_answer", res), \
                 patch.object(webapp, "narrate", narr), \
                 patch.object(webapp, "say", new=AsyncMock()), \
                 patch.object(webapp, "turn_clock", new=fake_clock):
                await webapp.sala_ws(ws, "TESTV", name="Ana")
        finally:
            webapp.rooms.pop("TESTV", None)

    async def test_ruleta_text_answer_is_matched_to_an_option(self):
        room = make_room(capacity=5)
        narr, res = AsyncMock(), AsyncMock()
        await self.drive(room, "París", narr, res)
        self.assertEqual(res.await_args_list[0][0][2], 1)

    async def test_unmatched_text_gets_a_spoken_retry_not_silence(self):
        room = make_room(capacity=5)
        narr, res = AsyncMock(), AsyncMock()
        await self.drive(room, "no lo sé", narr, res)
        res.assert_not_awaited()
        self.assertTrue(any("No te entendí" in c[0][1] for c in narr.await_args_list),
                        narr.await_args_list)


class BombaTests(unittest.IsolatedAsyncioTestCase):
    def make_bomba_room(self, *names):
        room = make_room(*names, mode="bomba" if len(names) > 1 else "solo_bomba",
                         capacity=max(1, len(names)))
        webapp.rooms["BBBB"] = room
        self.addCleanup(webapp.rooms.pop, "BBBB", None)
        return room

    async def start(self, room):
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "bb_fuse_clock", new=fake_clock):
            await webapp.start_match(room)
        return room["bomba"]

    async def test_match_opens_with_prompt_and_lives(self):
        room = self.make_bomba_room("Ana", "Beto")
        bb = await self.start(room)
        self.assertEqual(room["phase"], "bomba")
        self.assertIsNotNone(bb["prompt"])
        self.assertEqual(bb["lives"], {1: webapp.BOMBA_LIVES, 2: webapp.BOMBA_LIVES})
        self.assertTrue(0 < bb["fuse"] <= webapp.BOMBA_FUSE_MAX)

    async def test_valid_answer_passes_the_bomb(self):
        room = self.make_bomba_room("Ana", "Beto")
        bb = await self.start(room)
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "bb_fuse_clock", new=fake_clock), \
             patch.object(webapp, "judge_bomba", new=AsyncMock(return_value=True)):
            await webapp.bb_answer(room, room["players"][0], "cuchara")
        self.assertEqual(webapp.current_player(room)["name"], "Beto")
        self.assertIn("cuchara", bb["said"])

    async def test_invalid_answer_explodes_and_costs_a_life(self):
        room = self.make_bomba_room("Ana", "Beto")
        bb = await self.start(room)
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "bb_fuse_clock", new=fake_clock), \
             patch.object(webapp, "judge_bomba", new=AsyncMock(return_value=False)):
            await webapp.bb_answer(room, room["players"][0], "xyz no vale")
        self.assertEqual(bb["lives"][1], webapp.BOMBA_LIVES - 1)
        self.assertEqual(room["scores"][1], webapp.BOMBA_LIVES - 1)

    async def test_repeated_answer_is_rejected_without_explosion(self):
        room = self.make_bomba_room("Ana", "Beto")
        bb = await self.start(room)
        bb["said"].add("cuchara")
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "bb_fuse_clock", new=fake_clock):
            await webapp.bb_answer(room, room["players"][0], "¡Cuchara!")
        self.assertIn("ya la dijeron", narr.await_args_list[-1][0][1])
        self.assertEqual(bb["lives"][1], webapp.BOMBA_LIVES)
        self.assertEqual(webapp.current_player(room)["name"], "Ana")

    async def test_third_explosion_eliminates_and_last_standing_wins(self):
        room = self.make_bomba_room("Ana", "Beto")
        bb = await self.start(room)
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "bb_fuse_clock", new=fake_clock), \
             patch.object(webapp, "start_match", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()), \
             patch.object(webapp, "judge_bomba", new=AsyncMock(return_value=False)):
            for _ in range(webapp.BOMBA_LIVES):
                # Ana holds the bomb each time: after an explosion the turn passes,
                # so hand it back to her before the next invalid answer.
                room["turn"] = 0
                await webapp.bb_answer(room, room["players"][0], "no vale nada")
        self.assertTrue(room["players"][0].get("out"))
        self.assertEqual(room["phase"], "gameover")

    async def test_not_the_holder_cannot_answer(self):
        room = self.make_bomba_room("Ana", "Beto")
        bb = await self.start(room)
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "judge_bomba", new=AsyncMock(return_value=True)):
            await webapp.bb_answer(room, room["players"][1], "cuchara")
        narr.assert_not_called()
        self.assertEqual(bb["said"], set())

class MisterioTests(unittest.IsolatedAsyncioTestCase):
    def make_misterio_room(self, *names):
        room = make_room(*names, mode="misterio" if len(names) > 1 else "solo_misterio",
                         capacity=max(1, len(names)))
        webapp.rooms["MMMM"] = room
        self.addCleanup(webapp.rooms.pop, "MMMM", None)
        return room

    async def start(self, room):
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "mst_case_clock", new=fake_clock):
            await webapp.start_match(room)
        return room["misterio"]

    async def test_match_opens_with_a_case_and_lives(self):
        room = self.make_misterio_room("Ana", "Beto")
        mst = await self.start(room)
        self.assertEqual(room["phase"], "misterio")
        self.assertIsNotNone(mst["case"])
        self.assertEqual(mst["lives"], {1: webapp.MISTERIO_LIVES, 2: webapp.MISTERIO_LIVES})

    async def test_keyword_hit_solves_without_groq(self):
        room = self.make_misterio_room("Ana", "Beto")
        mst = await self.start(room)
        hit = mst["case"][3][0]
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "mst_case_clock", new=fake_clock):
            await webapp.mst_guess(room, room["players"][0], f"es lo del {hit}")
        self.assertEqual(mst["solved"][1], 1)
        self.assertEqual(room["scores"][1], 1)
        self.assertTrue(any("resolvió el misterio" in c[0][1]
                            for c in narr.await_args_list))

    async def test_cerca_costs_no_life(self):
        room = self.make_misterio_room("Ana", "Beto")
        mst = await self.start(room)
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "judge_misterio", new=AsyncMock(return_value="cerca")):
            await webapp.mst_guess(room, room["players"][0], "una teoría")
        self.assertIn("está cerca", narr.await_args_list[-1][0][1])
        self.assertEqual(mst["lives"][1], webapp.MISTERIO_LIVES)

    async def test_lejos_costs_a_life_and_three_strikes_eliminate(self):
        room = self.make_misterio_room("Ana", "Beto")
        mst = await self.start(room)
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "start_match", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()), \
             patch.object(webapp, "judge_misterio", new=AsyncMock(return_value="lejos")):
            for _ in range(webapp.MISTERIO_LIVES):
                await webapp.mst_guess(room, room["players"][0], "una teoría mala")
        self.assertTrue(room["players"][0].get("out"))
        self.assertEqual(room["phase"], "gameover")  # Beto is the last one standing

    async def test_solving_two_cases_wins_the_match(self):
        room = self.make_misterio_room("Ana", "Beto")
        mst = await self.start(room)
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "mst_case_clock", new=fake_clock), \
             patch.object(webapp, "start_match", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()), \
             patch.object(webapp, "judge_misterio", new=AsyncMock(return_value="acierto")):
            for _ in range(webapp.MISTERIO_TO_WIN):
                await webapp.mst_guess(room, room["players"][0], "la solución")
        self.assertEqual(room["phase"], "gameover")

class JudgeTests(unittest.TestCase):
    def test_norm_strips_accents_and_case(self):
        self.assertEqual(webapp.norm("¡Héladera, María!"), "heladera maria")

    def test_kw_hit_matches_whole_words(self):
        self.assertTrue(webapp.kw_hit("es un paracaídas", ["paracaidas"]))
        self.assertFalse(webapp.kw_hit("es un paracaidista", ["caida"]))


class TeamTests(unittest.IsolatedAsyncioTestCase):
    def test_team_turns_alternate_and_members_rotate(self):
        room = make_room("Roja 1", "Azul 1", "Roja 2", "Azul 2")
        room["team_count"] = 2
        for i, player in enumerate(room["players"]):
            player["team"] = i % 2
        order = []
        for turn in range(8):
            room["turn"] = turn
            order.append(webapp.current_player(room)["name"])
        self.assertEqual(order, ["Roja 1", "Azul 1", "Roja 2", "Azul 2"] * 2)

    async def test_quiz_progress_shared_between_teammates(self):
        room = make_room("Ana", "Beto", "Ceci", mode="solo")
        room["team_count"] = 2
        for player, team in zip(room["players"], (0,1,0)):
            player["team"] = team
        player = room["players"][0]
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "end_turn", new=AsyncMock()), \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.ask_question(room, player, "cultura")
            for _ in range(5):
                await webapp.resolve_answer(room, player, room["question"]["correct"])
        self.assertEqual(room["scores"][1],1)
        self.assertEqual(room["scores"][3],1)
        self.assertEqual(room["scores"][2],0)

    def test_surviving_team_wins_with_two_members(self):
        room = make_room("Ana", "Beto", "Ceci")
        room["team_count"] = 2
        for player, team in zip(room["players"], (0,1,0)):
            player["team"] = team
        alive = [room["players"][0], room["players"][2]]
        self.assertIs(webapp.survivor_winner(room, alive),alive[0])

    async def test_explicit_spectator_cannot_answer(self):
        from fastapi import WebSocketDisconnect
        room = make_room("Ana", capacity=5)
        room["code"] = "WATCH"
        room["phase"] = "misterio"
        webapp.rooms["WATCH"] = room
        ws = FakeWS(); calls = [0]
        async def receive():
            calls[0] += 1
            if calls[0] == 1:
                return json.dumps({"action":"guess", "text":"una teoría"})
            raise WebSocketDisconnect()
        ws.receive_text = receive
        try:
            with patch.object(webapp, "narrate",new=AsyncMock()), \
                 patch.object(webapp, "mst_guess",new=AsyncMock()) as guess:
                await webapp.sala_ws(ws,"WATCH",name="Mirón",spectator=True)
            guess.assert_not_awaited()
        finally:
            webapp.rooms.pop("WATCH",None)


class TeamConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_host_configures_teams_then_picks_team(self):
        from fastapi import WebSocketDisconnect
        room = make_room(capacity=5)
        room["code"] = "TEAMS"
        webapp.rooms["TEAMS"] = room
        ws = FakeWS()
        messages = iter([{"action":"equipos", "count":3}, {"action":"equipo", "team":2}])
        async def receive():
            try:
                return json.dumps(next(messages))
            except StopIteration:
                raise WebSocketDisconnect()
        ws.receive_text = receive
        try:
            with patch.object(webapp,"narrate",new=AsyncMock()), patch.object(webapp,"say",new=AsyncMock()):
                await webapp.sala_ws(ws,"TEAMS",name="Host")
            self.assertEqual(room["team_count"],3)
            self.assertEqual(room["players"][0]["team"],2)
        finally:
            webapp.rooms.pop("TEAMS",None)

    def test_first_spectator_does_not_become_host(self):
        room = make_room("Observer", "Host")
        room["players"][0]["spectator"] = True
        self.assertIs(webapp.host_player(room),room["players"][1])


class FiveQuestionPlumbingTests(unittest.TestCase):
    def test_four_lives_and_loss_per_wrong_answer(self):
        room = make_room("Ana")
        player = room["players"][0]
        webapp.new_quiz_run(room, player, "cultura")
        self.assertEqual(webapp.quiz_lives(room, player), 4)
        webapp.record_quiz_answer(room, player, False)
        self.assertEqual(webapp.quiz_lives(room, player), 3)
        self.assertEqual(room["quiz_run"]["mistakes"],1)

    def test_five_clean_answers_gift_one_life_once(self):
        room = make_room("Ana")
        player = room["players"][0]
        webapp.new_quiz_run(room, player, "cultura")
        for _ in range(5):
            webapp.record_quiz_answer(room, player, True)
        self.assertTrue(webapp.quiz_bonus(room,player))
        self.assertEqual(webapp.quiz_lives(room,player),4)
        self.assertFalse(webapp.quiz_bonus(room,player))
        self.assertEqual(webapp.quiz_lives(room,player),4)

    def test_mistake_blocks_bonus_and_lives_remain_personal_in_teams(self):
        room = make_room("Ana","Beto")
        room["team_count"]=2
        for player in room["players"]:
            player["team"]=0
        a,b=room["players"]
        webapp.new_quiz_run(room,a,"cultura")
        webapp.record_quiz_answer(room,a,False)
        for _ in range(5):
            webapp.record_quiz_answer(room,a,True)
        self.assertTrue(webapp.quiz_bonus(room,a))
        self.assertEqual(webapp.quiz_lives(room,a),4)
        self.assertEqual(webapp.quiz_lives(room,b),4)


class FinalRunRulesTests(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_then_five_correct_streak_recovers_life(self):
        room = make_room("Ana", "Beto", mode="solo")
        player=room["players"][0]
        with patch.object(webapp,"narrate",new=AsyncMock()) as narr, \
             patch.object(webapp,"end_turn",new=AsyncMock()), \
             patch.object(webapp,"turn_clock",new=fake_clock):
            await webapp.ask_question(room,player,"cultura")
            await webapp.resolve_answer(room,player,(room["question"]["correct"]+1)%4)
            self.assertEqual(webapp.quiz_lives(room,player),3)
            self.assertEqual(room["quiz_run"]["answered"],1)
            for _ in range(5):
                await webapp.resolve_answer(room,player,room["question"]["correct"])
        self.assertEqual(webapp.quiz_lives(room,player),4)
        self.assertEqual(room["quiz_run"]["answered"],6)
        self.assertEqual(room["scores"][player["id"]],1)
        self.assertTrue(any("Cinco correctas seguidas" in c.args[1] for c in narr.await_args_list))

    async def test_nonconsecutive_five_pass_without_bonus(self):
        room = make_room("Ana", "Beto", mode="solo")
        player=room["players"][0]
        with patch.object(webapp,"narrate",new=AsyncMock()), \
             patch.object(webapp,"end_turn",new=AsyncMock()), \
             patch.object(webapp,"turn_clock",new=fake_clock):
            await webapp.ask_question(room,player,"cultura")
            for correct in [True,False,True,True,True,True]:
                idx=room["question"]["correct"]
                await webapp.resolve_answer(room,player,idx if correct else (idx+1)%4)
        self.assertEqual(webapp.quiz_lives(room,player),3)
        self.assertEqual(room["scores"][player["id"]],1)

    async def test_zero_lives_restarts_player_in_room(self):
        room=make_room("Ana","Beto",mode="solo")
        player=room["players"][0]
        room["cat_progress"]={1:{"cultura":5}}
        room["scores"][1]=1
        with patch.object(webapp,"narrate",new=AsyncMock()), \
             patch.object(webapp,"begin_turn",new=AsyncMock()) as restart, \
             patch.object(webapp,"turn_clock",new=fake_clock):
            await webapp.ask_question(room,player,"historia")
            for _ in range(4):
                await webapp.resolve_answer(room,player,(room["question"]["correct"]+1)%4)
        restart.assert_awaited_once()
        self.assertFalse(player.get("out",False))
        self.assertEqual(webapp.quiz_lives(room,player),4)
        self.assertEqual(room["scores"][1],0)
        self.assertNotIn(1,room["cat_progress"])

    async def test_no_ten_attempt_ceiling(self):
        room=make_room("Ana",mode="solo")
        player=room["players"][0]
        with patch.object(webapp,"narrate",new=AsyncMock()), \
             patch.object(webapp,"end_turn",new=AsyncMock()) as end, \
             patch.object(webapp,"turn_clock",new=fake_clock):
            await webapp.ask_question(room,player,"cultura")
            room["quiz_run"].update(answered=10,correct=3,mistakes=7,streak=0)
            await webapp.resolve_answer(room,player,room["question"]["correct"])
        end.assert_not_awaited()
        self.assertEqual(room["phase"],"question")
        self.assertEqual(room["quiz_run"]["correct"],4)

    async def test_team_zero_lives_keeps_shared_progress(self):
        room=make_room("Ana","Beto","Ceci",mode="solo")
        room["team_count"]=2
        for p,t in zip(room["players"],(0,1,0)):
            p["team"]=t
        player=room["players"][0]
        room["cat_progress"]={"equipo:0":{"cultura":5}}
        webapp.sync_score(room,player,1)
        with patch.object(webapp,"narrate",new=AsyncMock()), \
             patch.object(webapp,"begin_turn",new=AsyncMock()), \
             patch.object(webapp,"turn_clock",new=fake_clock):
            await webapp.ask_question(room,player,"historia")
            room["quiz_lives"][1]=1
            await webapp.resolve_answer(room,player,(room["question"]["correct"]+1)%4)
        self.assertEqual(room["scores"][1],1)
        self.assertEqual(room["scores"][3],1)
        self.assertEqual(room["cat_progress"]["equipo:0"]["cultura"],5)
        self.assertEqual(webapp.quiz_lives(room,player),4)

    async def test_zero_lives_solo_restarts_without_elimination(self):
        room=make_room("Ana",mode="solo",capacity=1)
        player=room["players"][0]
        with patch.object(webapp,"narrate",new=AsyncMock()), \
             patch.object(webapp,"begin_turn",new=AsyncMock()) as restart, \
             patch.object(webapp,"turn_clock",new=fake_clock):
            await webapp.ask_question(room,player,"cultura")
            room["quiz_lives"][1]=1
            await webapp.resolve_answer(room,player,(room["question"]["correct"]+1)%4)
        restart.assert_awaited_once()
        self.assertFalse(player.get("out",False))
        self.assertEqual(webapp.quiz_lives(room,player),4)


class RunTimerTests(unittest.IsolatedAsyncioTestCase):
    async def test_question_timeout_is_one_missed_answer(self):
        room=make_room("Ana","Beto",mode="solo")
        room["phase"]="question"
        room["question"]={"category":"cultura","options":["a","b","c","d"],"correct":2}
        with patch("asyncio.sleep",new=AsyncMock()), \
             patch.object(webapp,"turn_chatter",new=AsyncMock()), \
             patch.object(webapp,"narrate",new=AsyncMock()), \
             patch.object(webapp,"resolve_answer",new=AsyncMock()) as resolve, \
             patch.object(webapp,"begin_turn",new=AsyncMock()) as turn:
            await webapp.turn_clock(room,1)
        resolve.assert_awaited_once_with(room,room["players"][0],-1)
        turn.assert_not_awaited()

    async def test_duplicate_answer_is_ignored_during_narration(self):
        room=make_room("Ana",mode="solo")
        player=room["players"][0]
        room["phase"]="question"
        room["question"]={"category":"cultura","options":["a","b","c","d"],"correct":2}
        webapp.new_quiz_run(room,player,"cultura")
        entered=asyncio.Event();release=asyncio.Event()
        async def narrate(*args,**kwargs):
            entered.set()
            await release.wait()
        with patch.object(webapp,"narrate",side_effect=narrate), \
             patch.object(webapp,"ask_question",new=AsyncMock()):
            first=asyncio.create_task(webapp.resolve_answer(room,player,2))
            await entered.wait()
            await webapp.resolve_answer(room,player,2)
            release.set()
            await first
        self.assertEqual(room["quiz_run"]["correct"],1)

    def test_life_total_persists_between_categories(self):
        room=make_room("Ana")
        player=room["players"][0]
        webapp.new_quiz_run(room,player,"cultura")
        webapp.record_quiz_answer(room,player,False)
        webapp.new_quiz_run(room,player,"historia")
        self.assertEqual(webapp.quiz_lives(room,player),3)
        self.assertEqual(room["quiz_run"]["answered"],0)


class SpokenOptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_options_read_text_only(self):
        room=make_room("Ana",mode="solo")
        with patch.object(webapp,"narrate",new=AsyncMock()) as narr, \
             patch.object(webapp,"turn_clock",new=fake_clock):
            await webapp.ask_question(room,room["players"][0],"cultura")
        text=narr.await_args_list[0].args[1]
        for opt in room["question"]["options"]:
            self.assertIn(opt,text)
        for letter in "ABCD":
            self.assertNotIn("Opción "+letter+":",text)
        self.assertNotIn("de 10",text)
        self.assertIn("4 vidas",text)

class VoiceDeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def test_remote_timeout_uses_local_spanish(self):
        async def timeout_voice(*args):
            raise asyncio.TimeoutError()
        with patch('app.synthesize', side_effect=timeout_voice), \
             patch('app.synthesize_once', new=AsyncMock(return_value=b'ogg')) as local, \
             patch.object(webapp, 'ogg_to_mp3', new=AsyncMock(return_value=b'mp3')):
            self.assertEqual(await webapp.bounded_voice_mp3('Hola', 'es-AR-ElenaNeural'), b'mp3')
            local.assert_awaited_once_with('Hola', 'espeak-es-419')

    async def test_double_failure_still_sends_text(self):
        room = make_room('Ana')
        with patch.object(webapp, 'bounded_voice_mp3', new=AsyncMock(side_effect=RuntimeError('voice unavailable'))), \
             patch.object(webapp, 'broadcast', new=AsyncMock()) as broadcast:
            await webapp.narrate(room, 'Tu turno, Ana')
            self.assertFalse(room['audio_lock'].locked())
            self.assertEqual(broadcast.call_args.args[1], {'event':'say','text':'Tu turno, Ana','audio':None})

    async def test_failed_chatter_releases_lock_without_queue(self):
        room = make_room('Ana')
        with patch('app.synthesize', new=AsyncMock(side_effect=asyncio.TimeoutError())), \
             patch.object(webapp, 'broadcast', new=AsyncMock()) as broadcast:
            await webapp.turn_chatter(room, room['players'][0])
            self.assertFalse(room['audio_lock'].locked())
            broadcast.assert_not_awaited()

class QuestionDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_and_options_arrive_before_speech_and_clock(self):
        room = make_room('Ana', mode='solo_paises', capacity=1)
        p = room['players'][0]
        sent = []
        async def broadcast(room, msg): sent.append(msg.copy())
        async def narrate(*args, **kw):
            self.assertTrue(any(m.get('event')=='question' for m in sent))
            self.assertIsNone(room['timer_task'])
            self.assertFalse(room['question']['clock_started'])
        with patch.object(webapp, 'broadcast', side_effect=broadcast), \
             patch.object(webapp, 'narrate', side_effect=narrate):
            await webapp.ask_question(room, p, 'cultura')
        self.assertEqual(len(sent[0]['options']), 4)
        self.assertNotIn('correct', webapp.public_question(room))
        self.assertEqual(webapp.room_state(room)['question']['q'], room['question']['q'])

    async def test_only_owner_and_current_question_can_start_clock_once(self):
        room = make_room('Ana', 'Beto', mode='solo')
        with patch.object(webapp, 'narrate', new=AsyncMock()), \
             patch.object(webapp, 'turn_clock', new=fake_clock), \
             patch.object(webapp, 'broadcast', new=AsyncMock()) as b:
            await webapp.ask_question(room, room['players'][0], 'cultura')
            qid = room['question']['id']
            await webapp.start_question_clock(room, room['players'][1], qid)
            await webapp.start_question_clock(room, room['players'][0], qid-1)
            self.assertIsNone(room['timer_task'])
            await webapp.start_question_clock(room, room['players'][0], qid)
            timer = room['timer_task']
            await webapp.start_question_clock(room, room['players'][0], qid)
            self.assertIs(timer, room['timer_task'])
            self.assertTrue(room['question']['clock_started'])
            webapp.cancel_timer(room)

    async def test_spin_cancels_previous_clock_before_animation(self):
        room = make_room('Ana', mode='solo_paises', capacity=1)
        seen = []
        original = webapp.cancel_timer
        def cancel(r): seen.append('cancel'); original(r)
        async def sleep(n): self.assertEqual(seen[0], 'cancel')
        with patch.object(webapp, 'cancel_timer', side_effect=cancel), \
             patch.object(webapp.asyncio, 'sleep', side_effect=sleep), \
             patch.object(webapp, 'narrate', new=AsyncMock()):
            await webapp.do_country_spin(room, room['players'][0])
        self.assertEqual(room['phase'], 'spin_ready')

    def test_client_restores_question_and_requires_ready_for_clock(self):
        self.assertIn('onQuestion(msg.question)', webapp.PAGE)
        self.assertIn('lastQuestion = null;', webapp.PAGE)
        self.assertIn('action:"question-ready"', webapp.PAGE)
        self.assertIn('Repetir pregunta', webapp.PAGE)

class SeatReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_browser_key_reclaims_live_seat_and_pauses_clock(self):
        from fastapi import WebSocketDisconnect
        room = make_room('Ana', mode='solo_paises', capacity=1)
        old = FakeWS();room['players'][0]['ws']=old
        room['players'][0]['seat_key']='browser-test-key'
        room['phase']='question'
        room['question']={'id':1,'q':'¿Capital?','category':'cultura','options':['a','b','c','d'],
                          'correct':1,'clock_started':True,'audio':'/audio/test.mp3','audio_ready':True}
        ws=FakeWS()
        async def receive():raise WebSocketDisconnect()
        ws.receive_text=receive;webapp.rooms['SEAT']=room
        try:
            with patch.object(webapp,'narrate',new=AsyncMock()):
                await webapp.sala_ws(ws,'SEAT',name='Ana',seat_key='browser-test-key')
            welcome=next(m for m in ws.messages if m['event']=='welcome')
            self.assertEqual(welcome['id'],1)
            self.assertFalse(welcome['spectator'])
            self.assertEqual(len(room['players']),1)
            self.assertEqual(old.closed,4001)
            self.assertFalse(room['question']['clock_started'])
            self.assertTrue(any(m['event']=='question' for m in ws.messages))
            self.assertTrue(any(m['event']=='say' and m.get('question_id')==1 for m in ws.messages))
        finally:
            for task in room.get('disconnect_tasks',{}).values():task.cancel()
            webapp.rooms.pop('SEAT',None)

    def test_browser_retains_room_specific_key(self):
        self.assertIn('sessionStorage.getItem(seatStorage)', webapp.PAGE)
        self.assertIn('&seat_key=', webapp.PAGE)
