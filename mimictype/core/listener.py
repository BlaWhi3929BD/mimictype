import select
import threading
from typing import Callable, Dict, List, Optional, Set
import evdev
from evdev import ecodes as e


class HotkeyListener:
    """
    Monitors physical Linux keyboards via evdev in non-blocking / passive mode (no grab),
    detecting global activation hotkeys and the emergency Kill Switch (ESC).
    """

    MODIFIER_MAP = {
        "ctrl": {e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL},
        "alt": {e.KEY_LEFTALT, e.KEY_RIGHTALT},
        "shift": {e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT},
        "super": {e.KEY_LEFTMETA, e.KEY_RIGHTMETA},
        "meta": {e.KEY_LEFTMETA, e.KEY_RIGHTMETA},
    }

    def __init__(
        self,
        hotkey_str: str = "ctrl+alt+v",
        on_trigger: Optional[Callable[[], None]] = None,
        on_emergency_stop: Optional[Callable[[], None]] = None,
        ignore_device_names: Optional[List[str]] = None,
    ):
        self.hotkey_str = hotkey_str.lower()
        self.on_trigger = on_trigger
        self.on_emergency_stop = on_emergency_stop
        self.ignore_device_names = ignore_device_names or [
            "Logitech USB Keyboard",
            "mimictype",
        ]

        self._active_modifiers: Set[str] = set()
        self._target_modifiers: Set[str] = set()
        self._target_key_code: int = e.KEY_V
        self._parse_hotkey()

        self._devices: Dict[int, evdev.InputDevice] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _parse_hotkey(self):
        parts = [p.strip() for p in self.hotkey_str.split("+")]
        for part in parts[:-1]:
            if part in self.MODIFIER_MAP:
                self._target_modifiers.add(part)

        trigger_key_name = parts[-1].upper()
        # Look up keycode in ecodes.KEY_<NAME>
        code = getattr(e, f"KEY_{trigger_key_name}", None)
        if code is not None:
            self._target_key_code = code
        else:
            self._target_key_code = e.KEY_V

    def _scan_keyboards(self) -> List[evdev.InputDevice]:
        keyboards = []
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                if any(ignored in dev.name for ignored in self.ignore_device_names):
                    continue
                caps = dev.capabilities()
                if e.EV_KEY in caps:
                    keys = caps[e.EV_KEY]
                    # Must have normal typing keys
                    if e.KEY_A in keys and e.KEY_SPACE in keys:
                        keyboards.append(dev)
            except Exception:
                continue
        return keyboards

    def start(self):
        """Starts background listener thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="mimictype-hotkey-listener"
        )
        self._thread.start()

    def stop(self):
        """Stops listener and closes devices."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.5)
            self._thread = None
        for dev in self._devices.values():
            try:
                dev.close()
            except Exception:
                pass
        self._devices.clear()

    def _listen_loop(self):
        devs = self._scan_keyboards()
        if not devs:
            return

        self._devices = {dev.fd: dev for dev in devs}
        held_keys: Set[int] = set()

        while self._running:
            try:
                r, _, _ = select.select(list(self._devices.keys()), [], [], 0.5)
            except Exception:
                break

            for fd in r:
                dev = self._devices.get(fd)
                if not dev:
                    continue
                try:
                    for event in dev.read():
                        if event.type != e.EV_KEY:
                            continue

                        key = event.code
                        value = event.value  # 0: up, 1: down, 2: hold

                        if value == 1:  # Key down
                            held_keys.add(key)

                            # Emergency Kill Switch check
                            if key == e.KEY_ESC and self.on_emergency_stop:
                                self.on_emergency_stop()

                            # Trigger hotkey check
                            if key == self._target_key_code:
                                # Check if all required modifiers are held
                                mods_satisfied = True
                                for mod in self._target_modifiers:
                                    matching_codes = self.MODIFIER_MAP[mod]
                                    if not (held_keys & matching_codes):
                                        mods_satisfied = False
                                        break
                                if mods_satisfied and self.on_trigger:
                                    self.on_trigger()

                        elif value == 0:  # Key up
                            held_keys.discard(key)

                except OSError:
                    # Device disconnected or read failed
                    break
