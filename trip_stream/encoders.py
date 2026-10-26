"""Audio encoders. Compressed formats are produced by an FFmpeg child process; WAV is native."""

from __future__ import annotations

import functools
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

# codec id -> description
CODECS = {
    "mp3": {"label": "MP3", "ext": "mp3", "content_type": "audio/mpeg", "ogg": False},
    "aac": {"label": "AAC+", "ext": "aac", "content_type": "audio/aacp", "ogg": False},
    "vorbis": {"label": "Ogg/Vorbis", "ext": "ogg", "content_type": "audio/ogg", "ogg": True},
    "opus": {"label": "Ogg/Opus", "ext": "opus", "content_type": "audio/ogg", "ogg": True},
    "flac": {"label": "Ogg/FLAC", "ext": "flac", "content_type": "audio/ogg", "ogg": True},
    "wav": {"label": "WAV", "ext": "wav", "content_type": "audio/wav", "ogg": False},
}
STREAM_CODECS = ["mp3", "aac", "vorbis", "opus", "flac"]
RECORD_CODECS = ["wav", "mp3", "aac", "vorbis", "opus", "flac"]
BITRATES = [8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
SAMPLERATES = [22050, 32000, 44100, 48000, 88200, 96000]
AAC_PROFILES = {"lc": "AAC-LC", "he": "HE-AAC (AAC+)", "hev2": "HE-AAC v2 (AAC+ v2)"}

_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0


def find_ffmpeg(configured: str = "") -> str:
    """Locate an FFmpeg binary: configured path, bundled copy, PATH, imageio-ffmpeg."""
    if configured and Path(configured).is_file():
        return configured
    exe = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidate = Path(bundle) / "ffmpeg" / exe
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


@functools.lru_cache(maxsize=8)
def ffmpeg_encoders(ffmpeg: str) -> frozenset:
    if not ffmpeg:
        return frozenset()
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True,
                             timeout=10, creationflags=_NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] == "A":
            names.add(parts[1])
    return frozenset(names)


def encoder_args(codec: str, bitrate: int, samplerate: int, channels: int, ffmpeg: str,
                 aac_profile: str = "he", for_file: bool = False, title: str = "") -> tuple[list, str]:
    """Return (ffmpeg output arguments, warning) for a codec."""
    available = ffmpeg_encoders(ffmpeg)
    warning = ""
    args: list[str] = []
    if codec == "mp3":
        args = ["-c:a", "libmp3lame" if "libmp3lame" in available or not available else "libshine",
                "-b:a", f"{bitrate}k", "-f", "mp3"]
        if samplerate > 48000:
            args[:0] = ["-ar", "48000"]
    elif codec == "aac":
        if "libfdk_aac" in available:
            profile = {"lc": "aac_low", "he": "aac_he", "hev2": "aac_he_v2"}.get(aac_profile, "aac_he")
            if profile == "aac_he_v2" and channels != 2:
                profile = "aac_he"
            args = ["-c:a", "libfdk_aac", "-profile:a", profile, "-b:a", f"{bitrate}k"]
        else:
            if aac_profile != "lc":
                warning = "aac_fallback"
            args = ["-c:a", "aac", "-b:a", f"{bitrate}k"]
        args += ["-f", "adts"]
    elif codec == "vorbis":
        args = ["-c:a", "libvorbis", "-b:a", f"{bitrate}k", "-f", "ogg"]
    elif codec == "opus":
        args = ["-c:a", "libopus", "-b:a", f"{bitrate}k", "-ar", "48000", "-application", "audio",
                "-frame_duration", "20", "-f", "ogg" if not for_file else "opus"]
    elif codec == "flac":
        args = ["-c:a", "flac", "-compression_level", "5", "-f", "ogg" if not for_file else "flac"]
    else:
        raise ValueError(f"unsupported codec {codec}")
    if title:
        args[:0] = ["-metadata", f"title={title}"]
    if not for_file and CODECS[codec]["ogg"]:
        args[:0] = ["-page_duration", "200000"]  # small Ogg pages keep latency low
    return args, warning


