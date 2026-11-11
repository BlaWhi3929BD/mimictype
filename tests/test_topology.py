import unittest
from mimictype.core.topology import KeyboardTopology


class TestKeyboardTopology(unittest.TestCase):

    def setUp(self):
        self.topology = KeyboardTopology()

    def test_key_info_us(self):
        info_f = self.topology.get_info("f")
        self.assertIsNotNone(info_f)
        row, col, is_left, finger, layout = info_f
        self.assertEqual(row, 2)
        self.assertTrue(is_left)
        self.assertEqual(finger, 4)  # Index finger
        self.assertEqual(layout, "us")

    def test_key_info_ru(self):
        info_a = self.topology.get_info("а")  # Russian 'а'
        self.assertIsNotNone(info_a)
        row, col, is_left, finger, layout = info_a
        self.assertEqual(row, 2)
        self.assertTrue(is_left)
        self.assertEqual(layout, "ru")

    def test_adjacent_keys(self):
        adj_k = self.topology.get_adjacent_keys("k")
        self.assertIn("j", adj_k)
        self.assertIn("l", adj_k)
        self.assertIn("i", adj_k)

    def test_hand_alternation(self):
        # 'f' is left hand, 'j' is right hand
        self.assertFalse(self.topology.is_same_hand("f", "j"))
        # 'f' and 'd' are both left hand
        self.assertTrue(self.topology.is_same_hand("f", "d"))

    def test_distances(self):
        dist_near = self.topology.get_distance("f", "d")
        dist_far = self.topology.get_distance("q", "p")
        self.assertLess(dist_near, dist_far)


if __name__ == "__main__":
    unittest.main()
