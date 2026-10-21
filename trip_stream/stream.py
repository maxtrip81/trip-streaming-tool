"""One streaming session per server: encoder + network source + automatic reconnection."""

from __future__ import annotations

import queue
import threading
import time

from trip_stream.encoders import CODECS, EncoderError, FFmpegEncoder
from trip_stream.net.icecast import ConnectionFailed, IcecastSource, ShoutcastSource
from trip_stream.net import whip

IDLE, CONNECTING, CONNECTED, RECONNECTING, FAILED = "idle", "connecting", "connected", "reconnecting", "failed"


class StreamSession:
    kind = "stream"

    def __init__(self, server: dict, cfg: dict, ffmpeg: str, samplerate: int, channels: int, log,
                 song: str = ""):
        self.server = server
        self.name = server["name"]
        self.cfg = cfg
        self.ffmpeg = ffmpeg
        self.samplerate = samplerate
        self.channels = channels
        self.log = log
        self.state = IDLE
        self.error = ""
        self.bytes_sent = 0
        self._session_bytes = 0
        self.connected_since = 0.0
        self.attempt = 0
        self._song = song
        self._song_dirty = False
        self._queue: queue.Queue = queue.Queue(maxsize=400)
        self._stop = threading.Event()
        self._send_error = ""
        self._source = None
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"trip-stream-{self.name}")

    # --------------------------------------------------------------- public
    @property
    def active(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        self._thread.start()

    def stop(self, wait: bool = True) -> None:
        self._stop.set()
        if wait and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=8)

    def feed(self, block) -> None:
        if self.state != CONNECTED:
            return
        try:
            self._queue.put_nowait(block)
        except queue.Full:  # network too slow: drop oldest audio to stay live
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(block)
            except (queue.Empty, queue.Full):
                pass

    def set_song(self, song: str) -> None:
        self._song = song
        self._song_dirty = True

    def kbps(self) -> float:
        if self.state != CONNECTED or not self.connected_since:
            return 0.0
        secs = max(1e-3, time.time() - self.connected_since)
        return self._session_bytes * 8 / 1000 / secs

    # -------------------------------------------------------------- private
    def _make_source(self):
        stream = self.cfg["stream"]
        kind = self.server["type"]
        if kind == "whip":
            return whip.WhipSource(self.server, self.samplerate, self.channels)
        cls = ShoutcastSource if kind == "shoutcast" else IcecastSource
        return cls(self.server, self.cfg["icy"], CODECS[stream["codec"]]["content_type"],
                   48000 if stream["codec"] == "opus" else self.samplerate, int(stream["bitrate"]),
                   self.channels)

    def _make_encoder(self, title: str = ""):
        stream = self.cfg["stream"]

        def on_data(data: bytes):
            self._source.send(data)
            self.bytes_sent += len(data)
            self._session_bytes += len(data)

        def on_error(msg: str):
            self.log(("msg.encoder_error", {"err": msg}))

        return FFmpegEncoder(self.ffmpeg, stream["codec"], int(stream["bitrate"]), self.samplerate,
                             self.channels, on_data=on_data, on_error=on_error,
                             aac_profile=stream["aac_profile"], title=title)

    def _send_metadata_async(self, song: str):
        source = self._source

        def worker():
            try:
                source.update_metadata(song)
            except Exception as exc:
                self.log(("msg.meta_error", {"server": self.name, "err": exc}))
        threading.Thread(target=worker, daemon=True).start()

    def _drain_queue(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def _run(self):
        stream_cfg = self.cfg["stream"]
        while not self._stop.is_set():
            self.state = CONNECTING if self.attempt == 0 else RECONNECTING
            self._session_bytes = 0
            self._send_error = ""
            try:
                self._session()
                if self._stop.is_set():
                    break
                raise ConnectionFailed(self._send_error or "connection lost")
            except (ConnectionFailed, EncoderError, OSError) as exc:
                if self._stop.is_set():
                    break
                self.error = str(exc) or exc.__class__.__name__
                self.log(("msg.conn_error", {"server": self.name, "err": self.error}))
            finally:
                self._close_source()
            if not stream_cfg["reconnect"]:
                self.state = FAILED
                return
            self.attempt += 1
            limit = int(stream_cfg["reconnect_max"])
            if limit and self.attempt > limit:
                self.log(("msg.giving_up", {"server": self.name, "n": limit}))
                self.state = FAILED
                return
            delay = max(1, int(stream_cfg["reconnect_delay"]))
            self.state = RECONNECTING
            self.log(("msg.reconnect", {"server": self.name, "secs": delay, "n": self.attempt}))
            self._stop.wait(delay)
        self.state = IDLE
        self.connected_since = 0.0
        self.log(("msg.disconnected", {"server": self.name}))

    def _close_source(self):
        if self._source is not None:
            self._source.close()
            self._source = None

    def _session(self):
        self._source = self._make_source()
        self.log(("msg.connecting", {"server": self.name, "target": self._source.target()}))
        self._source.connect()
        is_whip = self.server["type"] == "whip"
        is_ogg = CODECS[self.cfg["stream"]["codec"]]["ogg"]
        encoder = None
        try:
            if not is_whip:
                encoder = self._make_encoder(self._song if is_ogg else "")
            self._drain_queue()
            self.attempt = 0
            self.error = ""
            self.state = CONNECTED
            self.connected_since = time.time()
            self.log(("msg.connected", {"server": self.name}))
            if self._song and not is_ogg and not is_whip:
                self._send_metadata_async(self._song)
            self._song_dirty = False
            while not self._stop.is_set():
                if encoder is not None and encoder.data_error:
                    self._send_error = encoder.data_error
                if self._send_error:
                    return
                if self._song_dirty:
                    self._song_dirty = False
                    if is_ogg and encoder is not None:
                        # Ogg streams carry metadata in-band: start a new chained logical stream
                        encoder.close()
                        if encoder.data_error:
                            self._send_error = encoder.data_error
                            return
                        encoder = self._make_encoder(self._song)
                    elif not is_whip:
                        self._send_metadata_async(self._song)
                try:
                    block = self._queue.get(timeout=0.5)
                except queue.Empty:
                    if encoder is not None and not encoder.alive:
                        raise EncoderError("encoder terminated")
                    continue
                if is_whip:
                    self._source.send_pcm(block)
                else:
                    encoder.write(block)
        finally:
            if encoder is not None:
                if self._stop.is_set() and not self._send_error:
                    encoder.close(timeout=2)
                else:
                    encoder.kill()
            self.state = IDLE if self._stop.is_set() else self.state
            self.connected_since = 0.0
