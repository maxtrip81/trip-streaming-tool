"""Song title management: manual entry, text file watching, music app polling, prefix/suffix, delay."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time

_MAC_SCRIPT = '''
if application "Spotify" is running then
  tell application "Spotify"
    if player state is playing then return (artist of current track) & " - " & (name of current track)
  end tell
end if
if application "Music" is running then
  tell application "Music"
    if player state is playing then return (artist of current track) & " - " & (name of current track)
  end tell
end if
return ""
'''


def song_from_app() -> str:
    """Currently playing track from a desktop music application ("" when unknown)."""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["osascript", "-e", _MAC_SCRIPT], capture_output=True, text=True, timeout=3)
            return out.stdout.strip()
        if sys.platform.startswith("linux") and shutil.which("playerctl"):
            status = subprocess.run(["playerctl", "status"], capture_output=True, text=True, timeout=3)
            if status.stdout.strip() != "Playing":
                return ""
            out = subprocess.run(["playerctl", "metadata", "--format", "{{artist}} - {{title}}"],
                                 capture_output=True, text=True, timeout=3)
            text = out.stdout.strip()
            return "" if text in ("-", " - ") else text.strip(" -")
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def read_song_file(path: str, line: str = "first") -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [l.strip() for l in fh.read().splitlines() if l.strip()]
    except OSError:
        return ""
    if not lines:
        return ""
    return lines[-1] if line == "last" else lines[0]


class SongManager:
    def __init__(self, publish):
        self._publish_cb = publish
        self.cfg = {}
        self.current = ""
        self._raw = ""
        self._file_mtime = None
        self._last_app_poll = 0.0
        self._timer = None
        self._lock = threading.Lock()

    def configure(self, stream_cfg: dict) -> None:
        reset_file = self.cfg.get("song_file") != stream_cfg.get("song_file")
        self.cfg = dict(stream_cfg)
        if reset_file:
            self._file_mtime = None

    def format(self, raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return ""
        return f"{self.cfg.get('song_prefix', '')}{raw}{self.cfg.get('song_suffix', '')}"

    def set_manual(self, raw: str, immediate: bool = True) -> None:
        self._submit(raw, delay=0 if immediate else None)

    def _submit(self, raw: str, delay=None) -> None:
        song = self.format(raw)
        with self._lock:
            if raw == self._raw and song == self.current:
                return
            self._raw = raw
            if self._timer:
                self._timer.cancel()
                self._timer = None
            delay = float(self.cfg.get("song_delay", 0)) if delay is None else delay
            if delay > 0:
                self._timer = threading.Timer(delay, self._emit, args=(song,))
                self._timer.daemon = True
                self._timer.start()
            else:
                self._emit(song)

    def _emit(self, song: str) -> None:
        self.current = song
        self._publish_cb(song)

    def poll(self) -> None:
        path = self.cfg.get("song_file")
        if path:
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                mtime = None
            if mtime is not None and mtime != self._file_mtime:
                self._file_mtime = mtime
                raw = read_song_file(path, self.cfg.get("song_file_line", "first"))
                if raw:
                    self._submit(raw)
        if self.cfg.get("song_from_app") and time.monotonic() - self._last_app_poll > 2:
            self._last_app_poll = time.monotonic()
            raw = song_from_app()
            if raw:
                self._submit(raw)

    def cancel(self) -> None:
        if self._timer:
            self._timer.cancel()
