import math
from typing import Dict, List, Optional, Set, Tuple

# Physical layout grid: row (0: numbers, 1: top, 2: home, 3: bottom), col (0..12)
# Hand mapping: True = Left hand, False = Right hand
# Finger mapping: 1: pinky, 2: ring, 3: middle, 4: index, 5: thumb

KEY_COORDINATES_US: Dict[str, Tuple[int, float, bool, int]] = {
    # char: (row, col, is_left_hand, finger)
    # Row 0 (Number row)
    "`": (0, 0.0, True, 1),
    "1": (0, 1.0, True, 1),
    "2": (0, 2.0, True, 2),
    "3": (0, 3.0, True, 3),
    "4": (0, 4.0, True, 4),
    "5": (0, 5.0, True, 4),
    "6": (0, 6.0, False, 4),
    "7": (0, 7.0, False, 4),
    "8": (0, 8.0, False, 3),
    "9": (0, 9.0, False, 2),
    "0": (0, 10.0, False, 1),
    "-": (0, 11.0, False, 1),
    "=": (0, 12.0, False, 1),
    # Row 1 (QWERTY)
    "q": (1, 1.5, True, 1),
    "w": (1, 2.5, True, 2),
    "e": (1, 3.5, True, 3),
    "r": (1, 4.5, True, 4),
    "t": (1, 5.5, True, 4),
    "y": (1, 6.5, False, 4),
    "u": (1, 7.5, False, 4),
    "i": (1, 8.5, False, 3),
    "o": (1, 9.5, False, 2),
    "p": (1, 10.5, False, 1),
    "[": (1, 11.5, False, 1),
    "]": (1, 12.5, False, 1),
    # Row 2 (Home row)
    "a": (2, 1.8, True, 1),
    "s": (2, 2.8, True, 2),
    "d": (2, 3.8, True, 3),
    "f": (2, 4.8, True, 4),
    "g": (2, 5.8, True, 4),
    "h": (2, 6.8, False, 4),
    "j": (2, 7.8, False, 4),
    "k": (2, 8.8, False, 3),
    "l": (2, 9.8, False, 2),
    ";": (2, 10.8, False, 1),
    "'": (2, 11.8, False, 1),
    # Row 3 (Bottom row)
    "z": (3, 2.2, True, 1),
    "x": (3, 3.2, True, 2),
    "c": (3, 4.2, True, 3),
    "v": (3, 5.2, True, 4),
    "b": (3, 6.2, True, 4),
    "n": (3, 7.2, False, 4),
    "m": (3, 8.2, False, 4),
    ",": (3, 9.2, False, 3),
    ".": (3, 10.2, False, 2),
    "/": (3, 11.2, False, 1),
    # Row 4 (Space)
    " ": (4, 6.0, True, 5),
}

KEY_COORDINATES_RU: Dict[str, Tuple[int, float, bool, int]] = {
    # Row 0
    "ё": (0, 0.0, True, 1),
    "1": (0, 1.0, True, 1),
    "2": (0, 2.0, True, 2),
    "3": (0, 3.0, True, 3),
    "4": (0, 4.0, True, 4),
    "5": (0, 5.0, True, 4),
    "6": (0, 6.0, False, 4),
    "7": (0, 7.0, False, 4),
    "8": (0, 8.0, False, 3),
    "9": (0, 9.0, False, 2),
    "0": (0, 10.0, False, 1),
    "-": (0, 11.0, False, 1),
    "=": (0, 12.0, False, 1),
    # Row 1 (ЙЦУКЕН)
    "й": (1, 1.5, True, 1),
    "ц": (1, 2.5, True, 2),
    "у": (1, 3.5, True, 3),
    "к": (1, 4.5, True, 4),
    "е": (1, 5.5, True, 4),
    "н": (1, 6.5, False, 4),
    "г": (1, 7.5, False, 4),
    "ш": (1, 8.5, False, 3),
    "щ": (1, 9.5, False, 2),
    "з": (1, 10.5, False, 1),
    "х": (1, 11.5, False, 1),
    "ъ": (1, 12.5, False, 1),
    # Row 2 (ФЫВАПРОЛДЖЭ)
    "ф": (2, 1.8, True, 1),
    "ы": (2, 2.8, True, 2),
    "в": (2, 3.8, True, 3),
    "а": (2, 4.8, True, 4),
    "п": (2, 5.8, True, 4),
    "р": (2, 6.8, False, 4),
    "о": (2, 7.8, False, 4),
    "л": (2, 8.8, False, 3),
    "д": (2, 9.8, False, 2),
    "ж": (2, 10.8, False, 1),
    "э": (2, 11.8, False, 1),
    # Row 3 (ЯЧСМИТЬБЮ)
    "я": (3, 2.2, True, 1),
    "ч": (3, 3.2, True, 2),
    "с": (3, 4.2, True, 3),
    "м": (3, 5.2, True, 4),
    "и": (3, 6.2, True, 4),
    "т": (3, 7.2, False, 4),
    "ь": (3, 8.2, False, 4),
    "б": (3, 9.2, False, 3),
    "ю": (3, 10.2, False, 2),
    ".": (3, 11.2, False, 1),
    # Row 4 (Space)
    " ": (4, 6.0, True, 5),
}


