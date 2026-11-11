import os
import shutil
import subprocess
from typing import Optional


class ClipboardReader:
    """Reads text from system clipboard supporting both Wayland and X11 environments."""

    @staticmethod
    def is_wayland() -> bool:
        return bool(os.environ.get("WAYLAND_DISPLAY"))

    @classmethod
    def get_text(cls) -> Optional[str]:
        """Reads text from the primary clipboard."""
        # 1. Try Wayland wl-paste if Wayland session is detected
        if cls.is_wayland() and shutil.which("wl-paste"):
            try:
                res = subprocess.run(
                    ["wl-paste", "--no-newline"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                if res.returncode == 0 and res.stdout:
                    return res.stdout
            except Exception:
                pass

        # 2. Try xclip (works in X11 and inside Xephyr / Xwayland)
        if shutil.which("xclip"):
            try:
                res = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                if res.returncode == 0 and res.stdout:
                    return res.stdout
            except Exception:
                pass

        # 3. Try xsel
        if shutil.which("xsel"):
            try:
                res = subprocess.run(
                    ["xsel", "-b", "-o"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                if res.returncode == 0 and res.stdout:
                    return res.stdout
            except Exception:
                pass

        # 4. Fallback: try python Gtk if available
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            gi.require_version("Gdk", "3.0")
            from gi.repository import Gdk, Gtk

            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            text = clipboard.wait_for_text()
            if text:
                return text
        except Exception:
            pass

        return None
