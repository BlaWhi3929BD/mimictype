import logging
import select
import threading
from typing import Callable, Dict, List, Optional, Set, Tuple
import evdev
from evdev import ecodes as e

logger = logging.getLogger("mimictype.listener")


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
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.hotkey_str = hotkey_str.lower()
        self.on_trigger = on_trigger
        self.on_emergency_stop = on_emergency_stop
        self.on_error = on_error
        self.ignore_device_names = ignore_device_names or [
            "Logitech USB Keyboard",
            "mimictype",
        ]

        self._target_modifiers: Set[str] = set()
        self._target_key_code: int = e.KEY_V
        self._parse_hotkey()

        self._devices: Dict[int, evdev.InputDevice] = {}
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_error: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self._running and bool(self._devices)

    def _parse_hotkey(self):
        parts = [p.strip() for p in self.hotkey_str.split("+")]
        for part in parts[:-1]:
            if part in self.MODIFIER_MAP:
                self._target_modifiers.add(part)

        trigger_key_name = parts[-1].upper()
        code = getattr(e, f"KEY_{trigger_key_name}", None)
        if code is not None:
            self._target_key_code = code
        else:
            self._target_key_code = e.KEY_V

    def _report_error(self, msg: str):
        self.last_error = msg
        logger.warning(msg)
        if self.on_error:
            try:
                self.on_error(msg)
            except Exception:
                pass

    def _scan_keyboards(self) -> Tuple[List[evdev.InputDevice], int]:
        keyboards: List[evdev.InputDevice] = []
        permission_denied = 0

        try:
            paths = evdev.list_devices()
        except Exception as exc:
            self.last_error = f"Unable to enumerate /dev/input devices: {exc}"
            return [], 0

        for path in paths:
            dev = None
            keep = False
            try:
                dev = evdev.InputDevice(path)
                if any(ignored in dev.name for ignored in self.ignore_device_names):
                    continue
                caps = dev.capabilities()
                if e.EV_KEY in caps:
                    keys = caps[e.EV_KEY]
                    if e.KEY_A in keys and e.KEY_SPACE in keys:
                        keyboards.append(dev)
                        keep = True
            except PermissionError:
                permission_denied += 1
            except OSError:
                continue
            except Exception:
                continue
            finally:
                if dev is not None and not keep:
                    try:
                        dev.close()
                    except Exception:
                        pass

        return keyboards, permission_denied

    def _close_devices(self):
        for dev in self._devices.values():
            try:
                dev.close()
            except Exception:
                pass
        self._devices.clear()

    def _remove_device(self, fd: int, per_dev_held: Dict[int, Set[int]]):
        dev = self._devices.pop(fd, None)
        per_dev_held.pop(fd, None)
        if dev is not None:
            try:
                dev.close()
            except Exception:
                pass

    def start(self) -> bool:
        """
        Scans physical keyboards and starts the background listener thread.
        Returns True if at least one keyboard is being monitored, False otherwise.
        """
        if self._running:
            return bool(self._devices)

        self.last_error = None
        devs, permission_denied = self._scan_keyboards()
        if not devs:
            if permission_denied > 0:
                self._report_error(
                    "Permission denied reading /dev/input/event*; "
                    "evdev global hotkeys and ESC Kill Switch are disabled. "
                    "Use a DE shortcut with 'mimictype trigger'/'stop' or opt into the 'input' group."
                )
            else:
                self._report_error(
                    "No readable physical keyboard devices found in /dev/input."
                )
            return False

        self._devices = {dev.fd: dev for dev in devs}
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="mimictype-hotkey-listener"
        )
        self._thread.start()
        return True

    def stop(self):
        """Stops listener and closes devices."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.5)
            self._thread = None
        self._close_devices()

    def _listen_loop(self):
        per_dev_held: Dict[int, Set[int]] = {}

        while self._running:
            if not self._devices:
                # Re-scan periodically in case all keyboards disconnected and reconnected
                if self._stop_event.wait(2.0):
                    break
                devs, _ = self._scan_keyboards()
                if devs:
                    self._devices = {dev.fd: dev for dev in devs}
                    per_dev_held.clear()
                continue

            fds = list(self._devices.keys())
            try:
                r, _, _ = select.select(fds, [], [], 0.5)
            except (OSError, ValueError):
                # Clean out any invalid fd rather than spinning or crashing
                for fd in fds:
                    dev = self._devices.get(fd)
                    try:
                        if dev is not None:
                            dev.capabilities()
                    except OSError:
                        self._remove_device(fd, per_dev_held)
                continue

            for fd in r:
                dev = self._devices.get(fd)
                if not dev:
                    continue
                held_keys = per_dev_held.setdefault(fd, set())
                try:
                    for event in dev.read():
                        if event.type != e.EV_KEY:
                            continue

                        key = event.code
                        value = event.value  # 0: up, 1: down, 2: hold

                        if value == 1:
                            held_keys.add(key)

                            if key == e.KEY_ESC and self.on_emergency_stop:
                                self.on_emergency_stop()

                            if key == self._target_key_code:
                                combined_held: Set[int] = set()
                                for keys_set in per_dev_held.values():
                                    combined_held.update(keys_set)

                                mods_satisfied = all(
                                    bool(combined_held & self.MODIFIER_MAP[mod])
                                    for mod in self._target_modifiers
                                )
                                if mods_satisfied and self.on_trigger:
                                    self.on_trigger()

                        elif value == 0:
                            held_keys.discard(key)

                except OSError:
                    # Physical device disconnected: drop dead fd cleanly from select set
                    logger.info("Input device %s disconnected; removing fd %s", dev.name, fd)
                    self._remove_device(fd, per_dev_held)
