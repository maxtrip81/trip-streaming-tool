"""Local recording of the live signal, with optional periodic file splitting."""

from __future__ import annotations

import datetime as _dt
import os
import queue
import threading
import time
from pathlib import Path

from trip_stream.config import default_record_folder
from trip_stream.encoders import CODECS, FFmpegEncoder, WavWriter

STALL_SECONDS = 8.0


def expand_filename(template: str, index: int, now: _dt.datetime | None = None) -> str:
    now = now or _dt.datetime.now()
    template = template.replace("%i", str(index))
    try:
        name = now.strftime(template)
    except ValueError:
        name = template
    for bad in '<>:"/\\|?*':
        name = name.replace(bad, "-")
    return name.strip() or "recording"


def next_split_time(start: float, minutes: int, sync: bool) -> float:
    if minutes <= 0:
        return 0.0
    period = minutes * 60
    if not sync:
        return start + period
    local = _dt.datetime.fromtimestamp(start)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    elapsed = start - midnight
    return midnight + (int(elapsed // period) + 1) * period


class Recorder:
    kind = "record"

    def __init__(self, log):
        self.log = log
        self.path = ""
        self.started_at = 0.0
        self.file_started_at = 0.0
        self.index = 0
        self._writer = None
        self._queue: queue.Queue = queue.Queue(maxsize=800)
        self._thread = None
        self._stop = threading.Event()
        self._split_now = threading.Event()
        self._next_split = 0.0
        self.error = ""
        self.warning = ""
        self._last_size = -1
        self._last_growth = 0.0

    @property
    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @staticmethod
    def folder_for(cfg: dict) -> Path:
        return Path(os.path.expanduser(cfg["record"]["folder"] or str(default_record_folder())))

    def _open_writer(self):
        rec = self.cfg["record"]
        codec = rec["codec"]
        folder = self.folder_for(self.cfg)
        folder.mkdir(parents=True, exist_ok=True)
        base = expand_filename(rec["filename"], self.index)
        ext = CODECS[codec]["ext"]
        path = folder / f"{base}.{ext}"
        n = 1
        while path.exists():
            path = folder / f"{base}_{n}.{ext}"
            n += 1
        if codec == "wav":
            writer = WavWriter(str(path), self.samplerate, self.channels)
        else:
            writer = FFmpegEncoder(self.ffmpeg, codec, int(rec["bitrate"]), self.samplerate, self.channels,
                                   out_file=str(path), aac_profile=self.cfg["stream"]["aac_profile"],
                                   on_error=lambda m: self.log(("msg.rec_error", {"err": m})))
        self.path = str(path)
        self.file_started_at = time.time()
        self._last_size = -1
        self._last_growth = time.monotonic()
        self.warning = ""
        self._next_split = next_split_time(self.file_started_at, int(rec["split_minutes"]), bool(rec["split_sync"]))
        self.log(("msg.rec_start", {"file": self.path}))
        return writer

    def start(self, cfg: dict, samplerate: int, channels: int, ffmpeg: str) -> bool:
        if self.active:
            return True
        self.cfg, self.samplerate, self.channels, self.ffmpeg = cfg, samplerate, channels, ffmpeg
        self.index = 1
        self.error = ""
        self.warning = ""
        try:
            self._writer = self._open_writer()
        except Exception as exc:
            self.error = str(exc)
            self.log(("msg.rec_error", {"err": exc}))
            return False
        self.started_at = time.time()
        self._stop.clear()
        self._split_now.clear()
        self._queue = queue.Queue(maxsize=800)
        self._thread = threading.Thread(target=self._run, daemon=True, name="trip-record")
        self._thread.start()
        return True

    def feed(self, block) -> None:
        if self.active and not self._stop.is_set():
            try:
                self._queue.put_nowait(block)
            except queue.Full:
                pass

    def split(self) -> None:
        if self.active:
            self._split_now.set()

    def stop(self) -> None:
        if not self.active:
            return
        self._stop.set()
        self._thread.join(timeout=60)  # the file is finalised by the recording thread
        self._thread = None
        self.log(("msg.rec_stop", {"file": self.path}))

    def file_size(self) -> int:
        try:
            return os.path.getsize(self.path) if self.path else 0
        except OSError:
            return 0

    def check_growth(self) -> str:
        """Return a warning when the file has not grown for a while (writing blocked or impossible)."""
        if not self.active:
            return ""
        size = self.file_size()
        now = time.monotonic()
        if size != self._last_size:
            self._last_size = size
            self._last_growth = now
            self.warning = ""
        elif now - self._last_growth > STALL_SECONDS and not self.warning:
            self.warning = "stalled"
            return "stalled"
        return ""

    def _rotate(self):
        self._writer.close()
        self.index += 1
        self._writer = self._open_writer()

    def _run(self):
        try:
            while True:
                try:
                    block = self._queue.get(timeout=0.25)
                except queue.Empty:
                    block = None
                if block is not None:
                    self._writer.write(block)
                elif self._stop.is_set():
                    break
                if self._split_now.is_set() or getattr(self._writer, "full", False) or \
                        (self._next_split and time.time() >= self._next_split):
                    self._split_now.clear()
                    self._rotate()
        except Exception as exc:
            self.error = str(exc) or exc.__class__.__name__
            self.log(("msg.rec_error", {"err": self.error}))
        finally:
            if self._writer is not None:
                try:
                    self._writer.close()
                except Exception:
                    pass
                self._writer = None
