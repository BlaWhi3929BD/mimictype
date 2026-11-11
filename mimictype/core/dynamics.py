import math
import random
from typing import Optional
from mimictype.config import MimicConfig
from mimictype.core.topology import KeyboardTopology


class DynamicsEngine:
    """Computes realistic human keystroke intervals (Dwell & Flight Times)."""

    def __init__(
        self,
        config: MimicConfig,
        topology: Optional[KeyboardTopology] = None,
    ):
        self.config = config
        self.topology = topology or KeyboardTopology()
        # Words Per Minute to base character flight time conversion:
        # Standard assumption: 1 word = 5 characters.
        # Characters per minute = wpm * 5. Total time per char = 60 / (wpm * 5).
        # We divide that roughly into dwell (~40%) and flight (~60%).
        char_period = 60.0 / max(10, self.config.wpm * 5)
        self.base_flight = char_period * 0.60

    def compute_dwell_time(self, char: str) -> float:
        """
        Lognormal distribution for key press duration (Dwell Time).
        ln(T) ~ N(mu, sigma^2).
        """
        mu = self.config.dwell.mu
        sigma = self.config.dwell.sigma
        # Sample lognormal distribution in ms
        dwell_ms = math.exp(random.gauss(mu, sigma))
        dwell_sec = dwell_ms / 1000.0

        # Spacebar / Enter often have slightly longer dwell
        if char in (" ", "\n"):
            dwell_sec *= random.uniform(1.1, 1.3)

        return max(
            self.config.dwell.min_seconds,
            min(self.config.dwell.max_seconds, dwell_sec),
        )

    def compute_flight_time(
        self, prev_char: Optional[str], curr_char: str
    ) -> float:
        """
        Biomechanical flight time between key-up of prev_char and key-down of curr_char.
        Accounts for:
        - Same key repeated (Double tap)
        - Same finger transitions
        - Alternate hand speedup
        - Spatial physical distance
        """
        if not prev_char:
            return random.uniform(0.08, 0.18)

        cfg_flight = self.config.flight

        # 1. Double tap (repeated key)
        if prev_char == curr_char:
            min_m, max_m = cfg_flight.double_tap_multiplier_range
            multiplier = random.uniform(min_m, max_m)
        # 2. Check hand and finger ergonomics
        elif self.topology.is_same_finger(prev_char, curr_char):
            # Same finger has to physically travel
            min_m, max_m = cfg_flight.same_finger_multiplier_range
            multiplier = random.uniform(min_m, max_m)
        elif self.topology.is_same_hand(prev_char, curr_char) is False:
            # Opposite hands prepare in advance (anticipatory movement)
            min_m, max_m = cfg_flight.opposite_hand_multiplier_range
            multiplier = random.uniform(min_m, max_m)
        else:
            # Same hand, different fingers
            min_m, max_m = cfg_flight.same_hand_multiplier_range
            dist = self.topology.get_distance(prev_char, curr_char)
            # Slight scaling with distance
            dist_factor = 0.85 + (dist * 0.10)
            multiplier = random.uniform(min_m, max_m) * dist_factor

        flight_sec = self.base_flight * multiplier
        # Add random jitter
        jitter = random.gauss(0, flight_sec * cfg_flight.jitter_ratio)
        flight_sec += jitter

        return max(0.025, flight_sec)

    def compute_cognitive_pause(
        self, prev_char: Optional[str], curr_char: str, peek_ahead: str = ""
    ) -> float:
        """
        Calculates context-sensitive pauses before punctuation, newlines, and code constructs.
        """
        pauses = self.config.pauses

        # Sentence endings
        if curr_char in (".", "!", "?") and (
            not peek_ahead or peek_ahead[0] in (" ", "\n")
        ):
            return random.uniform(*pauses.sentence_boundary)

        # Clauses
        if curr_char in (",", ";", ":"):
            return random.uniform(*pauses.clause_boundary)

        # Newline
        if curr_char == "\n":
            return random.uniform(*pauses.newline)

        # Structural code tokens: check if we are starting a known keyword or block
        if curr_char in ("{", "}"):
            return random.uniform(*pauses.code_block)

        code_keywords = (
            "def ",
            "class ",
            "function ",
            "return ",
            "if ",
            "else:",
            "elif ",
        )
        if any(
            peek_ahead.startswith(kw) or (curr_char + peek_ahead).startswith(kw)
            for kw in code_keywords
        ):
            return random.uniform(*pauses.code_block)

        return 0.0
