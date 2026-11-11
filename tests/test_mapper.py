import unittest
from evdev import ecodes as e
from mimictype.core.mapper import LayoutMapper


class TestLayoutMapper(unittest.TestCase):

    def setUp(self):
        self.mapper = LayoutMapper(default_layout="us")

    def test_us_characters(self):
        # 'a' unshifted
        res = self.mapper.resolve("a")
        self.assertIsNotNone(res)
        binding, need_switch = res
        self.assertEqual(binding.code, e.KEY_A)
        self.assertFalse(binding.shift)
        self.assertFalse(need_switch)

        # 'A' shifted
        res = self.mapper.resolve("A")
        self.assertIsNotNone(res)
        binding, need_switch = res
        self.assertEqual(binding.code, e.KEY_A)
        self.assertTrue(binding.shift)
        self.assertFalse(need_switch)

    def test_ru_characters_trigger_layout_switch(self):
        res = self.mapper.resolve("ф")
        self.assertIsNotNone(res)
        binding, need_switch = res
        self.assertEqual(binding.code, e.KEY_A)
        self.assertEqual(binding.layout, "ru")
        self.assertTrue(need_switch)  # Needs switch because current is US

    def test_common_whitespace(self):
        for space_char in (" ", "\n", "\t"):
            res = self.mapper.resolve(space_char)
            self.assertIsNotNone(res)


if __name__ == "__main__":
    unittest.main()
