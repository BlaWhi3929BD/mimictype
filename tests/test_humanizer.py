import random
import unittest
from mimictype.config import MimicConfig
from mimictype.core.humanizer import ActionType, HumanizerEngine
from mimictype.core.mapper import LayoutMapper


class TestHumanizerEngine(unittest.TestCase):

    def test_disabled_humanizer(self):
        config = MimicConfig()
        config.humanizer.enabled = False
        engine = HumanizerEngine(config)

        text = "Hello world"
        steps = list(engine.generate_steps(text))
        chars = [s.char for s in steps if s.action == ActionType.TYPE_CHAR]
        self.assertEqual("".join(chars), text)

    def test_typo_correction_balance(self):
        # Force high error rate to test typo generation and Backspace sequence
        config = MimicConfig()
        config.humanizer.enabled = True
        config.humanizer.error_rate = 1.0  # Every eligible character triggers a typo
        config.humanizer.transposition_rate = 0.0  # Test fat-finger specifically
        config.humanizer.inertia_range = (1, 1)  # Exactly 1 inertia character
        engine = HumanizerEngine(config)

        text = "test"
        steps = list(engine.generate_steps(text))

        # Check that backspace steps were yielded
        backspaces = [s for s in steps if s.action == ActionType.BACKSPACE]
        self.assertGreater(len(backspaces), 0)

    def test_no_text_corruption_with_unsupported_chars_and_typos(self):
        random.seed(42)
        mapper = LayoutMapper("us")
        samples = [
            "a🚀b",
            "Привет 🚀 мир!",
            "foo€bar🎉\nbaz",
            "x😀yz",
            "Hello, world!",
        ]
        for trans_rate in (0.0, 0.5, 1.0):
            config = MimicConfig()
            config.humanizer.enabled = True
            config.humanizer.error_rate = 1.0
            config.humanizer.transposition_rate = trans_rate
            config.humanizer.inertia_range = (1, 2)
            engine = HumanizerEngine(config, mapper=mapper)

            for sample in samples:
                buf = []
                for step in engine.generate_steps(sample):
                    if step.action == ActionType.TYPE_CHAR and step.char:
                        if mapper.is_supported(step.char):
                            buf.append(step.char)
                    elif step.action == ActionType.BACKSPACE:
                        self.assertGreater(len(buf), 0, f"Underflow on {sample!r}")
                        buf.pop()
                expected = "".join(c for c in sample if mapper.is_supported(c))
                self.assertEqual("".join(buf), expected)

    def test_peek_ahead_matches_source_text_after_typos(self):
        random.seed(7)
        config = MimicConfig()
        config.humanizer.enabled = True
        config.humanizer.error_rate = 1.0
        config.humanizer.transposition_rate = 0.0
        config.humanizer.inertia_range = (1, 1)
        engine = HumanizerEngine(config)

        text = "Hello. World"
        steps = list(engine.generate_steps(text))
        dot_steps = [
            s
            for s in steps
            if s.action == ActionType.TYPE_CHAR and s.char == "." and not s.is_typo
        ]
        self.assertEqual(len(dot_steps), 1)
        self.assertTrue(dot_steps[0].peek_ahead.startswith(" World"))


if __name__ == "__main__":
    unittest.main()
