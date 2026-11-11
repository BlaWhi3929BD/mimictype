import unittest
from mimictype.config import MimicConfig
from mimictype.core.dynamics import DynamicsEngine


class TestDynamicsEngine(unittest.TestCase):

    def setUp(self):
        self.config = MimicConfig()
        self.dynamics = DynamicsEngine(self.config)

    def test_dwell_time_bounds(self):
        for _ in range(100):
            dwell = self.dynamics.compute_dwell_time("a")
            self.assertGreaterEqual(dwell, self.config.dwell.min_seconds)
            self.assertLessEqual(dwell, self.config.dwell.max_seconds)

    def test_flight_time_alternate_hand(self):
        # 't' and 'h' are alternate hands -> faster than double letters
        flight_alt = self.dynamics.compute_flight_time("t", "h")
        flight_double = self.dynamics.compute_flight_time("l", "l")
        self.assertGreater(flight_alt, 0.02)
        self.assertGreater(flight_double, 0.02)

    def test_cognitive_pauses(self):
        pause_dot = self.dynamics.compute_cognitive_pause(
            "t", ".", peek_ahead=" "
        )
        pause_letter = self.dynamics.compute_cognitive_pause("a", "b")
        self.assertGreater(pause_dot, 0.2)
        self.assertEqual(pause_letter, 0.0)


if __name__ == "__main__":
    unittest.main()
