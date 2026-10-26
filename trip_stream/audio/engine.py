"""Audio capture engine: primary + secondary device, mixer, DSP, metering, fan-out to sinks."""

from __future__ import annotations

import collections
import queue
import threading
import time

import numpy as np

from trip_stream.audio import devices
from trip_stream.audio.dsp import Compressor, Equalizer, db_to_lin, levels_db


class _Ring:
    """Thread-safe FIFO of frames used to align the secondary device with the primary clock."""

    def __init__(self, channels: int, max_frames: int):
        self.channels = channels
        self.max_frames = max_frames
        self._chunks = collections.deque()
        self._frames = 0
        self._lock = threading.Lock()

    def push(self, block: np.ndarray) -> None:
        with self._lock:
            self._chunks.append(block)
            self._frames += len(block)
            while self._frames > self.max_frames and self._chunks:  # drift: drop oldest audio
                self._frames -= len(self._chunks.popleft())

    def pull(self, frames: int) -> np.ndarray:
        out = np.zeros((frames, self.channels), dtype=np.float32)
        pos = 0
        with self._lock:
            while pos < frames and self._chunks:
                chunk = self._chunks[0]
                take = min(frames - pos, len(chunk))
                out[pos:pos + take] = chunk[:take]
                pos += take
                if take < len(chunk):
                    self._chunks[0] = chunk[take:]
                else:
                    self._chunks.popleft()
                self._frames -= take
        return out


class _ToneSource(threading.Thread):
    """Built-in test-tone generator (440 Hz left, 660 Hz right, -12 dBFS)."""

    def __init__(self, samplerate: int, blocksize: int, callback):
        super().__init__(daemon=True, name="trip-tone")
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.callback = callback
        self._stop = threading.Event()
        self._phase = 0

    def run(self):
        start = time.monotonic()
        produced = 0
        amp = db_to_lin(-12)
        while not self._stop.is_set():
            t = (np.arange(self.blocksize) + self._phase) / self.samplerate
            block = np.stack([amp * np.sin(2 * np.pi * 440 * t), amp * np.sin(2 * np.pi * 660 * t)],
                             axis=1).astype(np.float32)
            self._phase += self.blocksize
            self.callback(block)
            produced += self.blocksize
            delay = start + produced / self.samplerate - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)

    def stop(self):
        self._stop.set()

    def close(self):
        self.stop()


