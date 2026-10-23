"""Loopback bridge for browser playback time and seek commands."""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from PyQt5.QtCore import QObject, QTimer, pyqtSignal


DEFAULT_PORTS = tuple(range(8765, 8773))
CONNECTION_TIMEOUT_SECONDS = 4.0


@dataclass(frozen=True)
class PlaybackState:
    session_id: str
    title: str
    url: str
    current_time: float
    duration: float
    paused: bool
    can_seek: bool
    viewport_area: float
    received_at: float
    manual: bool = False


@dataclass(frozen=True)
class SeekCommand:
    sequence: int
    target_session: str
    time: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "target_session": self.target_session,
            "time": self.time,
        }


class PlayerBridge(QObject):
    state_changed = pyqtSignal(object)
    connection_changed = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._state: PlaybackState | None = None
        self._pending_command: SeekCommand | None = None
        self._command_sequence = 0
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._last_connected = False
        self._port = 0
        self._connection_timer = QTimer(self)
        self._connection_timer.setInterval(1000)
        self._connection_timer.timeout.connect(self._check_connection)

    @property
    def port(self) -> int:
        return self._port

    @property
    def is_connected(self) -> bool:
        with self._lock:
            state = self._state
        if state is None:
            return False
        if state.manual:
            return True
        return time.monotonic() - state.received_at <= CONNECTION_TIMEOUT_SECONDS

    @property
    def state(self) -> PlaybackState | None:
        with self._lock:
            return self._state

    def start(self) -> bool:
        if self._server is not None:
            return True
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format, *args) -> None:  # type: ignore[no-untyped-def]
                return

            def _cors_headers(self) -> None:
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header(
                    "Access-Control-Allow-Methods",
                    "GET, POST, OPTIONS",
                )
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Content-Type",
                )
                self.send_header("Cache-Control", "no-store")

            def _send_json(
                self,
                status: int,
                payload: dict[str, Any],
            ) -> None:
                body = json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                self.send_response(status)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self) -> None:  # noqa: N802
                self.send_response(204)
                self._cors_headers()
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                if self.path.split("?", 1)[0] != "/api/status":
                    self._send_json(404, {"ok": False, "error": "not found"})
                    return
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "connected": bridge.is_connected,
                        "port": bridge.port,
                    },
                )

            def do_POST(self) -> None:  # noqa: N802
                if self.path.split("?", 1)[0] != "/api/playback":
                    self._send_json(404, {"ok": False, "error": "not found"})
                    return
                origin = self.headers.get("Origin", "")
                if origin and not origin.startswith("chrome-extension://"):
                    self._send_json(403, {"ok": False, "error": "forbidden"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length <= 0 or length > 65_536:
                    self._send_json(
                        413,
                        {"ok": False, "error": "invalid body size"},
                    )
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, ValueError, TypeError):
                    self._send_json(
                        400,
                        {"ok": False, "error": "invalid json"},
                    )
                    return
                if not isinstance(payload, dict):
                    self._send_json(
                        400,
                        {"ok": False, "error": "object required"},
                    )
                    return
                command = bridge.accept_playback(payload)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "command": command.as_dict() if command else None,
                    },
                )

        server = None
        for port in DEFAULT_PORTS:
            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
                self._port = port
                break
            except OSError:
                continue
        if server is None:
            self.error.emit("播放器时间同步端口被占用，无法启动本地桥接服务。")
            return False
        server.daemon_threads = True
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            name="YuzhongChunshengPlayerBridge",
            daemon=True,
        )
        self._thread.start()
        self._connection_timer.start()
        return True

    def stop(self) -> None:
        self._connection_timer.stop()
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        if self._last_connected:
            self._last_connected = False
            self.connection_changed.emit(False)

    def time_at(self, monotonic_seconds: float) -> float | None:
        with self._lock:
            state = self._state
        if state is None:
            return None
        if state.manual or state.paused:
            return max(0.0, state.current_time)
        elapsed = monotonic_seconds - state.received_at
        return max(0.0, state.current_time + elapsed)

    def seek(self, seconds: float) -> bool:
        if not math.isfinite(seconds):
            return False
        with self._lock:
            state = self._state
            if (
                state is None
                or state.manual
                or not state.can_seek
                or time.monotonic() - state.received_at
                > CONNECTION_TIMEOUT_SECONDS
            ):
                return False
            self._command_sequence += 1
            self._pending_command = SeekCommand(
                sequence=self._command_sequence,
                target_session=state.session_id,
                time=max(0.0, float(seconds)),
            )
        return True

    def set_manual_position(
        self,
        current_time: float,
        title: str = "手动同步播放器",
    ) -> bool:
        if not math.isfinite(current_time) or current_time < 0:
            return False
        now = time.monotonic()
        state = PlaybackState(
            session_id="manual",
            title=title,
            url="",
            current_time=float(current_time),
            duration=0.0,
            paused=False,
            can_seek=False,
            viewport_area=0.0,
            received_at=now,
            manual=True,
        )
        with self._lock:
            self._state = state
        self.state_changed.emit(state)
        if not self._last_connected:
            self._last_connected = True
            self.connection_changed.emit(True)
        return True

    def accept_playback(self, payload: dict[str, Any]) -> SeekCommand | None:
        try:
            session_id = str(payload.get("session_id", "")).strip()[:160]
            if not session_id:
                return None
            current_time = float(payload.get("current_time", 0.0))
            duration = float(payload.get("duration", 0.0))
            viewport_area = float(payload.get("viewport_area", 0.0))
            last_command_sequence = int(payload.get("last_command_sequence", 0))
        except (TypeError, ValueError):
            return None
        if not math.isfinite(current_time) or current_time < 0:
            return None
        if not math.isfinite(duration) or duration < 0:
            duration = 0.0
        if not math.isfinite(viewport_area) or viewport_area < 0:
            viewport_area = 0.0
        state = PlaybackState(
            session_id=session_id,
            title=str(payload.get("title", "网页视频"))[:240],
            url=str(payload.get("url", ""))[:2048],
            current_time=current_time,
            duration=duration,
            paused=bool(payload.get("paused", False)),
            can_seek=bool(payload.get("can_seek", True)),
            viewport_area=viewport_area,
            received_at=time.monotonic(),
        )
        with self._lock:
            self._state = state
            command = self._pending_command
            if (
                command is None
                or command.sequence <= last_command_sequence
                or command.target_session != session_id
            ):
                command = None
            elif command is not None:
                self._pending_command = None
        self.state_changed.emit(state)
        return command

    def _check_connection(self) -> None:
        connected = self.is_connected
        if connected != self._last_connected:
            self._last_connected = connected
            self.connection_changed.emit(connected)
