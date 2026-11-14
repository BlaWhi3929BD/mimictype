import logging
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, Optional
from mimictype.config import MimicConfig
from mimictype.core.clipboard import ClipboardReader
from mimictype.core.engine import TyperEngine
from mimictype.core.ipc import IPCServer
from mimictype.core.listener import HotkeyListener

logger = logging.getLogger("mimictype.daemon")


def send_notification(summary: str, body: str = "", timeout_ms: int = 2000):
    """Dispatches a desktop notification asynchronously so callers never block."""
    if not shutil.which("notify-send"):
        return

    def _send():
        try:
            subprocess.run(
                ["notify-send", "-a", "MimicType", "-t", str(timeout_ms), summary, body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2.0,
                check=False,
            )
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True, name="mimictype-notify").start()


class MimicDaemon:
    """
    Background service for MimicType:
    - Listens for global hotkey without focus interruption.
    - Exposes Unix IPC socket for terminal & external script integration.
    - Monitors emergency Kill Switch (ESC).
    """

    def __init__(self, config: Optional[MimicConfig] = None, hotkey: str = "ctrl+alt+v"):
        self.config = config or MimicConfig.load()
        self.hotkey = hotkey
        self.engine: Optional[TyperEngine] = None
        self.listener: Optional[HotkeyListener] = None
        self.ipc_server: Optional[IPCServer] = None
        self._running = False
        self._typing_lock = threading.Lock()

    def start(self):
        """Starts the daemon services."""
        logger.info(f"Starting MimicType Daemon (Hotkey: {self.hotkey}, Target: {self.config.wpm} WPM)...")
        self.engine = TyperEngine(self.config)
        self.ipc_server = IPCServer(handler=self._handle_ipc_request)
        self.ipc_server.start()

        self.listener = HotkeyListener(
            hotkey_str=self.hotkey,
            on_trigger=self._on_hotkey_triggered,
            on_emergency_stop=self._on_emergency_stop,
            ignore_device_names=[self.config.device.name, "mimictype"],
        )
        listener_ok = self.listener.start()
        self._running = True

        if listener_ok:
            send_notification(
                "MimicType Daemon Active",
                f"Ready. Press {self.hotkey.upper()} to type.",
            )
        else:
            send_notification(
                "MimicType IPC Ready",
                "Global hotkey/ESC disabled (/dev/input unreadable). Use DE shortcuts with 'mimictype trigger'.",
            )
        logger.info("Daemon active and waiting for events.")

        try:
            while self._running:
                time.sleep(0.5)
        finally:
            self.stop()

    def stop(self):
        """Stops the daemon and cleans up all resources."""
        self._running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.ipc_server:
            self.ipc_server.stop()
            self.ipc_server = None
        if self.engine:
            self.engine.close()
            self.engine = None
        logger.info("Daemon stopped.")

    def trigger_typing(self, text: Optional[str] = None):
        """Asynchronously resolves text and executes typing without blocking the caller thread."""
        def _worker():
            if not self._typing_lock.acquire(blocking=False):
                send_notification("MimicType", "Typing already in progress!")
                return

            try:
                target_text = (
                    text if text is not None else ClipboardReader.get_text()
                )
                if not target_text:
                    msg = (
                        "No text provided."
                        if text is not None
                        else "Clipboard is empty!"
                    )
                    send_notification("MimicType", msg)
                    return

                char_count = len(target_text)
                send_notification(
                    "MimicType",
                    f"Typing {char_count} characters... (ESC to abort)",
                )
                success = self.engine.type_text(target_text)
                if success:
                    send_notification(
                        "MimicType", "Typing completed successfully."
                    )
                else:
                    send_notification("MimicType", "Typing aborted by user.")
            except Exception as e:
                send_notification("MimicType Error", str(e))
            finally:
                self._typing_lock.release()

        thread = threading.Thread(target=_worker, daemon=True, name="mimictype-worker")
        thread.start()

    def _on_hotkey_triggered(self):
        logger.info("Global hotkey triggered.")
        self.trigger_typing()

    def _on_emergency_stop(self):
        if self.engine and self.engine.is_typing:
            logger.info("Emergency Kill Switch triggered.")
            self.engine.abort()

    def _handle_ipc_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        cmd = req.get("command", "").upper()
        if cmd == "PING":
            return {"status": "PONG"}
        elif cmd == "STATUS":
            return {
                "status": "typing" if (self.engine and self.engine.is_typing) else "idle",
                "wpm": self.config.wpm,
                "hotkey": self.hotkey,
                "hotkey_active": bool(self.listener and self.listener.is_active),
                "hotkey_error": self.listener.last_error if self.listener else None,
            }
        elif cmd == "TYPE":
            text = req.get("text")
            self.trigger_typing(text)
            return {"status": "started"}
        elif cmd == "ABORT" or cmd == "STOP":
            if self.engine:
                self.engine.abort()
            return {"status": "aborted"}
        elif cmd == "QUIT":
            self._running = False
            return {"status": "shutting_down"}
        else:
            return {"error": f"Unknown command: {cmd}"}
