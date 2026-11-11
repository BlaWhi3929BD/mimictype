import threading
import time
from typing import Callable, Optional
from evdev import ecodes as e
from mimictype.config import MimicConfig
from mimictype.core.device import UInputDevice
from mimictype.core.dynamics import DynamicsEngine
from mimictype.core.humanizer import ActionType, HumanizerEngine, TypingStep
from mimictype.core.mapper import LayoutMapper
from mimictype.core.topology import KeyboardTopology


class TyperEngine:
    """Coordinates realistic keystroke generation and low-level dispatch."""

    def __init__(
        self,
        config: Optional[MimicConfig] = None,
        device: Optional[UInputDevice] = None,
    ):
        self.config = config or MimicConfig.load()
        self.device = device or UInputDevice(self.config.device)
        self.topology = KeyboardTopology()
        self.dynamics = DynamicsEngine(self.config, self.topology)
        self.humanizer = HumanizerEngine(self.config, self.topology)
        self.mapper = LayoutMapper(self.config.layout.default_layout)
        self._stop_requested = threading.Event()

    def abort(self):
        """Signals the typing loop to immediately halt and release keys."""
        self._stop_requested.set()
        if self.device:
            self.device.release_all_modifiers()

    def switch_layout_to(self, target_layout: str):
        """Sends configured key combination to switch layout on the system."""
        switch_keys_names = self.config.layout.switch_key_combination
        key_codes = [getattr(e, k) for k in switch_keys_names if hasattr(e, k)]
        if key_codes:
            self.device.trigger_combination(key_codes)
            time.sleep(self.config.layout.switch_settle_delay)
            self.mapper.set_current_layout(target_layout)

    def type_text(
        self, text: str, on_progress: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Executes natural human typing of the provided text.
        Returns True if completed successfully, False if aborted.
        """
        self._stop_requested.clear()
        steps = list(self.humanizer.generate_steps(text))
        total_steps = len(steps)

        prev_char: Optional[str] = None

        for idx, step in enumerate(steps):
            if self._stop_requested.is_set():
                self.device.release_all_modifiers()
                return False

            if step.action == ActionType.PAUSE:
                time.sleep(step.duration)
                continue

            elif step.action == ActionType.BACKSPACE:
                self.device.backspace(step.duration or 0.045)
                prev_char = None
                continue

            elif step.action == ActionType.TYPE_CHAR and step.char:
                curr_char = step.char

                # 1. Check layout and scancode
                res = self.mapper.resolve(curr_char)
                if not res:
                    # Unknown symbol: skip or log
                    continue

                binding, need_layout_switch = res
                if need_layout_switch:
                    self.switch_layout_to(binding.layout)

                # 2. Compute context pause before key
                peek_ahead = (
                    text[min(idx + 1, len(text)) :] if idx + 1 < len(text) else ""
                )
                pause_before = self.dynamics.compute_cognitive_pause(
                    prev_char, curr_char, peek_ahead
                )
                if pause_before > 0:
                    time.sleep(pause_before)

                # 3. Compute flight time
                flight_time = self.dynamics.compute_flight_time(
                    prev_char, curr_char
                )
                time.sleep(flight_time)

                # 4. Compute dwell time and press key
                dwell_time = self.dynamics.compute_dwell_time(curr_char)
                self.device.stroke(binding.code, dwell_time, shift=binding.shift)

                prev_char = curr_char

            if on_progress:
                on_progress(idx + 1, total_steps)

        return True

    def close(self):
        if self.device:
            self.device.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
