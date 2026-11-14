import ctypes
import json
import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional


_XKB_USE_CORE_KBD = 0x0100


class _XkbStateRec(ctypes.Structure):
    _fields_ = [
        ("group", ctypes.c_ubyte),
        ("locked_group", ctypes.c_ubyte),
        ("base_group", ctypes.c_ushort),
        ("latched_group", ctypes.c_ushort),
        ("mods", ctypes.c_ubyte),
        ("base_mods", ctypes.c_ubyte),
        ("latched_mods", ctypes.c_ubyte),
        ("locked_mods", ctypes.c_ubyte),
        ("compat_state", ctypes.c_ubyte),
        ("grab_mods", ctypes.c_ubyte),
        ("compat_grab_mods", ctypes.c_ubyte),
        ("lookup_mods", ctypes.c_ubyte),
        ("compat_lookup_mods", ctypes.c_ubyte),
        ("ptr_buttons", ctypes.c_ushort),
    ]


class LayoutDetector:
    """
    Detects and controls the active keyboard layout using:
    1. KDE Plasma DBus (Wayland & X11)
    2. xkb-switch / X11 XKB state (X11 / Xephyr)
    3. Hardware key simulation fallback (handled by TyperEngine)
    """

    def __init__(self):
        self._kde_layouts_map: Optional[Dict[str, int]] = None
        self._detect_kde_support()

    @staticmethod
    def _parse_kde_layouts(raw: str) -> Optional[Dict[str, int]]:
        layouts: Dict[str, int] = {}

        try:
            payload = json.loads(raw)
            data = payload.get("data", [])
            entries = data[0] if data and isinstance(data[0], list) else []
            for idx, entry in enumerate(entries):
                if isinstance(entry, (list, tuple)) and entry:
                    code = str(entry[0]).strip().lower()
                    if code:
                        layouts.setdefault(code, idx)
            if layouts:
                return layouts
        except (json.JSONDecodeError, TypeError, ValueError, IndexError):
            pass

        # Fallback for plain GVariant busctl text output (supports non-empty variants & escaped quotes)
        triples = re.findall(
            r'"([a-zA-Z0-9_-]+)"\s+"([^"]*)"\s+"(?:[^"\\]|\\.)*"',
            raw,
        )
        for idx, (code, _variant) in enumerate(triples):
            normalized = code.strip().lower()
            if normalized:
                layouts.setdefault(normalized, idx)

        return layouts or None

    @staticmethod
    def _parse_kde_active_index(raw: str) -> Optional[int]:
        try:
            payload = json.loads(raw)
            data = payload.get("data", [])
            if data and isinstance(data[0], int):
                return data[0]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        m = re.search(r"\bu\s+(\d+)", raw)
        if m:
            return int(m.group(1))
        return None

    def _detect_kde_support(self):
        """Checks if KDE Plasma keyboard DBus service is responsive and parses layouts."""
        if not shutil.which("busctl"):
            self._kde_layouts_map = None
            return

        try:
            res = subprocess.run(
                [
                    "busctl",
                    "--user",
                    "--json=short",
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
                self._kde_layouts_map = self._parse_kde_layouts(res.stdout)
            else:
                self._kde_layouts_map = None
        except Exception:
            self._kde_layouts_map = None

    def _get_kde_active_layout(self) -> Optional[str]:
        if self._kde_layouts_map is None:
            self._detect_kde_support()
        if not self._kde_layouts_map or not shutil.which("busctl"):
            return None

        try:
            res = subprocess.run(
                [
                    "busctl",
                    "--user",
                    "--json=short",
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
            if res.returncode != 0 or not res.stdout:
                return None

            idx = self._parse_kde_active_index(res.stdout)
            if idx is None:
                return None

            for code, mapped_idx in self._kde_layouts_map.items():
                if mapped_idx == idx:
                    return code

            # Layout list may have changed dynamically; refresh once
            self._detect_kde_support()
            if self._kde_layouts_map:
                for code, mapped_idx in self._kde_layouts_map.items():
                    if mapped_idx == idx:
                        return code
        except Exception:
            pass

        return None

    @staticmethod
    def _load_x11():
        x11 = ctypes.CDLL("libX11.so.6")
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.restype = ctypes.c_int
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XFlush.restype = ctypes.c_int
        x11.XkbGetState.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.POINTER(_XkbStateRec),
        ]
        x11.XkbGetState.restype = ctypes.c_int
        x11.XkbLockGroup.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        x11.XkbLockGroup.restype = ctypes.c_int
        return x11

    @staticmethod
    def _get_x11_layouts() -> List[str]:
        if not (shutil.which("setxkbmap") and os.environ.get("DISPLAY")):
            return []
        try:
            res = subprocess.run(
                ["setxkbmap", "-query"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.0,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                m = re.search(r"^layout:\s+([^\s]+)", res.stdout, re.MULTILINE)
                if m:
                    return [
                        part.split("(")[0].strip().lower()
                        for part in m.group(1).split(",")
                        if part.strip()
                    ]
        except Exception:
            pass
        return []

    def _get_x11_active_group(self) -> Optional[int]:
        if shutil.which("xkblayout-state") and os.environ.get("DISPLAY"):
            try:
                res = subprocess.run(
                    ["xkblayout-state", "print", "%c"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.0,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip().isdigit():
                    return int(res.stdout.strip())
            except Exception:
                pass

        if os.environ.get("DISPLAY"):
            dpy = None
            x11 = None
            try:
                x11 = self._load_x11()
                dpy = x11.XOpenDisplay(None)
                if dpy:
                    state = _XkbStateRec()
                    if x11.XkbGetState(dpy, _XKB_USE_CORE_KBD, ctypes.byref(state)) == 0:
                        return int(state.group)
            except Exception:
                pass
            finally:
                if x11 is not None and dpy:
                    x11.XCloseDisplay(dpy)
        return None

    def get_active_layout(self) -> Optional[str]:
        """Returns the current active layout (e.g. 'us', 'ru') if detectable."""
        # 1. Try KDE DBus (works on both KDE Wayland and KDE X11)
        kde_layout = self._get_kde_active_layout()
        if kde_layout:
            return kde_layout

        # 2. Try xkb-switch / X11 XKB state only outside native Wayland sessions
        if not os.environ.get("WAYLAND_DISPLAY"):
            if shutil.which("xkb-switch") and os.environ.get("DISPLAY"):
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
                        return res.stdout.strip().split("(")[0].strip().lower()
                except Exception:
                    pass

            layouts = self._get_x11_layouts()
            if layouts:
                group = self._get_x11_active_group()
                if group is not None and 0 <= group < len(layouts):
                    return layouts[group]
                if len(layouts) == 1:
                    return layouts[0]

        return None

    def switch_layout_direct(self, target_layout: str) -> bool:
        """
        Attempts to directly set the target layout using desktop APIs.
        Returns True if successful, False if fallback key combinations must be used.
        """
        target = target_layout.lower()

        # 1. KDE DBus setLayout
        if self._kde_layouts_map is None:
            self._detect_kde_support()
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

        # 2. X11 direct APIs (only when not under Wayland/Xwayland)
        if not os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
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

            layouts = self._get_x11_layouts()
            if target in layouts:
                target_idx = layouts.index(target)
                dpy = None
                x11 = None
                try:
                    x11 = self._load_x11()
                    dpy = x11.XOpenDisplay(None)
                    if dpy and x11.XkbLockGroup(dpy, _XKB_USE_CORE_KBD, target_idx) != 0:
                        x11.XFlush(dpy)
                        return True
                except Exception:
                    pass
                finally:
                    if x11 is not None and dpy:
                        x11.XCloseDisplay(dpy)

        return False
