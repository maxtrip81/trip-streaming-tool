"""Application core: ties together audio engine, streaming sessions, recorder, song updates and remote control."""

from __future__ import annotations

import collections
import copy
import datetime as _dt
import threading
import time

from trip_stream import config as config_mod
from trip_stream.audio.engine import AudioEngine
from trip_stream.encoders import CODECS, find_ffmpeg
from trip_stream.i18n import tr
from trip_stream.metadata import SongManager
from trip_stream.recorder import Recorder
from trip_stream.remote import RemoteServer
from trip_stream.stream import CONNECTED, StreamSession


class Controller:
    def __init__(self, cfg: dict, cfg_path=None):
        self.cfg = cfg
        self.cfg_path = cfg_path
        self._lock = threading.RLock()
        self.logs = collections.deque(maxlen=1000)
        self.log_serial = 0
        self.engine = AudioEngine(log=self.log)
        self.recorder = Recorder(log=self.log)
        self.songs = SongManager(self._publish_song)
        self.remote = RemoteServer(self.remote_dispatch)
        self.sessions: list[StreamSession] = []
        self.ffmpeg = ""
        self.quit_requested = False
        self._was_connected = False
        self._tick_thread = None
        self._running = False

    # ---------------------------------------------------------------- logging
    def log(self, msg) -> None:
        if isinstance(msg, tuple):
            key, kwargs = msg
            text = tr(key, **kwargs)
        else:
            text = str(msg)
        line = f"{_dt.datetime.now():%H:%M:%S}  {text}"
        self.logs.append(line)
        self.log_serial += 1
        path = self.cfg["advanced"].get("log_file")
        if path:
            try:
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(f"{_dt.datetime.now():%Y-%m-%d} {line}\n")
            except OSError:
                pass

    # -------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self.ffmpeg = find_ffmpeg(self.cfg["advanced"]["ffmpeg_path"])
        self.songs.configure(self.cfg["stream"])
        if self.cfg["stream"]["song"]:
            self.songs.set_manual(self.cfg["stream"]["song"])
        self.engine.start(self.cfg)
        self._start_remote()
        self._running = True
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True, name="trip-tick")
        self._tick_thread.start()
        if self.cfg["stream"]["connect_at_startup"]:
            self.connect()

    def _start_remote(self) -> None:
        self.remote.stop()
        adv = self.cfg["advanced"]
        if adv["remote_enabled"]:
            try:
                self.remote.start(adv["remote_host"], int(adv["remote_port"]))
                self.log(("msg.remote_listen", {"addr": self.remote.address}))
            except OSError as exc:
                self.log(("msg.remote_error", {"err": exc}))

    def shutdown(self) -> None:
        self._running = False
        self.disconnect()
        self.stop_record()
        self.songs.cancel()
        self.engine.stop()
        self.remote.stop()

    def save_config(self) -> None:
        config_mod.save(self.cfg, self.cfg_path)

    def apply_config(self, new_cfg: dict) -> None:
        """Apply a modified configuration; restarts audio/streams only when needed."""
        with self._lock:
            old = self.cfg
            self.cfg = copy.deepcopy(new_cfg)
            self.ffmpeg = find_ffmpeg(self.cfg["advanced"]["ffmpeg_path"])
            self.songs.configure(self.cfg["stream"])
            self.engine.threshold_db = float(self.cfg["detection"]["threshold_db"])
            audio_changed = old["audio"] != self.cfg["audio"]
            stream_changed = (old["stream"]["codec"], old["stream"]["bitrate"], old["stream"]["aac_profile"],
                              old["servers"], old["icy"]) != (
                self.cfg["stream"]["codec"], self.cfg["stream"]["bitrate"], self.cfg["stream"]["aac_profile"],
                self.cfg["servers"], self.cfg["icy"])
            streaming = self.is_streaming
            if audio_changed:
                recording = self.recorder.active
                if streaming:
                    self.disconnect(user=False)
                self.recorder.stop()
                self.engine.start(self.cfg)
                if streaming:
                    self.connect()
                if recording:
                    self.start_record()
            else:
                self.engine.apply_mixer(self.cfg["mixer"])
                self.engine.apply_dsp(self.cfg["dsp"])
                if streaming and stream_changed:
                    self.disconnect(user=False)
                    self.connect()
            if old["advanced"]["remote_enabled"] != self.cfg["advanced"]["remote_enabled"] or \
                    old["advanced"]["remote_port"] != self.cfg["advanced"]["remote_port"] or \
                    old["advanced"]["remote_host"] != self.cfg["advanced"]["remote_host"]:
                self._start_remote()
            for session in self.sessions:
                session.cfg = self.cfg

    def apply_mixer(self) -> None:
        self.engine.apply_mixer(self.cfg["mixer"])

    # -------------------------------------------------------------- streaming
    @property
    def is_streaming(self) -> bool:
        return any(s.active for s in self.sessions)

    @property
    def is_connected(self) -> bool:
        return any(s.state == CONNECTED for s in self.sessions)

    def connect(self) -> bool:
        with self._lock:
            if self.is_streaming:
                return True
            servers = [s for s in self.cfg["servers"] if s.get("enabled", True)]
            if not servers:
                self.log(("msg.no_servers", {}))
                return False
            codec = self.cfg["stream"]["codec"]
            needs_ffmpeg = any(s["type"] != "whip" for s in servers)
            if needs_ffmpeg and not self.ffmpeg:
                self.log(("msg.no_ffmpeg", {"codec": CODECS[codec]["label"]}))
                return False
            if codec == "aac" and self.cfg["stream"]["aac_profile"] != "lc" and self.ffmpeg:
                from trip_stream.encoders import ffmpeg_encoders
                if "libfdk_aac" not in ffmpeg_encoders(self.ffmpeg):
                    self.log(("msg.codec_fallback", {"codec": "AAC+"}))
            self.sessions = []
            for server in servers:
                session = StreamSession(server, self.cfg, self.ffmpeg, self.engine.samplerate,
                                        self.engine.channels, self.log, song=self.songs.current)
                self.sessions.append(session)
                self.engine.add_sink(session)
                session.start()
            return True

    def disconnect(self, user: bool = True) -> None:
        with self._lock:
            sessions, self.sessions = self.sessions, []
            for session in sessions:
                self.engine.remove_sink(session)
                session.stop(wait=False)
            for session in sessions:
                session.stop(wait=True)
            if user and self._was_connected and self.cfg["record"]["stop_on_disconnect"]:
                self.stop_record()
            self._was_connected = False

    # -------------------------------------------------------------- recording
    def start_record(self) -> bool:
        with self._lock:
            if self.recorder.active:
                return True
            codec = self.cfg["record"]["codec"]
            if codec != "wav" and not self.ffmpeg:
                self.log(("msg.no_ffmpeg", {"codec": CODECS[codec]["label"]}))
                return False
            ok = self.recorder.start(self.cfg, self.engine.samplerate, self.engine.channels, self.ffmpeg)
            if ok:
                self.engine.add_sink(self.recorder)
            return ok

    def stop_record(self) -> None:
        with self._lock:
            self.engine.remove_sink(self.recorder)
            self.recorder.stop()

    def toggle_record(self) -> None:
        if self.recorder.active:
            self.stop_record()
        else:
            self.start_record()

    def split_record(self) -> None:
        self.recorder.split()

    # ------------------------------------------------------------------- song
    def update_song(self, raw: str) -> None:
        self.cfg["stream"]["song"] = raw
        self.songs.set_manual(raw)

    def _publish_song(self, song: str) -> None:
        if song:
            self.log(("msg.song", {"song": song}))
        for session in list(self.sessions):
            session.set_song(song)

    # ------------------------------------------------------------- automation
    def _tick_loop(self) -> None:
        while self._running:
            try:
                self.tick()
            except Exception as exc:  # keep the automation alive whatever happens
                self.log(f"tick error: {exc}")
            time.sleep(0.25)

    def tick(self) -> None:
        self.songs.poll()
        stream, rec = self.cfg["stream"], self.cfg["record"]
        engine = self.engine
        connected = self.is_connected
        if connected and not self._was_connected:
            self._was_connected = True
            if rec["start_on_connect"] and not self.recorder.active:
                self.start_record()
        if self.sessions and not self.is_streaming:  # every session gave up
            self.disconnect()
        if self.recorder.error and not self.recorder.active:
            self.engine.remove_sink(self.recorder)
        if engine.running:
            if stream["start_on_signal"] and not self.is_streaming and \
                    engine.signal_secs >= float(stream["start_signal_secs"]):
                self.log(("msg.signal_start", {"what": tr("msg.what_stream")}))
                self.connect()
            if stream["stop_on_silence"] and self.is_streaming and \
                    engine.silence_secs >= float(stream["stop_silence_secs"]):
                self.log(("msg.silence_stop", {"what": tr("msg.what_stream")}))
                self.disconnect()
            if rec["start_on_signal"] and not self.recorder.active and \
                    engine.signal_secs >= float(rec["start_signal_secs"]):
                self.log(("msg.signal_start", {"what": tr("msg.what_record")}))
                self.start_record()
            if rec["stop_on_silence"] and self.recorder.active and \
                    engine.silence_secs >= float(rec["stop_silence_secs"]):
                self.log(("msg.silence_stop", {"what": tr("msg.what_record")}))
                self.stop_record()

    # ----------------------------------------------------------------- status
    def status(self) -> dict:
        sessions = [{
            "name": s.name, "type": s.server["type"], "state": s.state, "bytes_sent": s.bytes_sent,
            "kbps": round(s.kbps(), 1), "error": s.error,
            "uptime": int(time.time() - s.connected_since) if s.connected_since else 0,
        } for s in self.sessions]
        rec = self.recorder
        return {
            "streaming": self.is_streaming,
            "connected": self.is_connected,
            "sessions": sessions,
            "recording": rec.active,
            "record_file": rec.path if rec.active else "",
            "record_seconds": int(time.time() - rec.started_at) if rec.active else 0,
            "record_bytes": rec.file_size() if rec.active else 0,
            "song": self.songs.current,
            "codec": self.cfg["stream"]["codec"],
            "bitrate": self.cfg["stream"]["bitrate"],
            "samplerate": self.engine.samplerate,
            "channels": self.engine.channels,
            "peak_db": list(self.engine.peak_db),
            "rms_db": list(self.engine.rms_db),
            "audio_error": self.engine.error,
        }

    def remote_dispatch(self, cmd: str, arg: str):
        if cmd == "connect":
            return self.connect()
        if cmd == "disconnect":
            self.disconnect()
            return True
        if cmd == "record_start":
            return self.start_record()
        if cmd == "record_stop":
            self.stop_record()
            return True
        if cmd == "split":
            self.split_record()
            return True
        if cmd == "song":
            self.update_song(arg)
            return True
        if cmd == "status":
            return self.status()
        if cmd == "quit":
            self.quit_requested = True
            return True
        raise ValueError(f"unknown command: {cmd}")
