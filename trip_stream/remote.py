"""TCP remote control: a running instance can be driven from the command line or scripts.

Protocol: one line per request, ``<command> [argument]``; the reply is one JSON line.
Commands: connect, disconnect, record_start, record_stop, split, song <text>, status, quit.
"""

from __future__ import annotations

import json
import socket
import socketserver
import threading

COMMANDS = ("connect", "disconnect", "record_start", "record_stop", "split", "song", "status", "quit")


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            line = self.rfile.readline(65536).decode("utf-8", "replace").strip()
        except OSError:
            return
        cmd, _, arg = line.partition(" ")
        try:
            result = self.server.dispatch(cmd.lower(), arg)
            reply = {"ok": True, "result": result}
        except Exception as exc:
            reply = {"ok": False, "error": str(exc)}
        self.wfile.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class RemoteServer:
    def __init__(self, dispatch):
        self.dispatch = dispatch
        self._server = None
        self._thread = None
        self.address = ""

    def start(self, host: str, port: int) -> None:
        self.stop()
        server = _Server((host, port), _Handler)
        server.dispatch = self.dispatch
        self._server = server
        self.address = f"{host}:{server.server_address[1]}"
        self._thread = threading.Thread(target=server.serve_forever, daemon=True, name="trip-remote")
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


def send_command(host: str, port: int, command: str, arg: str = "", timeout: float = 5.0) -> dict:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall((f"{command} {arg}".strip() + "\n").encode("utf-8"))
        data = b""
        while not data.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    return json.loads(data.decode("utf-8"))
