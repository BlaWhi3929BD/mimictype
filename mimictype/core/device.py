import time
from typing import List, Optional
import evdev
from evdev import UInput, ecodes as e
from mimictype.config import DeviceConfig


class UInputDevice:
    """Manages creation and low-level hardware event dispatch via /dev/uinput."""

    def __init__(self, config: Optional[DeviceConfig] = None):
        self.config = config or DeviceConfig()
        self._uinput: Optional[UInput] = None
        self._init_device()

    def _init_device(self):
        # Build list of all standard keyboard keys to register
        keys = [
            e.KEY_ESC,
            e.KEY_1,
            e.KEY_2,
            e.KEY_3,
            e.KEY_4,
            e.KEY_5,
            e.KEY_6,
            e.KEY_7,
            e.KEY_8,
            e.KEY_9,
            e.KEY_0,
            e.KEY_MINUS,
            e.KEY_EQUAL,
            e.KEY_BACKSPACE,
            e.KEY_TAB,
            e.KEY_Q,
            e.KEY_W,
            e.KEY_E,
            e.KEY_R,
            e.KEY_T,
            e.KEY_Y,
            e.KEY_U,
            e.KEY_I,
            e.KEY_O,
            e.KEY_P,
            e.KEY_LEFTBRACE,
            e.KEY_RIGHTBRACE,
            e.KEY_ENTER,
            e.KEY_LEFTCTRL,
            e.KEY_A,
            e.KEY_S,
            e.KEY_D,
            e.KEY_F,
            e.KEY_G,
            e.KEY_H,
            e.KEY_J,
            e.KEY_K,
            e.KEY_L,
            e.KEY_SEMICOLON,
            e.KEY_APOSTROPHE,
            e.KEY_GRAVE,
            e.KEY_LEFTSHIFT,
            e.KEY_BACKSLASH,
            e.KEY_Z,
            e.KEY_X,
            e.KEY_C,
            e.KEY_V,
            e.KEY_B,
            e.KEY_N,
            e.KEY_M,
            e.KEY_COMMA,
            e.KEY_DOT,
            e.KEY_SLASH,
            e.KEY_RIGHTSHIFT,
            e.KEY_KPASTERISK,
            e.KEY_LEFTALT,
            e.KEY_SPACE,
            e.KEY_CAPSLOCK,
            e.KEY_RIGHTALT,
            e.KEY_RIGHTCTRL,
            e.KEY_UP,
            e.KEY_DOWN,
            e.KEY_LEFT,
            e.KEY_RIGHT,
            e.KEY_DELETE,
            e.KEY_HOME,
            e.KEY_END,
            e.KEY_PAGEUP,
            e.KEY_PAGEDOWN,
        ]

        capabilities = {
            e.EV_KEY: keys,
        }

        self._uinput = UInput(
            events=capabilities,
            name=self.config.name,
            vendor=self.config.vendor_id,
            product=self.config.product_id,
            version=self.config.version,
            bustype=e.BUS_USB,
        )
        # Give OS / udev / libinput a brief moment to discover device node
        time.sleep(0.15)

    def key_down(self, code: int):
        """Emits hardware key press event."""
        if self._uinput:
            self._uinput.write(e.EV_KEY, code, 1)
            self._uinput.syn()

    def key_up(self, code: int):
        """Emits hardware key release event."""
        if self._uinput:
            self._uinput.write(e.EV_KEY, code, 0)
            self._uinput.syn()

    def stroke(
        self,
        code: int,
        dwell_time: float,
        shift: bool = False,
        shift_pre_delay: float = 0.040,
        shift_post_delay: float = 0.035,
    ):
        """
        Emits a full press-release cycle with precise dwell duration and optional Shift modifier.
        """
        if shift:
            self.key_down(e.KEY_LEFTSHIFT)
            time.sleep(shift_pre_delay)

        self.key_down(code)
        time.sleep(dwell_time)
        self.key_up(code)

        if shift:
            time.sleep(shift_post_delay)
            self.key_up(e.KEY_LEFTSHIFT)

    def backspace(self, dwell_time: float = 0.045):
        """Emits a single Backspace key event."""
        self.stroke(e.KEY_BACKSPACE, dwell_time)

    def trigger_combination(self, codes: List[int], dwell_time: float = 0.050):
        """Presses and releases a combination of keys (e.g. Alt+Shift for layout switch)."""
        for code in codes:
            self.key_down(code)
            time.sleep(0.015)

        time.sleep(dwell_time)

        for code in reversed(codes):
            self.key_up(code)
            time.sleep(0.010)

    def release_all_modifiers(self):
        """Safety function to release common modifiers."""
        modifiers = [
            e.KEY_LEFTSHIFT,
            e.KEY_RIGHTSHIFT,
            e.KEY_LEFTCTRL,
            e.KEY_RIGHTCTRL,
            e.KEY_LEFTALT,
            e.KEY_RIGHTALT,
        ]
        for mod in modifiers:
            self.key_up(mod)

    def close(self):
        """Closes and unregisters virtual uinput device."""
        if self._uinput:
            self.release_all_modifiers()
            self._uinput.close()
            self._uinput = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
