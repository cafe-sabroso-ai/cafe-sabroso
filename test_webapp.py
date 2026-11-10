import json
import unittest
from unittest.mock import AsyncMock, patch

import webapp


class FakeWS:
    def __init__(self):
        self.messages = []

    async def send_text(self, data):
        self.messages.append(json.loads(data))


def fresh_room(*names):
    room = {
        "code": "TEST",
        "players": [{"name": name, "ws": FakeWS()} for name in names],
        "turn": 0,
        "spinning": False,
        "used_retos": set(),
        "used_verdades": set(),
    }
    return room


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

    def test_room_state_reports_the_turn(self):
        room = fresh_room("Ana", "Beto")
        self.assertEqual(webapp.room_state(room)["turn"], "Ana")
        room["turn"] += 1
        self.assertEqual(webapp.room_state(room)["turn"], "Beto")
        room["turn"] += 1
        self.assertEqual(webapp.room_state(room)["turn"], "Ana")  # wraps around


class SpinTests(unittest.IsolatedAsyncioTestCase):
    async def spin(self, room, player="Ana"):
        with patch.object(webapp, "narrate", new=AsyncMock()), \
             patch("asyncio.sleep", new=AsyncMock()):
            await webapp.do_spin(room, player)

    async def test_spin_broadcasts_and_advances_the_turn(self):
        room = fresh_room("Ana", "Beto")
        await self.spin(room)
        self.assertEqual(room["turn"], 1)
        self.assertFalse(room["spinning"])
        starts = [m for m in room["players"][0]["ws"].messages if m["event"] == "spin_start"]
        self.assertEqual(len(starts), 1)
        # Both players saw the same spin.
        self.assertIn(starts[0], room["players"][1]["ws"].messages)
        state = [m for m in room["players"][0]["ws"].messages if m["event"] == "state"][-1]
        self.assertEqual(state["turn"], "Beto")

    async def test_cards_do_not_repeat_until_the_bank_runs_out(self):
        room = fresh_room("Ana")
        with patch.object(webapp, "SEGMENTS", ("reto",)), \
             patch.object(webapp, "RETOS", ["reto uno", "reto dos"]):
            await self.spin(room)
            await self.spin(room)
            self.assertEqual(room["used_retos"], {"reto uno", "reto dos"})
            await self.spin(room)  # bank exhausted: resets and deals again
            self.assertEqual(len(room["used_retos"]), 1)


class PageAccessibilityTests(unittest.TestCase):
    def test_page_has_no_text_inputs(self):
        # A keyboard must never pop up: nothing editable on the page.
        self.assertNotIn("<input", webapp.PAGE)
        self.assertNotIn("contenteditable", webapp.PAGE)

    def test_page_announces_status_to_screen_readers(self):
        self.assertIn('role="status"', webapp.PAGE)
        self.assertIn('aria-live="assertive"', webapp.PAGE)
        self.assertIn('lang="es"', webapp.PAGE)

    def test_creating_a_room_does_not_navigate(self):
        # A full navigation can drop focus into the browser chrome (keyboard).
        self.assertNotIn("location.href", webapp.PAGE)
        self.assertIn("history.pushState", webapp.PAGE)

    def test_every_button_has_discernible_text(self):
        self.assertIn("Crear una mesa nueva", webapp.PAGE)
        self.assertIn("Entrar a jugar", webapp.PAGE)
        self.assertIn("Copiar el link", webapp.PAGE)
        self.assertIn("Girar la ruleta", webapp.PAGE)

    def test_wheel_is_decorative_and_the_button_is_the_control(self):
        # El canvas no es un control: el botón real y etiquetado es lo que gira.
        self.assertIn('<canvas id="wheel" width="640" height="640" aria-hidden="true">', webapp.PAGE)
        self.assertNotIn('role="img"', webapp.PAGE)
        self.assertIn('id="btn-girar-text">Girar la ruleta</span>', webapp.PAGE)

    def test_emojis_never_reach_the_accessible_name(self):
        # Voice Access / lectores: el nombre accesible es solo texto.
        for emoji in ("☕", "💗", "📤", "🎡"):
            self.assertIn(f'<span aria-hidden="true">{emoji} </span>', webapp.PAGE)

    def test_he_keeps_his_name_across_visits(self):
        self.assertIn('localStorage.getItem("cafe_nombre")', webapp.PAGE)
        self.assertIn('localStorage.setItem("cafe_nombre", myName)', webapp.PAGE)
        self.assertIn("?name=" , webapp.PAGE)

    def test_welcome_announces_room_and_name(self):
        self.assertIn('"Estás en la mesa " + codeSpelled + " como "', webapp.PAGE)


class JoinGuidanceTests(unittest.IsolatedAsyncioTestCase):
    async def join(self, room, name=""):
        from fastapi import WebSocketDisconnect

        ws = FakeWS()
        ws.accept = AsyncMock()

        async def receive():
            raise WebSocketDisconnect()

        ws.receive_text = receive
        code = room["code"]
        webapp.rooms[code] = room
        with patch.object(webapp, "narrate", new=AsyncMock()) as narr:
            await webapp.sala_ws(ws, code, name=name)
        return ws, narr

    async def test_first_player_hears_spoken_guidance(self):
        room = fresh_room()
        try:
            ws, narr = await self.join(room)
            welcome = [m for m in ws.messages if m["event"] == "welcome"]
            self.assertEqual(welcome[0]["name"], "Jugador 1")  # auto-assigned
            self.assertIn("Ya estás en la mesa", narr.await_args_list[0][0][1])
            self.assertIn("Girar la ruleta", narr.await_args_list[0][0][1])
        finally:
            webapp.rooms.pop("TEST", None)

    async def test_second_player_gets_the_plain_join_narration(self):
        room = fresh_room("Ana")
        try:
            _, narr = await self.join(room)
            first = narr.await_args_list[0][0][1]
            self.assertIn("se sumó a la mesa", first)
            self.assertNotIn("Copiar el link", first)
        finally:
            webapp.rooms.pop("TEST", None)


if __name__ == "__main__":
    unittest.main()
