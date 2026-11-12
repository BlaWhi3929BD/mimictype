import unittest
from mimictype.config import MimicConfig
from mimictype.core.engine import TyperEngine


class DummyDevice:
    """Mock device for testing TyperEngine without creating uinput device."""

    def __init__(self):
        self.events = []
        self.backspaces = 0

    def stroke(self, code, dwell_time, shift=False):
        self.events.append(("stroke", code, shift))

    def backspace(self, dwell_time):
        self.backspaces += 1
        self.events.append(("backspace",))

    def trigger_combination(self, codes):
        self.events.append(("combination", tuple(codes)))

    def release_all_modifiers(self):
        self.events.append(("release_modifiers",))

    def close(self):
        self.events.append(("close",))


class TestTyperEngine(unittest.TestCase):

    def test_mock_typing_execution(self):
        dummy_dev = DummyDevice()
        config = MimicConfig()
        config.humanizer.enabled = False  # Deterministic test
        config.layout.default_layout = "us"

        engine = TyperEngine(config=config, device=dummy_dev)

        progress_records = []

        def on_progress(curr, total, char):
            progress_records.append((curr, total, char))

        success = engine.type_text("Hello", on_progress=on_progress)
        self.assertTrue(success)
        self.assertEqual(len(progress_records), 5)
        # Verify events were dispatched to device
        strokes = [e for e in dummy_dev.events if e[0] == "stroke"]
        self.assertEqual(len(strokes), 5)

    def test_abort_typing(self):
        dummy_dev = DummyDevice()
        config = MimicConfig()
        config.humanizer.enabled = False

        engine = TyperEngine(config=config, device=dummy_dev)

        # Abort halfway
        def on_progress(curr, total, char):
            if curr >= 2:
                engine.abort()

        success = engine.type_text("Long text to type", on_progress=on_progress)
        self.assertFalse(success)
        self.assertIn(("release_modifiers",), dummy_dev.events)


if __name__ == "__main__":
    unittest.main()