class AudioEngine:
    """Captures audio and delivers processed float32 blocks (frames x channels) to sinks.

    Sinks are objects with a ``kind`` attribute ("stream" or "record") and a ``feed(block)`` method.
    """

    def __init__(self, log=None):
        self.log = log or (lambda msg: None)
        self._sinks: list = []
        self._sinks_lock = threading.Lock()
        self._queue: queue.Queue = queue.Queue(maxsize=200)
        self._worker = None
        self._running = False
        self._streams = []
        self._ring: _Ring | None = None
        self.samplerate = 44100
        self.channels = 2
        self.error = ""
        # mixer
        self.primary_gain = 1.0
        self.secondary_gain = 1.0
        self.master_gain = 1.0
        self.primary_mute = False
        self.secondary_mute = False
        # DSP
        self.eq: Equalizer | None = None
        self.comp: Compressor | None = None
        self.eq_enabled = False
        self.comp_enabled = False
        self.dsp_stream = True
        self.dsp_record = True
        # metering / detection
        self.peak_db = [-90.0, -90.0]
        self.rms_db = [-90.0, -90.0]
        self.threshold_db = -50.0
        self.signal_secs = 0.0
        self.silence_secs = 0.0
        self._map = {}

    # ------------------------------------------------------------------ sinks
    def add_sink(self, sink) -> None:
        with self._sinks_lock:
            if sink not in self._sinks:
                self._sinks.append(sink)

    def remove_sink(self, sink) -> None:
        with self._sinks_lock:
            if sink in self._sinks:
                self._sinks.remove(sink)

    # --------------------------------------------------------------- settings
    def apply_mixer(self, mixer: dict) -> None:
        self.primary_gain = db_to_lin(mixer["primary_gain_db"])
        self.secondary_gain = db_to_lin(mixer["secondary_gain_db"])
        self.master_gain = db_to_lin(mixer["master_gain_db"])
        self.primary_mute = bool(mixer["primary_mute"])
        self.secondary_mute = bool(mixer["secondary_mute"])

    def apply_dsp(self, dsp: dict) -> None:
        if self.eq is None or self.eq.samplerate != self.samplerate or self.eq.channels != self.channels:
            self.eq = Equalizer(self.samplerate, self.channels)
            self.comp = Compressor(self.samplerate)
        self.eq.set_gains(dsp["eq_gains"])
        self.comp.configure(dsp["comp_threshold_db"], dsp["comp_ratio"], dsp["comp_attack_ms"],
                            dsp["comp_release_ms"], dsp["comp_makeup_db"])
        self.eq_enabled = bool(dsp["eq_enabled"])
        self.comp_enabled = bool(dsp["comp_enabled"])
        self.dsp_stream = bool(dsp["apply_stream"])
        self.dsp_record = bool(dsp["apply_record"])

    # -------------------------------------------------------------- lifecycle
    @property
    def running(self) -> bool:
        return self._running

    def start(self, cfg: dict) -> bool:
        self.stop()
        audio = cfg["audio"]
        self.samplerate = int(audio["samplerate"])
        self.channels = 1 if int(audio["channels"]) == 1 else 2
        self.threshold_db = float(cfg["detection"]["threshold_db"])
        self.eq = None
        self.apply_mixer(cfg["mixer"])
        self.apply_dsp(cfg["dsp"])
        self.peak_db = [-90.0] * self.channels
        self.rms_db = [-90.0] * self.channels
        blocksize = max(64, int(self.samplerate * int(audio["buffer_ms"]) / 1000))
        self.error = ""
        self._queue = queue.Queue(maxsize=200)
        self._running = True
        self._worker = threading.Thread(target=self._work, daemon=True, name="trip-audio")
        self._worker.start()
        primary = audio["primary_device"]
        secondary = audio["secondary_device"]
        try:
            self._open(primary, audio["primary_left"], audio["primary_right"], blocksize, primary=True)
            if secondary:
                self._ring = _Ring(self.channels, self.samplerate // 2)
                self._open(secondary, audio["secondary_left"], audio["secondary_right"], blocksize,
                           primary=False)
            else:
                self._ring = None
        except Exception as exc:  # device missing / unsupported format
            self.error = str(exc) or exc.__class__.__name__
            self.log(("msg.audio_error", {"err": self.error}))
            self.stop()  # running must be False when no audio can flow
            return False
        name = primary or "default"
        if primary == devices.TONE_DEVICE:
            name = "test tone"
        self.log(("msg.audio_started", {"dev": name, "sr": self.samplerate, "ch": self.channels}))
        return True

    def _open(self, label, left, right, blocksize, primary: bool):
        if label == devices.TONE_DEVICE:
            src = _ToneSource(self.samplerate, blocksize,
                              (lambda b: self._on_primary(b, 2, 0, 1)) if primary
                              else (lambda b: self._on_secondary(b, 0, 1)))
            src.start()
            self._streams.append(src)
            return
        if devices.sd is None:
            raise RuntimeError("PortAudio not available")
        index = devices.find_device(label)
        dev_channels = devices.device_channels(label)
        left = min(int(left), dev_channels - 1)
        right = min(int(right), dev_channels - 1)
        open_ch = max(left, right) + 1

        if primary:
            def callback(indata, frames, time_info, status):
                self._on_primary(indata.copy(), open_ch, left, right)
        else:
            def callback(indata, frames, time_info, status):
                self._on_secondary(indata.copy(), left, right)

        stream = devices.sd.InputStream(device=index, channels=open_ch, samplerate=self.samplerate,
                                        blocksize=blocksize, dtype="float32", callback=callback)
        stream.start()
        self._streams.append(stream)

    def _map_channels(self, block: np.ndarray, left: int, right: int) -> np.ndarray:
        if block.shape[1] == 1:
            left = right = 0
        if self.channels == 1:
            if left == right:
                return block[:, left:left + 1]
            return ((block[:, left] + block[:, right]) * 0.5)[:, None]
        return np.stack([block[:, left], block[:, right]], axis=1)

    def _on_primary(self, block, _open_ch, left, right):
        try:
            self._queue.put_nowait(self._map_channels(block, left, right))
        except queue.Full:
            pass

    def _on_secondary(self, block, left, right):
        if self._ring is not None:
            self._ring.push(self._map_channels(block, left, right))

    def _close_streams(self):
        for stream in self._streams:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self._streams = []

    def stop(self) -> None:
        self._close_streams()
        if self._running:
            self._running = False
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
            if self._worker:
                self._worker.join(timeout=2)
        self._worker = None
        self.peak_db = [-90.0] * self.channels
        self.rms_db = [-90.0] * self.channels

    # ----------------------------------------------------------------- worker
    def _work(self):
        while self._running:
            block = self._queue.get()
            if block is None:
                break
            self.process(block)

    def process(self, block: np.ndarray) -> None:
        """Mix, meter and distribute one block of primary audio (public for tests)."""
        block = block.astype(np.float32) * (0.0 if self.primary_mute else self.primary_gain)
        if self._ring is not None:
            sec = self._ring.pull(len(block))
            if not self.secondary_mute:
                block = block + sec * self.secondary_gain
        dry = block * self.master_gain
        wet = dry
        if self.eq_enabled and self.eq is not None:
            wet = self.eq.process(wet)
        if self.comp_enabled and self.comp is not None:
            wet = self.comp.process(wet)
        dry = np.clip(dry, -1.0, 1.0)
        wet = np.clip(wet, -1.0, 1.0)

        metered = wet if (self.eq_enabled or self.comp_enabled) and self.dsp_stream else dry
        peak, rms = levels_db(metered)
        self.peak_db, self.rms_db = peak, rms
        secs = len(block) / self.samplerate
        if max(rms) > self.threshold_db:
            self.signal_secs += secs
            self.silence_secs = 0.0
        else:
            self.silence_secs += secs
            self.signal_secs = 0.0

        with self._sinks_lock:
            sinks = list(self._sinks)
        for sink in sinks:
            use_wet = self.dsp_stream if sink.kind == "stream" else self.dsp_record
            try:
                sink.feed(wet if use_wet else dry)
            except Exception as exc:  # a broken sink must never stop the audio
                self.log(f"sink error: {exc}")
