import unittest
from unittest.mock import patch
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

    def test_peek_ahead_not_desynced_by_typos(self):
        dummy_dev = DummyDevice()
        config = MimicConfig(wpm=300)
        config.humanizer.enabled = True
        config.humanizer.error_rate = 1.0
        config.humanizer.transposition_rate = 0.0
        config.humanizer.inertia_range = (1, 1)
        config.humanizer.perception_delay = (0.0, 0.0)
        config.humanizer.recovery_delay = (0.0, 0.0)
        config.humanizer.backspace_dwell = 0.0
        config.humanizer.backspace_flight = 0.0

        seen = []
        engine = TyperEngine(config=config, device=dummy_dev)
        with (
            patch.object(
                engine.dynamics,
                "compute_cognitive_pause",
                side_effect=lambda prev, curr, peek: seen.append((curr, peek)) or 0.0,
            ),
            patch("mimictype.core.engine.time.sleep"),
        ):
            self.assertTrue(engine.type_text("abc. def"))

        dot_calls = [peek for ch, peek in seen if ch == "."]
        self.assertEqual(dot_calls, [" def"])

    def test_layout_refreshed_before_each_type_text(self):
        dummy_dev = DummyDevice()
        config = MimicConfig()
        config.humanizer.enabled = False
        config.layout.default_layout = "us"

        with patch(
            "mimictype.core.layout_detector.LayoutDetector.get_active_layout",
            side_effect=["us", "ru"],
        ):
            engine = TyperEngine(config=config, device=dummy_dev)
            with patch.object(engine, "switch_layout_to") as mock_switch:
                engine.type_text("Привет")
                mock_switch.assert_not_called()
                self.assertEqual(engine.mapper.current_layout, "ru")


if __name__ == "__main__":
    unittest.main()
