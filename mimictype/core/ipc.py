import json
import os
from pathlib import Path
import socket
import struct
import threading
from typing import Any, Callable, Dict, Optional


MAX_IPC_FRAME_BYTES = 16 * 1024 * 1024  # 16 MiB safety cap


def get_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and Path(runtime_dir).exists():
        base = Path(runtime_dir) / "mimictype"
    else:
        base = Path.home() / ".cache" / "mimictype"
    base.mkdir(parents=True, exist_ok=True)
    return base / "daemon.sock"


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def _send_frame(sock: socket.socket, obj: Dict[str, Any]) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_IPC_FRAME_BYTES:
        raise ValueError(f"IPC payload exceeds {MAX_IPC_FRAME_BYTES} bytes")
    header = struct.pack("!I", len(body))
    sock.sendall(header + body)


def _recv_frame(sock: socket.socket) -> Optional[Dict[str, Any]]:
    header = _recv_exact(sock, 4)
    if header is None:
        return None
    (length,) = struct.unpack("!I", header)
    if length <= 0 or length > MAX_IPC_FRAME_BYTES:
        raise ValueError(f"Invalid IPC frame length: {length}")
    body = _recv_exact(sock, length)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))


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
        try:
            os.chmod(self.socket_path, 0o600)
        except OSError:
            pass
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
                    conn.settimeout(2.0)
                    req = _recv_frame(conn)
                    if req is not None:
                        resp = self.handler(req)
                        _send_frame(conn, resp)
                except Exception as e:
                    try:
                        _send_frame(conn, {"error": str(e)})
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
        client.settimeout(5.0)
        try:
            client.connect(str(sock_path))
            msg: Dict[str, Any] = {"command": command}
            if payload:
                msg.update(payload)
            _send_frame(client, msg)
            return _recv_frame(client)
        except Exception:
            return None
        finally:
            client.close()

    @classmethod
    def ping(cls) -> bool:
        resp = cls.send("PING")
        return bool(resp and resp.get("status") == "PONG")
