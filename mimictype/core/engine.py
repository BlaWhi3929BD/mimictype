import threading
import time
from typing import Callable, Optional
from evdev import ecodes as e
from mimictype.config import MimicConfig
from mimictype.core.device import UInputDevice
from mimictype.core.dynamics import DynamicsEngine
from mimictype.core.humanizer import ActionType, HumanizerEngine, TypingStep
from mimictype.core.layout_detector import LayoutDetector
from mimictype.core.mapper import LayoutMapper
from mimictype.core.normalizer import TextNormalizer
from mimictype.core.topology import KeyboardTopology


class TyperEngine:
    """Coordinates realistic keystroke generation, low-level dispatch, and state tracking."""

    def __init__(
        self,
        config: Optional[MimicConfig] = None,
        device: Optional[UInputDevice] = None,
    ):
        self.config = config or MimicConfig.load()
        self.device = device or UInputDevice(self.config.device)
        self.topology = KeyboardTopology()
        self.layout_detector = LayoutDetector()

        # Initialize layout with active OS layout if detectable, else config default
        initial_layout = (
            self.layout_detector.get_active_layout()
            or self.config.layout.default_layout
        )
        self.mapper = LayoutMapper(initial_layout)
        self.dynamics = DynamicsEngine(self.config, self.topology)
        self.humanizer = HumanizerEngine(
            self.config, self.topology, mapper=self.mapper
        )
        self._stop_requested = threading.Event()
        self._is_typing = threading.Event()

    @property
    def is_typing(self) -> bool:
        return self._is_typing.is_set()

    def abort(self):
        """Signals the typing loop to immediately halt and release keys."""
        self._stop_requested.set()
        if self.device:
            self.device.release_all_modifiers()

    def switch_layout_to(self, target_layout: str):
        """Switches desktop layout via DBus/system API or simulated hotkey."""
        # Try direct desktop switch (e.g. KDE DBus)
        if self.layout_detector.switch_layout_direct(target_layout):
            time.sleep(self.config.layout.switch_settle_delay)
            self.mapper.set_current_layout(target_layout)
            return

        # Fallback to physical key combination (e.g. Alt+Shift)
        switch_keys_names = self.config.layout.switch_key_combination
        key_codes = [getattr(e, k) for k in switch_keys_names if hasattr(e, k)]
        if key_codes:
            self.device.trigger_combination(key_codes)
            time.sleep(self.config.layout.switch_settle_delay)
            self.mapper.set_current_layout(target_layout)

    def type_text(
        self,
        raw_text: str,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_event: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        """
        Executes natural human typing of the provided text.
        Returns True if completed successfully, False if aborted.
        """
        if not raw_text:
            return True

        # Pre-normalize unicode symbols (quotes, dashes, non-breaking spaces)
        text = TextNormalizer.normalize(raw_text)

        # Refresh active OS layout before typing so manual layout changes are tracked
        active_layout = self.layout_detector.get_active_layout()
        if active_layout:
            self.mapper.set_current_layout(active_layout)

        # Synchronize layout before typing the first letter
        first_letter = next((c for c in text if c.isalpha()), None)
        if first_letter:
            res = self.mapper.resolve(first_letter)
            if res:
                binding, need_switch = res
                if need_switch:
                    self.switch_layout_to(binding.layout)

        self._stop_requested.clear()
        self._is_typing.set()

        try:
            steps = list(self.humanizer.generate_steps(text))
            total_steps = len(steps)
            prev_char: Optional[str] = None
            chars_typed_count = 0

            for idx, step in enumerate(steps):
                if self._stop_requested.is_set():
                    self.device.release_all_modifiers()
                    if on_event:
                        on_event("abort", "Typing was aborted by user.")
                    return False

                if step.action == ActionType.PAUSE:
                    time.sleep(step.duration)
                    continue

                elif step.action == ActionType.BACKSPACE:
                    self.device.backspace(step.duration or 0.045)
                    prev_char = None
                    if on_event:
                        on_event("backspace", "Correcting mistake")
                    continue

                elif step.action == ActionType.TYPE_CHAR and step.char:
                    curr_char = step.char

                    # 1. Resolve key binding
                    res = self.mapper.resolve(curr_char)
                    if not res:
                        # Character not in map: skip
                        continue

                    binding, need_layout_switch = res
                    if need_layout_switch:
                        self.switch_layout_to(binding.layout)

                    # 2. Context pause before key (punctuation, newlines, code blocks)
                    if not step.is_typo:
                        pause_before = self.dynamics.compute_cognitive_pause(
                            prev_char, curr_char, step.peek_ahead
                        )
                        if pause_before > 0:
                            time.sleep(pause_before)

                    # 3. Flight time (gap before pressing)
                    flight_time = self.dynamics.compute_flight_time(
                        prev_char, curr_char
                    )
                    time.sleep(flight_time)

                    # 4. Dwell time & key press
                    dwell_time = self.dynamics.compute_dwell_time(curr_char)
                    self.device.stroke(
                        binding.code, dwell_time, shift=binding.shift
                    )

                    chars_typed_count += 1
                    prev_char = curr_char

                    if on_event and step.description:
                        on_event("typo", f"{step.description}: '{curr_char}'")

                if on_progress:
                    on_progress(idx + 1, total_steps, curr_char if step.action == ActionType.TYPE_CHAR else "")

            return True
        finally:
            self._is_typing.clear()
            self.device.release_all_modifiers()

    def close(self):
        self.abort()
        if self.device:
            self.device.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
