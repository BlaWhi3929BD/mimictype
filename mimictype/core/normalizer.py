import unicodedata
from typing import Dict


# Translation table for common unicode characters that don't have direct keys on standard layouts
UNICODE_REPLACEMENTS: Dict[str, str] = {
    # Quotes
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "„": '"',
    "‘": "'",
    "’": "'",
    "‚": "'",
    "ʻ": "'",
    "ʼ": "'",
    # Dashes and hyphens
    "—": "--",  # Em-dash
    "–": "-",  # En-dash
    "−": "-",  # Minus sign
    "‑": "-",  # Non-breaking hyphen
    "‒": "-",  # Figure dash
    # Spaces
    "\u00a0": " ",  # Non-breaking space
    "\u2000": " ",  # En quad
    "\u2001": " ",  # Em quad
    "\u2002": " ",  # En space
    "\u2003": " ",  # Em space
    "\u2004": " ",  # Three-per-em space
    "\u2005": " ",  # Four-per-em space
    "\u2006": " ",  # Six-per-em space
    "\u2007": " ",  # Figure space
    "\u2008": " ",  # Punctuation space
    "\u2009": " ",  # Thin space
    "\u200a": " ",  # Hair space
    "\u202f": " ",  # Narrow no-break space
    "\u205f": " ",  # Medium mathematical space
    "\u3000": " ",  # Ideographic space
    # Zero-width characters (to be stripped)
    "\u200b": "",  # Zero-width space
    "\u200c": "",  # Zero-width non-joiner
    "\u200d": "",  # Zero-width joiner
    "\ufeff": "",  # Byte order mark / zero-width no-break space
    # Ellipsis
    "…": "...",
    # Bullets
    "•": "*",
    "◦": "*",
    "·": "*",
    # Kazakh letters fallback (if not on standard RU keyboard layout)
    "ә": "а",
    "Ә": "А",
    "ғ": "г",
    "Ғ": "Г",
    "қ": "к",
    "Қ": "К",
    "ң": "н",
    "Ң": "Н",
    "ө": "о",
    "Ө": "О",
    "ұ": "у",
    "Ұ": "У",
    "ү": "у",
    "Ү": "У",
    "һ": "х",
    "Һ": "Х",
    "і": "и",
    "І": "И",
}


class TextNormalizer:
    """Normalizes clipboard text, replacing non-standard unicode characters with typeable counterparts."""

    @classmethod
    def normalize(cls, text: str, preserve_kazakh: bool = False) -> str:
        if not text:
            return ""

        # Normalize line endings to standard Unix LF
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Decompose accents / combining diacritics if necessary
        text = unicodedata.normalize("NFC", text)

        out = []
        for char in text:
            if preserve_kazakh and char in "әӘғҒқҚңҢөӨұҰүҮһҺіІ":
                out.append(char)
            elif char in UNICODE_REPLACEMENTS:
                out.append(UNICODE_REPLACEMENTS[char])
            else:
                out.append(char)

        return "".join(out)
