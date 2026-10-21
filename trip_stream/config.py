"""Configuration handling (JSON file in the per-user config directory)."""

from __future__ import annotations

import copy
import configparser
import json
import locale
import os
import sys
from pathlib import Path

from trip_stream import APP_ID

CONFIG_FILENAME = "trip_stream.json"

DEFAULT_SERVER = {
    "name": "My server",
    "type": "icecast",          # icecast | shoutcast | whip
    "host": "localhost",
    "port": 8000,
    "password": "hackme",
    "mount": "/stream",
    "user": "source",
    "tls": False,
    "tls_verify": True,
    "icecast_protocol": "put",  # put | source (legacy, Icecast < 2.4)
    "sc_sid": 1,                 # SHOUTcast v2 stream id
    "whip_url": "",
    "whip_token": "",
    "enabled": True,
}

DEFAULTS = {
    "version": 1,
    "servers": [],
    "icy": {
        "name": "TRIP streaming tool",
        "description": "Live with TRIP streaming tool",
        "genre": "Various",
        "url": "",
        "irc": "",
        "icq": "",
        "aim": "",
        "public": False,
    },
    "audio": {
        "primary_device": "",       # "" = system default input
        "primary_left": 0,
        "primary_right": 1,
        "secondary_device": "",     # "" = disabled
        "secondary_left": 0,
        "secondary_right": 1,
        "samplerate": 44100,
        "channels": 2,
        "buffer_ms": 50,
    },
    "mixer": {
        "primary_gain_db": 0.0,
        "secondary_gain_db": 0.0,
        "master_gain_db": 0.0,
        "primary_mute": False,
        "secondary_mute": False,
    },
    "stream": {
        "codec": "mp3",
        "bitrate": 128,
        "aac_profile": "he",        # lc | he | hev2
        "song": "",
        "song_file": "",
        "song_file_line": "first",  # first | last
        "song_from_app": False,
        "song_prefix": "",
        "song_suffix": "",
        "song_delay": 0,
        "connect_at_startup": False,
        "reconnect": True,
        "reconnect_delay": 3,
        "reconnect_max": 0,         # 0 = retry forever
        "start_on_signal": False,
        "start_signal_secs": 5,
        "stop_on_silence": False,
        "stop_silence_secs": 30,
    },
    "record": {
        "codec": "wav",
        "bitrate": 192,
        "folder": str(Path.home()),
        "filename": "rec_%Y-%m-%d_%H-%M-%S",
        "split_minutes": 0,
        "split_sync": False,
        "start_on_connect": False,
        "stop_on_disconnect": False,
        "start_on_signal": False,
        "start_signal_secs": 5,
        "stop_on_silence": False,
        "stop_silence_secs": 30,
    },
    "detection": {
        "threshold_db": -50.0,
    },
    "dsp": {
        "eq_enabled": False,
        "eq_preset": "flat",
        "eq_gains": [0.0] * 10,
        "comp_enabled": False,
        "comp_threshold_db": -20.0,
        "comp_ratio": 4.0,
        "comp_attack_ms": 10.0,
        "comp_release_ms": 200.0,
        "comp_makeup_db": 0.0,
        "apply_stream": True,
        "apply_record": True,
    },
    "advanced": {
        "ffmpeg_path": "",
        "remote_enabled": True,
        "remote_host": "127.0.0.1",
        "remote_port": 1256,
        "log_file": "",
    },
    "gui": {
        "language": "",
        "always_on_top": False,
        "start_minimized": False,
        "lcd_color": "#38f2b0",
        "geometry": "",
    },
}


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "TRIP streaming tool"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "TRIP streaming tool"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_ID


def default_config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


def _merge(defaults, loaded):
    if isinstance(defaults, dict) and isinstance(loaded, dict):
        out = {}
        for key, value in defaults.items():
            out[key] = _merge(value, loaded[key]) if key in loaded else copy.deepcopy(value)
        for key, value in loaded.items():
            if key not in defaults:
                out[key] = value
        return out
    return loaded


def normalize_server(server: dict) -> dict:
    return _merge(DEFAULT_SERVER, server)


def load(path: Path | str | None = None) -> dict:
    path = Path(path) if path else default_config_path()
    cfg = copy.deepcopy(DEFAULTS)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                cfg = _merge(DEFAULTS, json.load(fh))
        except (OSError, ValueError):
            pass
    cfg["servers"] = [normalize_server(s) for s in cfg.get("servers", [])]
    if len(cfg["dsp"]["eq_gains"]) != 10:
        cfg["dsp"]["eq_gains"] = [0.0] * 10
    return cfg


def save(cfg: dict, path: Path | str | None = None) -> None:
    path = Path(path) if path else default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def install_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        # macOS bundle: .../TRIP.app/Contents/MacOS/trip -> look in Contents/Resources too
        return exe.parent
    return Path(__file__).resolve().parent.parent


def installer_language() -> str:
    """Language chosen in the installer (written to language.ini by the installer)."""
    candidates = [install_dir() / "language.ini",
                  install_dir().parent / "Resources" / "language.ini",
                  config_dir() / "language.ini"]
    for ini in candidates:
        if ini.exists():
            parser = configparser.ConfigParser()
            try:
                parser.read(ini, encoding="utf-8")
                lang = parser.get("TRIP", "language", fallback="").strip().lower()
            except (configparser.Error, OSError):
                continue
            if lang:
                return lang
    return ""


def system_language() -> str:
    try:
        lang = locale.getlocale()[0] or os.environ.get("LANG", "")
    except ValueError:
        lang = os.environ.get("LANG", "")
    return "it" if (lang or "").lower().startswith("it") else "en"


def resolve_language(cfg: dict) -> str:
    """Return the configured language, or "" when the user has never chosen one."""
    lang = cfg["gui"].get("language") or installer_language()
    return lang if lang in ("it", "en") else ""
