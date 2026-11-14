import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from evdev import ecodes as e

from mimictype.config import MimicConfig
from mimictype.core.daemon import MimicDaemon
from mimictype.core.listener import HotkeyListener


class _FakeKeyboardDevice:
    def __init__(self, fd: int, name: str = "Fake Keyboard", fail_on_read: bool = False, events=None):
        self.fd = fd
        self.name = name
        self.fail_on_read = fail_on_read
        self._events = list(events or [])
        self.closed = False

    def capabilities(self):
        return {e.EV_KEY: [e.KEY_A, e.KEY_SPACE, e.KEY_ESC]}

    def read(self):
        if self.fail_on_read:
            raise OSError(19, "No such device")
        evs = self._events
        self._events = []
        return evs

    def close(self):
        self.closed = True


class TestHotkeyListenerAndDaemon(unittest.TestCase):
    def test_permission_denied_reports_error_instead_of_silent_exit(self):
        errors = []
        listener = HotkeyListener(on_error=errors.append)

        with (
            patch("mimictype.core.listener.evdev.list_devices", return_value=["/dev/input/event0"]),
            patch("mimictype.core.listener.evdev.InputDevice", side_effect=PermissionError("denied")),
        ):
            started = listener.start()

        self.assertFalse(started)
        self.assertIsNotNone(listener.last_error)
        self.assertIn("/dev/input/event*", listener.last_error)
        self.assertEqual(len(errors), 1)

    def test_disconnected_keyboard_fd_removed_from_select(self):
        dead_dev = _FakeKeyboardDevice(fd=99, name="Dead KB", fail_on_read=True)
        live_dev = _FakeKeyboardDevice(fd=100, name="Live KB", fail_on_read=False)
        listener = HotkeyListener()
        listener._devices = {99: dead_dev, 100: live_dev}
        listener._running = True
        listener._stop_event.clear()

        seen_rlists = []

        def fake_select(rlist, wlist, xlist, timeout):
            seen_rlists.append(list(rlist))
            if len(seen_rlists) == 1:
                return [99], [], []
            listener._running = False
            listener._stop_event.set()
            return [], [], []

        with patch("mimictype.core.listener.select.select", side_effect=fake_select):
            listener._listen_loop()

        self.assertEqual(seen_rlists, [[99, 100], [100]])
        self.assertNotIn(99, listener._devices)
        self.assertIn(100, listener._devices)
        self.assertTrue(dead_dev.closed)
        self.assertFalse(live_dev.closed)

    def test_hotkey_and_esc_events_dispatch(self):
        triggered = []
        aborted = []
        events = [
            SimpleNamespace(type=e.EV_KEY, code=e.KEY_LEFTCTRL, value=1),
            SimpleNamespace(type=e.EV_KEY, code=e.KEY_LEFTALT, value=1),
            SimpleNamespace(type=e.EV_KEY, code=e.KEY_V, value=1),
            SimpleNamespace(type=e.EV_KEY, code=e.KEY_ESC, value=1),
        ]
        dev = _FakeKeyboardDevice(fd=50, events=events)
        listener = HotkeyListener(
            hotkey_str="ctrl+alt+v",
            on_trigger=lambda: triggered.append(True),
            on_emergency_stop=lambda: aborted.append(True),
        )
        listener._devices = {50: dev}
        listener._running = True
        listener._stop_event.clear()

        passes = 0

        def fake_select(rlist, wlist, xlist, timeout):
            nonlocal passes
            passes += 1
            if passes == 1:
                return [50], [], []
            listener._running = False
            listener._stop_event.set()
            return [], [], []

        with patch("mimictype.core.listener.select.select", side_effect=fake_select):
            listener._listen_loop()

        self.assertEqual(len(triggered), 1)
        self.assertEqual(len(aborted), 1)

    def test_daemon_trigger_does_not_block_caller_when_clipboard_slow(self):
        cfg = MimicConfig()
        daemon = MimicDaemon(config=cfg)
        daemon.engine = MagicMock()
        daemon.engine.type_text.return_value = True

        clipboard_started = threading.Event()
        release_clipboard = threading.Event()

        def slow_clipboard():
            clipboard_started.set()
            release_clipboard.wait(timeout=2.0)
            return "hello"

        with (
            patch("mimictype.core.daemon.ClipboardReader.get_text", side_effect=slow_clipboard),
            patch("mimictype.core.daemon.send_notification"),
        ):
            t0 = time.monotonic()
            daemon.trigger_typing()
            elapsed = time.monotonic() - t0
            self.assertLess(elapsed, 0.1)
            self.assertTrue(clipboard_started.wait(timeout=1.0))
            release_clipboard.set()

            deadline = time.monotonic() + 1.0
            while not daemon.engine.type_text.called and time.monotonic() < deadline:
                time.sleep(0.01)

            daemon.engine.type_text.assert_called_once_with("hello")


if __name__ == "__main__":
    unittest.main()
