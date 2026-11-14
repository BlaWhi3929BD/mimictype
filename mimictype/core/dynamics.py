import math
import random
from typing import Optional
from mimictype.config import MimicConfig
from mimictype.core.topology import KeyboardTopology


class DynamicsEngine:
    """Computes realistic keystroke intervals (Dwell & Flight Times) dynamically calibrated to target WPM."""

    def __init__(
        self,
        config: MimicConfig,
        topology: Optional[KeyboardTopology] = None,
    ):
        self.config = config
        self.topology = topology or KeyboardTopology()

        # Words Per Minute to base character period:
        # Standard: 1 word = 5 characters.
        # Total time budget per character = 60.0 / (wpm * 5)
        wpm = max(10, self.config.wpm)
        self.char_period = 60.0 / (wpm * 5.0)

        cfg_dwell = self.config.dwell
        cfg_median_dwell = math.exp(cfg_dwell.mu) / 1000.0
        max_dwell_budget = self.char_period * 0.75

        if cfg_median_dwell <= max_dwell_budget:
            self.dwell_mu = cfg_dwell.mu
            self.dwell_sigma = cfg_dwell.sigma
            self.min_dwell = max(0.004, cfg_dwell.min_seconds)
            self.max_dwell = max(self.min_dwell, cfg_dwell.max_seconds)
            self.target_dwell = max(self.min_dwell, min(self.max_dwell, cfg_median_dwell))
        else:
            # Target speed is faster than configured dwell allows: scale proportionally
            scaled_dwell = self.char_period * 0.38
            scale_ratio = scaled_dwell / max(1e-6, cfg_median_dwell)
            self.target_dwell = scaled_dwell
            self.dwell_mu = math.log(max(1.0, scaled_dwell * 1000.0))
            self.dwell_sigma = cfg_dwell.sigma
            self.min_dwell = max(0.004, cfg_dwell.min_seconds * scale_ratio)
            self.max_dwell = max(self.min_dwell * 1.5, cfg_dwell.max_seconds * scale_ratio)

        self.base_flight = max(0.004, self.char_period - self.target_dwell)

        # Cognitive pause scaling: at high WPM, pauses scale down
        # At 65 WPM: scale = 1.0; at 333 WPM: scale ~ 0.17
        self.pause_scale = min(1.0, (65.0 / wpm) ** 1.15)

    def compute_dwell_time(self, char: str) -> float:
        """
        Lognormal distribution for key press duration (Dwell Time).
        ln(T) ~ N(mu, sigma^2), dynamically scaled to target WPM.
        """
        dwell_ms = math.exp(random.gauss(self.dwell_mu, self.dwell_sigma))
        dwell_sec = dwell_ms / 1000.0

        # Spacebar / Enter have slightly longer dwell
        if char in (" ", "\n"):
            dwell_sec *= random.uniform(1.08, 1.22)

        return max(self.min_dwell, min(self.max_dwell, dwell_sec))

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
            return max(0.010, self.base_flight * random.uniform(0.9, 1.4))

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
            dist_factor = 0.88 + (dist * 0.08)
            multiplier = random.uniform(min_m, max_m) * dist_factor

        flight_sec = self.base_flight * multiplier
        # Add random jitter
        jitter = random.gauss(0, flight_sec * cfg_flight.jitter_ratio)
        flight_sec += jitter

        min_flight = max(0.003, self.base_flight * 0.25)
        return max(min_flight, flight_sec)

    def compute_cognitive_pause(
        self, prev_char: Optional[str], curr_char: str, peek_ahead: str = ""
    ) -> float:
        """
        Calculates context-sensitive pauses before punctuation, newlines, and code constructs.
        Scaled proportionally to target WPM.
        """
        pauses = self.config.pauses

        # If WPM is extremely high (>250), eliminate cognitive pauses to prioritize raw speed
        if self.config.wpm >= 280:
            scale = self.pause_scale * 0.4
        else:
            scale = self.pause_scale

        # Sentence endings
        if curr_char in (".", "!", "?") and (
            not peek_ahead or peek_ahead[0] in (" ", "\n")
        ):
            return random.uniform(*pauses.sentence_boundary) * scale

        # Clauses
        if curr_char in (",", ";", ":"):
            return random.uniform(*pauses.clause_boundary) * scale

        # Newline
        if curr_char == "\n":
            return random.uniform(*pauses.newline) * scale

        # Structural code tokens: check if we are starting a known keyword or block
        if curr_char in ("{", "}"):
            return random.uniform(*pauses.code_block) * scale

        code_keywords = (
            "def ",
            "class ",
            "function ",
            "return ",
            "if ",
            "else:",
            "elif ",
        )
        is_word_start = prev_char is None or not (
            prev_char.isalnum() or prev_char == "_"
        )
        if is_word_start:
            token_prefix = curr_char + peek_ahead
            if any(token_prefix.startswith(kw) for kw in code_keywords):
                return random.uniform(*pauses.code_block) * scale

        return 0.0