class KeyboardTopology:
    """Provides spatial key distances and adjacency maps for realistic typing physics."""

    def __init__(self):
        self.adjacencies_us: Dict[str, List[str]] = self._build_adjacency_map(
            KEY_COORDINATES_US
        )
        self.adjacencies_ru: Dict[str, List[str]] = self._build_adjacency_map(
            KEY_COORDINATES_RU
        )

    def _build_adjacency_map(
        self, coords: Dict[str, Tuple[int, float, bool, int]]
    ) -> Dict[str, List[str]]:
        adj: Dict[str, List[str]] = {}
        for key1, (r1, c1, _, _) in coords.items():
            if key1 == " ":
                continue
            neighbors = []
            for key2, (r2, c2, _, _) in coords.items():
                if key1 == key2 or key2 == " ":
                    continue
                # Manhattan-like or Euclidean key distance
                dist = math.hypot(r1 - r2, c1 - c2)
                # Adjacent keys are roughly within ~1.4 units
                if dist <= 1.45:
                    neighbors.append(key2)
            adj[key1] = neighbors
        return adj

    def get_info(
        self, char: str
    ) -> Optional[Tuple[int, float, bool, int, str]]:
        """Returns (row, col, is_left_hand, finger, layout_name) for a character."""
        lower = char.lower()
        if lower in KEY_COORDINATES_US:
            r, c, left, finger = KEY_COORDINATES_US[lower]
            return (r, c, left, finger, "us")
        if lower in KEY_COORDINATES_RU:
            r, c, left, finger = KEY_COORDINATES_RU[lower]
            return (r, c, left, finger, "ru")
        return None

    def get_distance(self, char1: str, char2: str) -> float:
        """Returns physical keyboard distance between two characters."""
        info1 = self.get_info(char1)
        info2 = self.get_info(char2)
        if not info1 or not info2:
            return 2.0  # Default neutral distance
        r1, c1, _, _, _ = info1
        r2, c2, _, _, _ = info2
        return math.hypot(r1 - r2, c1 - c2)

    def is_same_hand(self, char1: str, char2: str) -> Optional[bool]:
        """Returns True if typed by the same hand, False if opposite hand."""
        info1 = self.get_info(char1)
        info2 = self.get_info(char2)
        if not info1 or not info2:
            return None
        return info1[2] == info2[2]

    def is_same_finger(self, char1: str, char2: str) -> Optional[bool]:
        """Returns True if typed by the exact same finger."""
        info1 = self.get_info(char1)
        info2 = self.get_info(char2)
        if not info1 or not info2:
            return None
        return (info1[2] == info2[2]) and (info1[3] == info2[3])

    def get_adjacent_keys(self, char: str) -> List[str]:
        """Returns a list of neighboring physical keys."""
        lower = char.lower()
        if lower in self.adjacencies_us:
            res = self.adjacencies_us[lower]
            return (
                [k.upper() for k in res] if char.isupper() else list(res)
            )
        if lower in self.adjacencies_ru:
            res = self.adjacencies_ru[lower]
            return (
                [k.upper() for k in res] if char.isupper() else list(res)
            )
        return []
