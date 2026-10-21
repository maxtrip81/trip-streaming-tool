"""WebRTC-HTTP Ingestion Protocol (WHIP) client based on aiortc (Opus over WebRTC)."""

from __future__ import annotations

import asyncio
import fractions
import threading
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

from trip_stream import USER_AGENT
from trip_stream.net.icecast import ConnectionFailed

try:
    import av
    from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
    AVAILABLE = True
except ImportError:  # optional dependency
    AVAILABLE = False
    MediaStreamTrack = object


class PcmTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, loop, samplerate: int, channels: int):
        super().__init__()
        self._loop = loop
        self.samplerate = samplerate
        self.channels = channels
        self._frame = samplerate // 50  # 20 ms
        self._pending = np.zeros((0, channels), dtype=np.int16)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._pts = 0

    def push(self, block: np.ndarray) -> None:
        pcm = (np.clip(block, -1, 1) * 32767).astype(np.int16)
        self._pending = np.concatenate([self._pending, pcm]) if len(self._pending) else pcm
        while len(self._pending) >= self._frame:
            chunk, self._pending = self._pending[:self._frame], self._pending[self._frame:]
            self._loop.call_soon_threadsafe(self._enqueue, chunk)

    def _enqueue(self, chunk):
        if self._queue.qsize() > 50:  # not consumed yet (connecting): keep latency bounded
            self._queue.get_nowait()
        self._queue.put_nowait(chunk)

    async def recv(self):
        chunk = await self._queue.get()
        layout = "stereo" if self.channels == 2 else "mono"
        frame = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), format="s16", layout=layout)
        frame.sample_rate = self.samplerate
        frame.pts = self._pts
        frame.time_base = fractions.Fraction(1, self.samplerate)
        self._pts += len(chunk)
        return frame


class WhipSource:
    """Publishes PCM to a WHIP endpoint. ``send_pcm`` replaces the byte-oriented ``send``."""

    def __init__(self, server: dict, samplerate: int, channels: int):
        self.server = server
        self.samplerate = samplerate
        self.channels = channels
        self._loop = None
        self._thread = None
        self._pc = None
        self._track = None
        self._resource = None
        self.failed = ""

    def target(self) -> str:
        return self.server.get("whip_url") or "(no WHIP URL)"

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _call(self, coro, timeout=30):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def connect(self) -> None:
        if not AVAILABLE:
            raise ConnectionFailed("aiortc not installed")
        if not self.server.get("whip_url"):
            raise ConnectionFailed("missing WHIP URL")
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="trip-whip")
        self._thread.start()
        try:
            self._call(self._connect())
        except ConnectionFailed:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise ConnectionFailed(str(exc) or exc.__class__.__name__) from exc

    def _post_offer(self, sdp: str) -> tuple[str, str]:
        headers = {"Content-Type": "application/sdp", "User-Agent": USER_AGENT}
        if self.server.get("whip_token"):
            headers["Authorization"] = f"Bearer {self.server['whip_token']}"
        req = urllib.request.Request(self.server["whip_url"], data=sdp.encode("utf-8"), headers=headers,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                answer = resp.read().decode("utf-8")
                location = resp.headers.get("Location", "")
        except urllib.error.HTTPError as exc:
            raise ConnectionFailed(f"WHIP endpoint answered {exc.code} {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise ConnectionFailed(str(exc.reason)) from exc
        return answer, urllib.parse.urljoin(self.server["whip_url"], location) if location else ""

    async def _connect(self):
        self._pc = RTCPeerConnection()
        self._track = PcmTrack(asyncio.get_running_loop(), self.samplerate, self.channels)
        self._pc.addTransceiver(self._track, direction="sendonly")

        @self._pc.on("connectionstatechange")
        async def _state():
            if self._pc and self._pc.connectionState in ("failed", "closed"):
                self.failed = f"WebRTC connection {self._pc.connectionState}"

        await self._pc.setLocalDescription(await self._pc.createOffer())
        answer, self._resource = await asyncio.get_running_loop().run_in_executor(
            None, self._post_offer, self._pc.localDescription.sdp)
        await self._pc.setRemoteDescription(RTCSessionDescription(sdp=answer, type="answer"))

    def send_pcm(self, block: np.ndarray) -> None:
        if self.failed:
            raise ConnectionFailed(self.failed)
        if self._track is not None:
            self._track.push(block)

    def update_metadata(self, song: str) -> None:
        pass  # WHIP has no standard metadata channel

    def close(self) -> None:
        if self._resource:
            try:
                headers = {"User-Agent": USER_AGENT}
                if self.server.get("whip_token"):
                    headers["Authorization"] = f"Bearer {self.server['whip_token']}"
                urllib.request.urlopen(urllib.request.Request(self._resource, headers=headers,
                                                              method="DELETE"), timeout=5).close()
            except Exception:
                pass
            self._resource = None
        if self._loop is not None:
            if self._pc is not None:
                try:
                    self._call(self._pc.close(), timeout=5)
                except Exception:
                    pass
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=5)
            self._loop = None
        self._pc = None
        self._track = None
