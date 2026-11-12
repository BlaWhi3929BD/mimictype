import unittest
from mimictype.config import MimicConfig
from mimictype.core.humanizer import ActionType, HumanizerEngine


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


if __name__ == "__main__":
    unittest.main()
