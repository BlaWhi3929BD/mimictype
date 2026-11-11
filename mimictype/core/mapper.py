from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from evdev import ecodes as e


@dataclass
class KeyBinding:
    code: int
    shift: bool = False
    layout: str = "us"  # "us" or "ru"


class LayoutMapper:
    """Translates UTF-8 characters to Linux evdev scancodes, Shift modifiers, and keyboard layouts."""

    def __init__(self, default_layout: str = "us"):
        self.current_layout = default_layout
        self._map_us: Dict[str, KeyBinding] = {}
        self._map_ru: Dict[str, KeyBinding] = {}
        self._build_tables()

    def _build_tables(self):
        # 1. Base US Layout
        # Digits & symbols on number row
        num_row = [
            ("`", "~", e.KEY_GRAVE),
            ("1", "!", e.KEY_1),
            ("2", "@", e.KEY_2),
            ("3", "#", e.KEY_3),
            ("4", "$", e.KEY_4),
            ("5", "%", e.KEY_5),
            ("6", "^", e.KEY_6),
            ("7", "&", e.KEY_7),
            ("8", "*", e.KEY_8),
            ("9", "(", e.KEY_9),
            ("0", ")", e.KEY_0),
            ("-", "_", e.KEY_MINUS),
            ("=", "+", e.KEY_EQUAL),
        ]
        for unshifted, shifted, code in num_row:
            self._map_us[unshifted] = KeyBinding(code, shift=False, layout="us")
            self._map_us[shifted] = KeyBinding(code, shift=True, layout="us")

        # Alphabet US
        letters = [
            ("q", e.KEY_Q),
            ("w", e.KEY_W),
            ("e", e.KEY_E),
            ("r", e.KEY_R),
            ("t", e.KEY_T),
            ("y", e.KEY_Y),
            ("u", e.KEY_U),
            ("i", e.KEY_I),
            ("o", e.KEY_O),
            ("p", e.KEY_P),
            ("a", e.KEY_A),
            ("s", e.KEY_S),
            ("d", e.KEY_D),
            ("f", e.KEY_F),
            ("g", e.KEY_G),
            ("h", e.KEY_H),
            ("j", e.KEY_J),
            ("k", e.KEY_K),
            ("l", e.KEY_L),
            ("z", e.KEY_Z),
            ("x", e.KEY_X),
            ("c", e.KEY_C),
            ("v", e.KEY_V),
            ("b", e.KEY_B),
            ("n", e.KEY_N),
            ("m", e.KEY_M),
        ]
        for char, code in letters:
            self._map_us[char] = KeyBinding(code, shift=False, layout="us")
            self._map_us[char.upper()] = KeyBinding(
                code, shift=True, layout="us"
            )

        # US Punctuation
        punct_us = [
            ("[", "{", e.KEY_LEFTBRACE),
            ("]", "}", e.KEY_RIGHTBRACE),
            (";", ":", e.KEY_SEMICOLON),
            ("'", '"', e.KEY_APOSTROPHE),
            (",", "<", e.KEY_COMMA),
            (".", ">", e.KEY_DOT),
            ("/", "?", e.KEY_SLASH),
            ("\\", "|", e.KEY_BACKSLASH),
        ]
        for unshifted, shifted, code in punct_us:
            self._map_us[unshifted] = KeyBinding(code, shift=False, layout="us")
            self._map_us[shifted] = KeyBinding(code, shift=True, layout="us")

        # Common Whitespace & Control Keys (layout independent)
        common_keys = {
            " ": KeyBinding(e.KEY_SPACE, shift=False),
            "\n": KeyBinding(e.KEY_ENTER, shift=False),
            "\t": KeyBinding(e.KEY_TAB, shift=False),
        }
        for k, v in common_keys.items():
            self._map_us[k] = v
            self._map_ru[k] = v

        # 2. Russian JCUKEN Layout
        ru_letters = [
            ("й", e.KEY_Q),
            ("ц", e.KEY_W),
            ("у", e.KEY_E),
            ("к", e.KEY_R),
            ("е", e.KEY_T),
            ("н", e.KEY_Y),
            ("г", e.KEY_U),
            ("ш", e.KEY_I),
            ("щ", e.KEY_O),
            ("з", e.KEY_P),
            ("х", e.KEY_LEFTBRACE),
            ("ъ", e.KEY_RIGHTBRACE),
            ("ф", e.KEY_A),
            ("ы", e.KEY_S),
            ("в", e.KEY_D),
            ("а", e.KEY_F),
            ("п", e.KEY_G),
            ("р", e.KEY_H),
            ("о", e.KEY_J),
            ("л", e.KEY_K),
            ("д", e.KEY_L),
            ("ж", e.KEY_SEMICOLON),
            ("э", e.KEY_APOSTROPHE),
            ("я", e.KEY_Z),
            ("ч", e.KEY_X),
            ("с", e.KEY_C),
            ("м", e.KEY_V),
            ("и", e.KEY_B),
            ("т", e.KEY_N),
            ("ь", e.KEY_M),
            ("б", e.KEY_COMMA),
            ("ю", e.KEY_DOT),
            ("ё", e.KEY_GRAVE),
        ]
        for char, code in ru_letters:
            self._map_ru[char] = KeyBinding(code, shift=False, layout="ru")
            self._map_ru[char.upper()] = KeyBinding(
                code, shift=True, layout="ru"
            )

        # Russian punctuation
        punct_ru = [
            (".", e.KEY_SLASH, False),
            (",", e.KEY_SLASH, True),
            ("!", e.KEY_1, True),
            ('"', e.KEY_2, True),
            ("№", e.KEY_3, True),
            (";", e.KEY_4, True),
            ("%", e.KEY_5, True),
            (":", e.KEY_6, True),
            ("?", e.KEY_7, True),
            ("*", e.KEY_8, True),
            ("(", e.KEY_9, True),
            (")", e.KEY_0, True),
            ("-", e.KEY_MINUS, False),
            ("_", e.KEY_MINUS, True),
            ("=", e.KEY_EQUAL, False),
            ("+", e.KEY_EQUAL, True),
            ("\\", e.KEY_BACKSLASH, False),
            ("/", e.KEY_BACKSLASH, True),
        ]
        for sym, code, shift in punct_ru:
            self._map_ru[sym] = KeyBinding(code, shift=shift, layout="ru")

    def resolve(
        self, char: str
    ) -> Optional[Tuple[KeyBinding, bool]]:
        """
        Resolves char to KeyBinding.
        Returns: (KeyBinding, layout_switch_needed)
        """
        # Prefer current layout if character is available in it
        if self.current_layout == "ru" and char in self._map_ru:
            return self._map_ru[char], False
        if self.current_layout == "us" and char in self._map_us:
            return self._map_us[char], False

        # If not in current, check alternative layout
        if char in self._map_us:
            return self._map_us[char], (self.current_layout != "us")
        if char in self._map_ru:
            return self._map_ru[char], (self.current_layout != "ru")

        # Unknown symbol
        return None

    def set_current_layout(self, layout: str):
        self.current_layout = layout
