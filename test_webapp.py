import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

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
        "used_retos": set(), "used_verdades": set(), "used_trivia": set(),
        "used_refranes": set(), "used_paises": set(),
        "voice": "es-AR-ElenaNeural", "question_voice": "es-UY-ValentinaNeural",
    }
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
        self.assertEqual(webapp.MAX_PLAYERS, 20)


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


class QuestionTests(unittest.IsolatedAsyncioTestCase):
    async def ask(self, room, cat="trivia"):
        player = webapp.current_player(room)
        room["phase"] = "category"
        with patch.object(webapp, "narrate", new=AsyncMock()):
            await webapp.ask_question(room, player, cat)
        return player

    async def test_question_broadcasts_options(self):
        room = make_room("Ana", "Beto")
        player = await self.ask(room)
        qs = [m for m in room["players"][1]["ws"].messages if m["event"] == "question"]
        self.assertEqual(len(qs), 1)
        self.assertEqual(len(qs[0]["options"]), 3)
        self.assertEqual(qs[0]["player"], player["id"])
        self.assertEqual(room["phase"], "question")

    async def test_mc_cards_do_not_repeat_until_exhausted(self):
        room = make_room("Ana")
        one = webapp.pick_mc(room, "trivia")
        two = webapp.pick_mc(room, "trivia")
        self.assertNotEqual(one[0], two[0])

    async def test_correct_answer_scores_and_passes_the_turn(self):
        room = make_room("Ana", "Beto")
        player = await self.ask(room)
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.resolve_answer(room, player, room["question"]["correct"])
        self.assertEqual(room["scores"][player["id"]], 1)
        self.assertEqual(webapp.current_player(room)["name"], "Beto")

    async def test_wrong_answer_says_the_right_one_and_scores_nothing(self):
        room = make_room("Ana", "Beto")
        player = await self.ask(room)
        wrong = (room["question"]["correct"] + 1) % 3
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "turn_clock", new=fake_clock):
            await webapp.resolve_answer(room, player, wrong)
        self.assertEqual(room["scores"][player["id"]], 0)
        self.assertIn("La correcta era", narr.await_args_list[0][0][1])


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
        room = make_room("Ana", "Beto")
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
    async def test_timeout_warns_twice_and_passes_the_turn(self):
        room = make_room("Ana", "Beto")
        room["phase"] = "category"
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr, \
             patch.object(webapp, "begin_turn", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.turn_clock(room, 1)
        self.assertEqual(room["turn"], 1)
        texts = [c[0][1] for c in narr.await_args_list]
        self.assertTrue(any("30 segundos" in t for t in texts))
        self.assertTrue(any("10 segundos" in t for t in texts))
        self.assertTrue(any("Se acabó el tiempo" in t for t in texts))


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

    async def test_a_full_sala_turns_people_away(self):
        room = make_room("Ana", "Beto", capacity=2)
        room["phase"] = "category"
        try:
            ws, _ = await self.join(room, name="Pepe")
            self.assertEqual(ws.closed, 4009)
            self.assertIn("llena", says(ws)[0]["text"])
        finally:
            webapp.rooms.pop("TEST", None)

    async def test_a_sala_starts_when_it_fills(self):
        room = make_room("Ana", capacity=2)
        try:
            _, narr = await self.join(room, name="Beto")
            self.assertTrue(any("Arranca la partida" in c[0][1] for c in narr.await_args_list))
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


class PageTests(unittest.TestCase):
    def test_start_screen_buttons_are_labeled(self):
        self.assertIn('aria-label="Jugar solo, sin amigos"', webapp.PAGE)
        self.assertIn('aria-label="Sala de juego, para jugar con amigos"', webapp.PAGE)

    def test_capacity_picker_goes_from_2_to_20(self):
        self.assertIn("for (let n = 2; n <= 20; n++)", webapp.PAGE)

    def test_every_beat_is_announced_to_screen_readers(self):
        self.assertIn('role="status"', webapp.PAGE)
        self.assertIn('aria-live="assertive"', webapp.PAGE)
        self.assertIn('aria-live="polite"', webapp.PAGE)
        self.assertIn('role="timer"', webapp.PAGE)
        self.assertIn('lang="es"', webapp.PAGE)

    def test_four_category_buttons(self):
        for cat in ("Verdad o Reto", "Trivia", "Refranes", "Países"):
            self.assertIn(f">Categoría {cat}<".replace(">Categoría", 'aria-label="Categoría').replace("<", '"'), webapp.PAGE)

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


if __name__ == "__main__":
    unittest.main()
