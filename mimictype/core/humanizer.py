from dataclasses import dataclass
from enum import Enum, auto
import random
from typing import Generator, List, Optional, Tuple
from mimictype.config import MimicConfig
from mimictype.core.mapper import LayoutMapper
from mimictype.core.topology import KeyboardTopology


class ActionType(Enum):
    TYPE_CHAR = auto()
    BACKSPACE = auto()
    PAUSE = auto()
    SWITCH_LAYOUT = auto()


@dataclass
class TypingStep:
    action: ActionType
    char: Optional[str] = None
    duration: float = 0.0
    description: str = ""
    peek_ahead: str = ""
    is_typo: bool = False


class HumanizerEngine:
    """
    Transforms a clean string into a realistic stream of typing actions,
    injecting human typos, motor inertia, realization pauses, and Backspace corrections.
    Dynamically scales all delays with target WPM.
    """

    def __init__(
        self,
        config: MimicConfig,
        topology: Optional[KeyboardTopology] = None,
        mapper: Optional[LayoutMapper] = None,
    ):
        self.config = config
        self.topology = topology or KeyboardTopology()
        self.mapper = mapper or LayoutMapper(self.config.layout.default_layout)
        wpm = max(10, self.config.wpm)
        self.char_period = 60.0 / (wpm * 5.0)
        self.wpm_scale = min(1.0, (65.0 / wpm) ** 1.1)

    def generate_steps(self, text: str) -> Generator[TypingStep, None, None]:
        """
        Processes text and yields a sequence of typing steps (characters, typos, backspaces, pauses).
        """
        i = 0
        n = len(text)
        cfg_h = self.config.humanizer

        # Dynamically scale Backspace dwell/flight and pauses to WPM
        bs_dwell = max(0.006, min(cfg_h.backspace_dwell, self.char_period * 0.35))
        bs_flight = max(0.006, min(cfg_h.backspace_flight, self.char_period * 0.45))

        while i < n:
            curr_char = text[i]

            # Don't make typos on whitespace, unsupported characters, or outside error_rate
            if (
                not cfg_h.enabled
                or curr_char in ("\n", "\t", " ")
                or not self.mapper.is_supported(curr_char)
                or random.random() >= cfg_h.error_rate
            ):
                yield TypingStep(
                    action=ActionType.TYPE_CHAR,
                    char=curr_char,
                    peek_ahead=text[i + 1 : i + 17],
                )
                i += 1
                continue

            # Typo occurred! Choose between Transposition and Fat-finger
            adjacent_keys = [
                k
                for k in self.topology.get_adjacent_keys(curr_char)
                if self.mapper.is_supported(k)
            ]
            can_transpose = (
                (i + 1 < n)
                and (text[i + 1] not in ("\n", "\t"))
                and (text[i + 1] != curr_char)
                and self.mapper.is_supported(text[i + 1])
            )
            is_transposition = (
                can_transpose and random.random() < cfg_h.transposition_rate
            )

            if is_transposition:
                # Transposition: type text[i+1] then text[i], then realize and fix
                next_char = text[i + 1]
                yield TypingStep(
                    action=ActionType.TYPE_CHAR,
                    char=next_char,
                    description="typo_transpose_1",
                    is_typo=True,
                )
                yield TypingStep(
                    action=ActionType.TYPE_CHAR,
                    char=curr_char,
                    description="typo_transpose_2",
                    is_typo=True,
                )

                # Realization pause (scaled by WPM)
                pause = random.uniform(*cfg_h.perception_delay) * self.wpm_scale
                yield TypingStep(
                    action=ActionType.PAUSE,
                    duration=pause,
                    description="transposition_perception_pause",
                )

                # Send 2 Backspaces
                for _ in range(2):
                    yield TypingStep(
                        action=ActionType.BACKSPACE,
                        duration=bs_dwell,
                    )
                    yield TypingStep(
                        action=ActionType.PAUSE,
                        duration=bs_flight,
                    )

                # Recovery pause
                rec_pause = random.uniform(*cfg_h.recovery_delay) * self.wpm_scale
                yield TypingStep(
                    action=ActionType.PAUSE,
                    duration=rec_pause,
                    description="recovery_pause",
                )

                # Now type correctly
                yield TypingStep(
                    action=ActionType.TYPE_CHAR,
                    char=curr_char,
                    description="corrected_char",
                    peek_ahead=text[i + 1 : i + 17],
                )
                yield TypingStep(
                    action=ActionType.TYPE_CHAR,
                    char=next_char,
                    description="corrected_char",
                    peek_ahead=text[i + 2 : i + 18],
                )
                i += 2
                continue

            elif adjacent_keys:
                # Fat-finger: press an adjacent key
                wrong_char = random.choice(adjacent_keys)
                yield TypingStep(
                    action=ActionType.TYPE_CHAR,
                    char=wrong_char,
                    description="typo_fat_finger",
                    is_typo=True,
                )

                # Motor inertia: type 0 to 2 following supported characters before noticing
                min_in, max_in = cfg_h.inertia_range
                inertia_count = random.randint(min_in, max_in)
                typed_inertia: List[str] = []

                for offset in range(1, inertia_count + 1):
                    if i + offset < n:
                        inertia_char = text[i + offset]
                        if inertia_char not in ("\n", "\t") and self.mapper.is_supported(inertia_char):
                            typed_inertia.append(inertia_char)
                            yield TypingStep(
                                action=ActionType.TYPE_CHAR,
                                char=inertia_char,
                                description="inertia_char",
                                is_typo=True,
                            )
                        else:
                            break
                    else:
                        break

                # Realization pause (scaled by WPM)
                pause = random.uniform(*cfg_h.perception_delay) * self.wpm_scale
                yield TypingStep(
                    action=ActionType.PAUSE,
                    duration=pause,
                    description="fat_finger_perception_pause",
                )

                # Backspace everything wrong (the typo + all inertia characters)
                backspaces_needed = 1 + len(typed_inertia)
                for _ in range(backspaces_needed):
                    yield TypingStep(
                        action=ActionType.BACKSPACE,
                        duration=bs_dwell,
                    )
                    yield TypingStep(
                        action=ActionType.PAUSE,
                        duration=bs_flight,
                    )

                # Recovery pause
                rec_pause = random.uniform(*cfg_h.recovery_delay) * self.wpm_scale
                yield TypingStep(
                    action=ActionType.PAUSE,
                    duration=rec_pause,
                    description="recovery_pause",
                )

                # Type correct current char
                yield TypingStep(
                    action=ActionType.TYPE_CHAR,
                    char=curr_char,
                    description="corrected_char",
                    peek_ahead=text[i + 1 : i + 17],
                )

                i += 1
                continue

            else:
                yield TypingStep(
                    action=ActionType.TYPE_CHAR,
                    char=curr_char,
                    peek_ahead=text[i + 1 : i + 17],
                )
                i += 1
