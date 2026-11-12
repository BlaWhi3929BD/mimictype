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
            self.assertGreaterEqual(dwell, self.dynamics.min_dwell)
            self.assertLessEqual(dwell, self.dynamics.max_dwell)

    def test_wpm_scaling(self):
        config_slow = MimicConfig(wpm=65)
        config_fast = MimicConfig(wpm=333)

        dyn_slow = DynamicsEngine(config_slow)
        dyn_fast = DynamicsEngine(config_fast)

        dwell_slow = dyn_slow.compute_dwell_time("a")
        dwell_fast = dyn_fast.compute_dwell_time("a")

        flight_slow = dyn_slow.compute_flight_time("a", "b")
        flight_fast = dyn_fast.compute_flight_time("a", "b")

        self.assertLess(dwell_fast, dwell_slow)
        self.assertLess(flight_fast, flight_slow)

    def test_flight_time_alternate_hand(self):
        # 't' and 'h' are alternate hands -> faster than double letters
        flight_alt = self.dynamics.compute_flight_time("t", "h")
        flight_double = self.dynamics.compute_flight_time("l", "l")
        self.assertGreater(flight_alt, 0.005)
        self.assertGreater(flight_double, 0.005)

    def test_cognitive_pauses(self):
        pause_dot = self.dynamics.compute_cognitive_pause(
            "t", ".", peek_ahead=" "
        )
        pause_letter = self.dynamics.compute_cognitive_pause("a", "b")
        self.assertGreater(pause_dot, 0.1)
        self.assertEqual(pause_letter, 0.0)


if __name__ == "__main__":
    unittest.main()
