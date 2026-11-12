import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple


class LayoutDetector:
    """
    Detects and controls the active keyboard layout using:
    1. KDE Plasma DBus (Wayland & X11)
    2. setxkbmap / xkb-switch (X11 / Xephyr)
    3. Hardware key simulation fallback (Alt+Shift, CapsLock, etc.)
    """

    def __init__(self):
        self._kde_layouts_map: Optional[Dict[str, int]] = None
        self._detect_kde_support()

    def _detect_kde_support(self):
        """Checks if KDE Plasma keyboard DBus service is responsive."""
        if not shutil.which("busctl"):
            return

        try:
            res = subprocess.run(
                [
                    "busctl",
                    "--user",
                    "call",
                    "org.kde.keyboard",
                    "/Layouts",
                    "org.kde.KeyboardLayouts",
                    "getLayoutsList",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.0,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                # Matches: "us" "" "English (US)" "ru" "" "Russian"
                raw = res.stdout
                matches = re.findall(r'"([a-zA-Z]{2})"\s+""\s+"[^"]+"', raw)
                if matches:
                    self._kde_layouts_map = {
                        code.lower(): idx for idx, code in enumerate(matches)
                    }
        except Exception:
            self._kde_layouts_map = None

    def get_active_layout(self) -> Optional[str]:
        """Returns the current active layout (e.g. 'us', 'ru') if detectable."""
        # 1. Try KDE DBus
        if self._kde_layouts_map:
            try:
                res = subprocess.run(
                    [
                        "busctl",
                        "--user",
                        "call",
                        "org.kde.keyboard",
                        "/Layouts",
                        "org.kde.KeyboardLayouts",
                        "getLayout",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.0,
                    check=False,
                )
                if res.returncode == 0:
                    # Output format: "u 1"
                    m = re.search(r"u\s+(\d+)", res.stdout)
                    if m:
                        idx = int(m.group(1))
                        # Reverse lookup index -> code
                        for code, mapped_idx in self._kde_layouts_map.items():
                            if mapped_idx == idx:
                                return code
            except Exception:
                pass

        # 2. Try xkb-switch
        if shutil.which("xkb-switch"):
            try:
                res = subprocess.run(
                    ["xkb-switch", "-p"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.0,
                    check=False,
                )
                if res.returncode == 0 and res.stdout:
                    return res.stdout.strip().lower()[:2]
            except Exception:
                pass

        # 3. Try setxkbmap (in X11)
        if shutil.which("setxkbmap") and os.environ.get("DISPLAY"):
            try:
                res = subprocess.run(
                    ["setxkbmap", "-query"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.0,
                    check=False,
                )
                if res.returncode == 0:
                    m = re.search(r"layout:\s+([a-zA-Z]+)", res.stdout)
                    if m:
                        return m.group(1).lower()[:2]
            except Exception:
                pass

        return None

    def switch_layout_direct(self, target_layout: str) -> bool:
        """
        Attempts to directly set the target layout using desktop APIs.
        Returns True if successful, False if fallback key combinations must be used.
        """
        target = target_layout.lower()

        # 1. KDE DBus setLayout
        if self._kde_layouts_map and target in self._kde_layouts_map:
            target_idx = self._kde_layouts_map[target]
            try:
                res = subprocess.run(
                    [
                        "busctl",
                        "--user",
                        "call",
                        "org.kde.keyboard",
                        "/Layouts",
                        "org.kde.KeyboardLayouts",
                        "setLayout",
                        "u",
                        str(target_idx),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.0,
                    check=False,
                )
                if res.returncode == 0:
                    return True
            except Exception:
                pass

        # 2. xkb-switch
        if shutil.which("xkb-switch"):
            try:
                res = subprocess.run(
                    ["xkb-switch", "-s", target],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                    check=False,
                )
                if res.returncode == 0:
                    return True
            except Exception:
                pass

        return False
