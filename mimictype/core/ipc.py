import json
import os
from pathlib import Path
import socket
import threading
from typing import Any, Callable, Dict, Optional


def get_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and Path(runtime_dir).exists():
        base = Path(runtime_dir) / "mimictype"
    else:
        base = Path.home() / ".cache" / "mimictype"
    base.mkdir(parents=True, exist_ok=True)
    return base / "daemon.sock"


class IPCServer:
    """Unix Domain Socket server for remote control of MimicType daemon."""

    def __init__(self, handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self.socket_path = get_socket_path()
        self.handler = handler
        self._server_sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self.socket_path.exists():
            # Check if an existing daemon is active
            if IPCClient.ping():
                raise RuntimeError(
                    f"Another MimicType daemon is already running at {self.socket_path}"
                )
            self.socket_path.unlink()

        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.bind(str(self.socket_path))
        self._server_sock.listen(5)
        self._server_sock.settimeout(0.5)
        self._running = True

        self._thread = threading.Thread(
            target=self._serve_loop, daemon=True, name="mimictype-ipc-server"
        )
        self._thread.start()

    def _serve_loop(self):
        while self._running and self._server_sock:
            try:
                conn, _ = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            with conn:
                try:
                    data = conn.recv(65536)
                    if data:
                        req = json.loads(data.decode("utf-8"))
                        resp = self.handler(req)
                        conn.sendall(json.dumps(resp).encode("utf-8"))
                except Exception as e:
                    try:
                        conn.sendall(
                            json.dumps({"error": str(e)}).encode("utf-8")
                        )
                    except Exception:
                        pass

    def stop(self):
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except Exception:
                pass


class IPCClient:
    """Client helper to talk to running MimicType daemon."""

    @classmethod
    def send(
        cls, command: str, payload: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        sock_path = get_socket_path()
        if not sock_path.exists():
            return None

        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(2.0)
        try:
            client.connect(str(sock_path))
            msg = {"command": command}
            if payload:
                msg.update(payload)
            client.sendall(json.dumps(msg).encode("utf-8"))
            raw = client.recv(65536)
            if raw:
                return json.loads(raw.decode("utf-8"))
        except Exception:
            return None
        finally:
            client.close()
        return None

    @classmethod
    def ping(cls) -> bool:
        resp = cls.send("PING")
        return bool(resp and resp.get("status") == "PONG")
