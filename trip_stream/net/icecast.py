"""Icecast 2 and SHOUTcast source clients."""

from __future__ import annotations

import base64
import socket
import ssl
import urllib.parse

from trip_stream import USER_AGENT


class ConnectionFailed(RuntimeError):
    pass


def _open_socket(host: str, port: int, use_tls: bool, verify: bool, timeout: float = 10.0):
    sock = socket.create_connection((host, port), timeout=timeout)
    if use_tls:
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        sock = ctx.wrap_socket(sock, server_hostname=host)
    sock.settimeout(timeout)
    return sock


def _read_headers(sock, limit: int = 8192) -> str:
    data = b""
    while b"\r\n\r\n" not in data and b"\n\n" not in data and len(data) < limit:
        chunk = sock.recv(1024)
        if not chunk:
            break
        data += chunk
    return data.decode("latin-1", "replace")


def _http_get(host: str, port: int, path: str, use_tls: bool, verify: bool, headers: dict) -> tuple[int, str]:
    sock = _open_socket(host, port, use_tls, verify, timeout=8.0)
    try:
        lines = [f"GET {path} HTTP/1.0", f"Host: {host}:{port}"]
        lines += [f"{k}: {v}" for k, v in headers.items()]
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("utf-8"))
        response = _read_headers(sock)
    finally:
        sock.close()
    try:
        code = int(response.split(None, 2)[1])
    except (IndexError, ValueError):
        code = 0
    return code, response


def _audio_info(samplerate: int, bitrate: int, channels: int) -> str:
    return f"ice-samplerate={samplerate};ice-bitrate={bitrate};ice-channels={channels}"


class IcecastSource:
    def __init__(self, server: dict, icy: dict, content_type: str, samplerate: int, bitrate: int,
                 channels: int):
        self.server = server
        self.icy = icy
        self.content_type = content_type
        self.samplerate, self.bitrate, self.channels = samplerate, bitrate, channels
        self.sock = None

    @property
    def mount(self) -> str:
        mount = self.server["mount"].strip() or "/stream"
        return mount if mount.startswith("/") else "/" + mount

    def target(self) -> str:
        scheme = "https" if self.server["tls"] else "http"
        return f"{scheme}://{self.server['host']}:{self.server['port']}{self.mount}"

    def _auth(self) -> str:
        user = self.server.get("user") or "source"
        token = base64.b64encode(f"{user}:{self.server['password']}".encode("utf-8")).decode("ascii")
        return f"Basic {token}"

    def connect(self) -> None:
        srv = self.server
        self.sock = _open_socket(srv["host"], int(srv["port"]), srv["tls"], srv["tls_verify"])
        legacy = srv.get("icecast_protocol") == "source"
        method = "SOURCE" if legacy else "PUT"
        icy = self.icy
        headers = [
            f"{method} {self.mount} HTTP/1.{0 if legacy else 1}",
            f"Host: {srv['host']}:{srv['port']}",
            f"Authorization: {self._auth()}",
            f"User-Agent: {USER_AGENT}",
            f"Content-Type: {self.content_type}",
            f"Ice-Name: {icy['name']}",
            f"Ice-Description: {icy['description']}",
            f"Ice-Genre: {icy['genre']}",
            f"Ice-Url: {icy['url']}",
            f"Ice-Public: {1 if icy['public'] else 0}",
            f"Ice-Bitrate: {self.bitrate}",
            f"Ice-Audio-Info: {_audio_info(self.samplerate, self.bitrate, self.channels)}",
        ]
        if not legacy:
            headers.append("Expect: 100-continue")
        try:
            self.sock.sendall(("\r\n".join(headers) + "\r\n\r\n").encode("utf-8"))
            response = _read_headers(self.sock)
        except OSError as exc:
            self.close()
            raise ConnectionFailed(str(exc)) from exc
        status = response.split("\r\n", 1)[0].strip()
        parts = status.split(None, 2)
        code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if code not in (100, 200):
            self.close()
            reason = {401: "authentication failed (401)", 403: "mountpoint in use or forbidden (403)",
                      404: "not found (404)", 405: "method not allowed (405) - try the legacy SOURCE protocol"}
            raise ConnectionFailed(reason.get(code, status or "no response from server"))
        self.sock.settimeout(15.0)

    def send(self, data: bytes) -> None:
        self.sock.sendall(data)

    def update_metadata(self, song: str) -> None:
        srv = self.server
        query = urllib.parse.urlencode({"mount": self.mount, "mode": "updinfo", "song": song,
                                        "charset": "UTF-8"})
        code, response = _http_get(srv["host"], int(srv["port"]), f"/admin/metadata?{query}", srv["tls"],
                                   srv["tls_verify"], {"Authorization": self._auth(), "User-Agent": USER_AGENT})
        if code != 200:
            raise ConnectionFailed(response.split("\r\n", 1)[0] or "no response")

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None


class ShoutcastSource(IcecastSource):
    """SHOUTcast v1 / v2 (legacy source protocol on port+1, "password:#sid" for v2 stream ids)."""

    def target(self) -> str:
        return f"shoutcast://{self.server['host']}:{int(self.server['port']) + 1} (sid {self.server['sc_sid']})"

    def _password(self) -> str:
        sid = int(self.server.get("sc_sid") or 1)
        pwd = self.server["password"]
        return f"{pwd}:#{sid}" if sid > 1 else pwd

    def connect(self) -> None:
        srv = self.server
        self.sock = _open_socket(srv["host"], int(srv["port"]) + 1, srv["tls"], srv["tls_verify"])
        try:
            self.sock.sendall((self._password() + "\r\n").encode("utf-8"))
            response = _read_headers(self.sock)
        except OSError as exc:
            self.close()
            raise ConnectionFailed(str(exc)) from exc
        if not response.startswith("OK"):
            self.close()
            raise ConnectionFailed(response.strip().splitlines()[0] if response.strip() else
                                   "no response from server")
        icy = self.icy
        headers = [
            f"content-type: {self.content_type}",
            f"icy-name: {icy['name']}",
            f"icy-genre: {icy['genre']}",
            f"icy-url: {icy['url']}",
            f"icy-pub: {1 if icy['public'] else 0}",
            f"icy-br: {self.bitrate}",
            f"icy-irc: {icy['irc']}",
            f"icy-icq: {icy['icq']}",
            f"icy-aim: {icy['aim']}",
        ]
        self.sock.sendall(("\r\n".join(headers) + "\r\n\r\n").encode("utf-8"))
        self.sock.settimeout(15.0)

    def update_metadata(self, song: str) -> None:
        srv = self.server
        query = urllib.parse.urlencode({"pass": srv["password"], "mode": "updinfo", "song": song,
                                        "sid": int(srv.get("sc_sid") or 1)})
        code, response = _http_get(srv["host"], int(srv["port"]), f"/admin.cgi?{query}", srv["tls"],
                                   srv["tls_verify"], {"User-Agent": f"Mozilla/5.0 ({USER_AGENT})"})
        if code not in (200, 0):
            raise ConnectionFailed(response.split("\r\n", 1)[0] or "no response")
