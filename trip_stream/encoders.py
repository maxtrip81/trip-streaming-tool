"""Audio encoders. Compressed formats are produced by an FFmpeg child process; WAV is native."""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys
import threading
import wave
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
                self.on_error(text)

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None

    def write(self, block: np.ndarray) -> None:
        if self._closed:
            return
        try:
            self._proc.stdin.write(to_s16(block))
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise EncoderError(f"encoder stopped: {exc}") from exc

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
    def __init__(self, path: str, samplerate: int, channels: int):
        self._wav = wave.open(path, "wb")
        self._wav.setnchannels(channels)
        self._wav.setsampwidth(2)
        self._wav.setframerate(samplerate)
        self.warning = ""

    alive = True

    def write(self, block: np.ndarray) -> None:
        self._wav.writeframes(to_s16(block))

    def close(self, timeout: float = 0) -> None:
        if self._wav is not None:
            self._wav.close()
            self._wav = None
