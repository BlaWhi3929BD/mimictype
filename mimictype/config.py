from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple
import yaml


@dataclass
class DwellConfig:
    mu: float = 4.31
    sigma: float = 0.20
    min_seconds: float = 0.045
    max_seconds: float = 0.145


@dataclass
class FlightConfig:
    jitter_ratio: float = 0.15
    double_tap_multiplier_range: Tuple[float, float] = (1.3, 1.8)
    same_finger_multiplier_range: Tuple[float, float] = (1.3, 1.7)
    opposite_hand_multiplier_range: Tuple[float, float] = (0.65, 0.90)
    same_hand_multiplier_range: Tuple[float, float] = (0.95, 1.30)


@dataclass
class PausesConfig:
    sentence_boundary: Tuple[float, float] = (0.35, 0.75)
    clause_boundary: Tuple[float, float] = (0.18, 0.38)
    newline: Tuple[float, float] = (0.40, 1.10)
    code_block: Tuple[float, float] = (0.30, 0.60)


@dataclass
class HumanizerConfig:
    enabled: bool = True
    error_rate: float = 0.02
    transposition_rate: float = 0.15
    inertia_range: Tuple[int, int] = (0, 2)
    perception_delay: Tuple[float, float] = (0.22, 0.45)
    backspace_dwell: float = 0.045
    backspace_flight: float = 0.065
    recovery_delay: Tuple[float, float] = (0.12, 0.25)


@dataclass
class DeviceConfig:
    name: str = "Logitech USB Keyboard"
    vendor_id: int = 0x046D
    product_id: int = 0xC31C
    version: int = 0x0111


@dataclass
class LayoutConfig:
    default_layout: str = "us"
    switch_key_combination: List[str] = field(
        default_factory=lambda: ["KEY_LEFTALT", "KEY_LEFTSHIFT"]
    )
    switch_settle_delay: float = 0.060


@dataclass
class MimicConfig:
    wpm: int = 65
    dwell: DwellConfig = field(default_factory=DwellConfig)
    flight: FlightConfig = field(default_factory=FlightConfig)
    pauses: PausesConfig = field(default_factory=PausesConfig)
    humanizer: HumanizerConfig = field(default_factory=HumanizerConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "MimicConfig":
        if path is None:
            default_path = (
                Path(__file__).parent.parent / "config" / "default.yaml"
            )
            if default_path.exists():
                path = default_path
            else:
                return cls()

        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        dwell_data = data.get("dwell", {})
        flight_data = data.get("flight", {})
        pauses_data = data.get("pauses", {})
        humanizer_data = data.get("humanizer", {})
        device_data = data.get("device", {})
        layout_data = data.get("layout", {})

        return cls(
            wpm=data.get("wpm", 65),
            dwell=DwellConfig(**dwell_data) if dwell_data else DwellConfig(),
            flight=FlightConfig(
                jitter_ratio=flight_data.get("jitter_ratio", 0.15),
                double_tap_multiplier_range=tuple(
                    flight_data.get("double_tap_multiplier_range", [1.3, 1.8])
                ),
                same_finger_multiplier_range=tuple(
                    flight_data.get("same_finger_multiplier_range", [1.3, 1.7])
                ),
                opposite_hand_multiplier_range=tuple(
                    flight_data.get(
                        "opposite_hand_multiplier_range", [0.65, 0.90]
                    )
                ),
                same_hand_multiplier_range=tuple(
                    flight_data.get("same_hand_multiplier_range", [0.95, 1.30])
                ),
            ),
            pauses=PausesConfig(
                sentence_boundary=tuple(
                    pauses_data.get("sentence_boundary", [0.35, 0.75])
                ),
                clause_boundary=tuple(
                    pauses_data.get("clause_boundary", [0.18, 0.38])
                ),
                newline=tuple(pauses_data.get("newline", [0.40, 1.10])),
                code_block=tuple(pauses_data.get("code_block", [0.30, 0.60])),
            ),
            humanizer=HumanizerConfig(
                enabled=humanizer_data.get("enabled", True),
                error_rate=humanizer_data.get("error_rate", 0.02),
                transposition_rate=humanizer_data.get(
                    "transposition_rate", 0.15
                ),
                inertia_range=tuple(
                    humanizer_data.get("inertia_range", [0, 2])
                ),
                perception_delay=tuple(
                    humanizer_data.get("perception_delay", [0.22, 0.45])
                ),
                backspace_dwell=humanizer_data.get("backspace_dwell", 0.045),
                backspace_flight=humanizer_data.get("backspace_flight", 0.065),
                recovery_delay=tuple(
                    humanizer_data.get("recovery_delay", [0.12, 0.25])
                ),
            ),
            device=DeviceConfig(**device_data)
            if device_data
            else DeviceConfig(),
            layout=LayoutConfig(**layout_data)
            if layout_data
            else LayoutConfig(),
        )