def to_s16(block: np.ndarray) -> bytes:
    return (np.clip(block, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


class EncoderError(RuntimeError):
    pass


class FFmpegEncoder:
    """PCM s16le in (stdin) -> encoded bytes out (callback) or written to a file."""

    def __init__(self, ffmpeg: str, codec: str, bitrate: int, samplerate: int, channels: int,
                 on_data=None, out_file: str | None = None, aac_profile: str = "he", title: str = "",
                 on_error=None):
        if not ffmpeg:
            raise EncoderError("FFmpeg not found")
        self.codec = codec
        self.on_data = on_data
        self.on_error = on_error or (lambda msg: None)
        args, self.warning = encoder_args(codec, bitrate, samplerate, channels, ffmpeg, aac_profile,
                                          for_file=out_file is not None, title=title)
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-probesize", "32", "-analyzeduration", "0",
               "-fflags", "nobuffer", "-f", "s16le", "-ar", str(samplerate),
               "-ac", str(channels), "-i", "pipe:0", "-vn"] + args
        cmd += ["-flush_packets", "1"]
        cmd += ["pipe:1"] if out_file is None else ["-y", out_file]
        self.cmd = cmd
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE if out_file is None else subprocess.DEVNULL,
                                      stderr=subprocess.PIPE, bufsize=0, creationflags=_NO_WINDOW)
        self._closed = False
        self.bytes_out = 0
        self.data_error = ""
        self.last_error = ""
        self._reader = None
        if out_file is None:
            self._reader = threading.Thread(target=self._read_loop, daemon=True, name="trip-enc-out")
            self._reader.start()
        self._err_reader = threading.Thread(target=self._err_loop, daemon=True, name="trip-enc-err")
        self._err_reader.start()

    def _read_loop(self):
        fd = self._proc.stdout
        while True:
            try:
                data = fd.read1(16384) if hasattr(fd, "read1") else os.read(fd.fileno(), 16384)
            except (OSError, ValueError):
                break
            if not data:
                break
            self.bytes_out += len(data)
            if self.on_data:
                try:
                    self.on_data(data)
                except Exception as exc:  # e.g. network failure while sending
                    self.data_error = str(exc) or exc.__class__.__name__
                    break

    def _err_loop(self):
        for line in iter(self._proc.stderr.readline, b""):
            text = line.decode("utf-8", "replace").strip()
            if text:
                self.last_error = text
                self.on_error(text)

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None

    def _exit_reason(self) -> str:
        code = self._proc.poll()
        if self._err_reader.is_alive():
            self._err_reader.join(timeout=1)
        return self.last_error or f"FFmpeg exited with code {code}"

    def write(self, block: np.ndarray) -> None:
        if self._closed:
            return
        if self._proc.poll() is not None:  # e.g. the output file could not be created
            raise EncoderError(self._exit_reason())
        view = memoryview(to_s16(block))
        try:
            while view:  # unbuffered pipe: the OS may accept only part of the data
                written = self._proc.stdin.write(view)
                if written is None:
                    continue
                view = view[written:]
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise EncoderError(self._exit_reason() if self._proc.poll() is not None
                               else f"encoder stopped: {exc}") from exc

    def close(self, timeout: float = 5.0) -> None:
        """Flush and terminate; all remaining encoded data is delivered before returning."""
        if self._closed:
            return
        self._closed = True
        try:
            self._proc.stdin.close()
        except OSError:
            pass
        try:
            self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        if self._reader:
            self._reader.join(timeout=timeout)

    def kill(self) -> None:
        self._closed = True
        try:
            self._proc.kill()
        except OSError:
            pass


class WavWriter:
    """16-bit PCM WAV writer.

    The header is rewritten every few seconds, so the file stays playable even if the program is closed
    abruptly; ``full`` tells the recorder to continue in a new file before the 4 GB WAV limit.
    """

    HEADER_INTERVAL = 2.0
    MAX_DATA_BYTES = 4_000_000_000

    def __init__(self, path: str, samplerate: int, channels: int):
        self.samplerate = samplerate
        self.channels = channels
        self.warning = ""
        self.data_bytes = 0
        self._fh = open(path, "wb")
        self._write_header()
        self._fh.flush()
        self._last_header = time.monotonic()

    alive = True

    @property
    def full(self) -> bool:
        return self.data_bytes >= self.MAX_DATA_BYTES

    def _write_header(self) -> None:
        align = self.channels * 2
        header = (b"RIFF" + struct.pack("<I", 36 + self.data_bytes) + b"WAVE"
                  + b"fmt " + struct.pack("<IHHIIHH", 16, 1, self.channels, self.samplerate,
                                          self.samplerate * align, align, 16)
                  + b"data" + struct.pack("<I", self.data_bytes))
        end = self._fh.tell()
        self._fh.seek(0)
        self._fh.write(header)
        self._fh.seek(max(end, len(header)))

    def write(self, block: np.ndarray) -> None:
        data = to_s16(block)
        self._fh.write(data)
        self.data_bytes += len(data)
        if time.monotonic() - self._last_header >= self.HEADER_INTERVAL:
            self._write_header()
            self._fh.flush()
            self._last_header = time.monotonic()

    def close(self, timeout: float = 0) -> None:
        if self._fh is not None:
            self._write_header()
            self._fh.close()
            self._fh = None
