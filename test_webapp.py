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


if __name__ == "__main__":
    unittest.main()
