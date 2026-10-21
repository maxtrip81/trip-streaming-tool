import json
import re
import socket
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from trip_stream import config, i18n
from trip_stream.audio.dsp import Compressor, Equalizer, levels_db
from trip_stream.audio.engine import AudioEngine
from trip_stream.encoders import FFmpegEncoder, find_ffmpeg
from trip_stream.metadata import SongManager, read_song_file
from trip_stream.recorder import expand_filename, next_split_time
from trip_stream.remote import RemoteServer, send_command

ROOT = Path(__file__).resolve().parent.parent


def test_every_used_key_is_translated():
    used = set()
    for path in (ROOT / "trip_stream").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        used |= set(re.findall(r'tr\(\s*"([a-z_]+\.[a-z0-9_]+)"', text))
        used |= set(re.findall(r'\(\s*"(msg\.[a-z_]+)"\s*,\s*\{', text))
        used |= set(re.findall(r'"((?:tab|audio|stream|record|preset|icy|server)\.[a-z0-9_]+)"', text)) & i18n.keys()
    missing = used - i18n.keys()
    assert not missing, missing
    for key in i18n.keys():
        en, it = i18n._STRINGS[key]
        assert en and it


def test_language_switch():
    i18n.set_language("it")
    assert i18n.tr("btn.settings") == "Impostazioni"
    i18n.set_language("en")
    assert i18n.tr("btn.settings") == "Settings"
    assert "Max Trip" in i18n.tr("about.text", version="1")


def test_config_roundtrip(tmp_path):
    path = tmp_path / "c.json"
    cfg = config.load(path)
    cfg["servers"].append(config.normalize_server({"name": "x"}))
    cfg["gui"]["language"] = "it"
    config.save(cfg, path)
    loaded = config.load(path)
    assert loaded["servers"][0]["mount"] == "/stream"
    assert config.resolve_language(loaded) == "it"
    # unknown future keys are preserved, missing keys get defaults
    raw = json.loads(path.read_text())
    del raw["dsp"]
    raw["future"] = 1
    path.write_text(json.dumps(raw))
    loaded = config.load(path)
    assert loaded["dsp"]["eq_gains"] == [0.0] * 10 and loaded["future"] == 1


def test_installer_language(tmp_path, monkeypatch):
    (tmp_path / "language.ini").write_text("[TRIP]\nlanguage=it\n")
    monkeypatch.setattr(config, "install_dir", lambda: tmp_path)
    cfg = config.load(tmp_path / "none.json")
    assert config.resolve_language(cfg) == "it"
    cfg["gui"]["language"] = "en"  # user choice wins over the installer
    assert config.resolve_language(cfg) == "en"


def test_equalizer_boosts_band():
    sr = 44100
    t = np.arange(sr) / sr
    sig = np.stack([np.sin(2 * np.pi * 1000 * t)] * 2, axis=1).astype(np.float32) * 0.1
    eq = Equalizer(sr, 2)
    eq.set_gains([0, 0, 0, 0, 0, 6, 0, 0, 0, 0])
    out = np.concatenate([eq.process(sig[i:i + 1024]) for i in range(0, sr, 1024)])
    gain = np.abs(out[sr // 2:]).max() / 0.1
    assert 1.8 < gain < 2.1  # +6 dB


def test_compressor_reduces_loud_signal():
    comp = Compressor(44100)
    comp.configure(-20, 4, 1, 100, 0)
    loud = np.full((44100, 2), 0.9, dtype=np.float32)
    out = comp.process(loud)
    assert np.abs(out[-1000:]).max() < 0.4
    quiet = np.full((4410, 2), 0.01, dtype=np.float32)
    comp2 = Compressor(44100)
    assert np.allclose(comp2.process(quiet), quiet)


def test_levels():
    peak, rms = levels_db(np.full((100, 2), 0.5, dtype=np.float32))
    assert abs(peak[0] + 6.02) < 0.1 and abs(rms[1] + 6.02) < 0.1


class Sink:
    kind = "stream"

    def __init__(self):
        self.blocks = []

    def feed(self, block):
        self.blocks.append(block)


def test_engine_mixer_and_detection():
    engine = AudioEngine()
    cfg = config.load("/nonexistent")
    engine.samplerate, engine.channels = 44100, 2
    engine.apply_mixer(dict(cfg["mixer"], master_gain_db=-6.0206))
    engine.apply_dsp(cfg["dsp"])
    sink = Sink()
    engine.add_sink(sink)
    engine.process(np.full((4410, 2), 0.5, dtype=np.float32))
    assert abs(sink.blocks[0][0, 0] - 0.25) < 1e-3
    assert engine.signal_secs == pytest.approx(0.1)
    engine.process(np.zeros((4410, 2), dtype=np.float32))
    assert engine.signal_secs == 0 and engine.silence_secs == pytest.approx(0.1)
    engine.primary_mute = True
    engine.process(np.full((10, 2), 0.5, dtype=np.float32))
    assert not sink.blocks[-1].any()


def test_engine_mono_downmix():
    engine = AudioEngine()
    engine.channels = 1
    block = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    assert engine._map_channels(block, 0, 1).shape == (2, 1)


def test_filename_and_split():
    import datetime as dt
    now = dt.datetime(2026, 5, 4, 13, 7, 9)
    assert expand_filename("rec_%Y%m%d-%H%M%S_%i", 3, now) == "rec_20260504-130709_3"
    assert expand_filename("a/b:c", 1, now) == "a-b-c"
    start = dt.datetime(2026, 5, 4, 13, 7, 9).timestamp()
    nxt = next_split_time(start, 60, True)
    assert dt.datetime.fromtimestamp(nxt) == dt.datetime(2026, 5, 4, 14, 0, 0)
    assert next_split_time(start, 30, False) == start + 1800
    assert next_split_time(start, 0, False) == 0


def test_song_manager(tmp_path):
    published = []
    sm = SongManager(published.append)
    sm.configure({"song_prefix": "Now: ", "song_suffix": " *", "song_delay": 0, "song_file": ""})
    sm.set_manual("A - B")
    assert published == ["Now: A - B *"]
    song = tmp_path / "song.txt"
    song.write_text("first\nsecond\n")
    assert read_song_file(str(song), "last") == "second"
    sm.configure({"song_prefix": "", "song_suffix": "", "song_delay": 0, "song_file": str(song),
                  "song_file_line": "first"})
    sm.poll()
    assert published[-1] == "first"


def test_remote_control():
    calls = []
    server = RemoteServer(lambda cmd, arg: calls.append((cmd, arg)) or {"cmd": cmd})
    server.start("127.0.0.1", 0)
    port = int(server.address.rsplit(":", 1)[1])
    reply = send_command("127.0.0.1", port, "song", "Max Trip - Hello")
    assert reply["ok"] and calls == [("song", "Max Trip - Hello")]
    server.stop()


@pytest.mark.skipif(not find_ffmpeg(), reason="FFmpeg not available")
@pytest.mark.parametrize("codec,magic", [("mp3", None), ("vorbis", b"OggS"), ("opus", b"OggS"),
                                         ("flac", b"OggS"), ("aac", b"\xff")])
def test_encoders(codec, magic):
    chunks = []
    enc = FFmpegEncoder(find_ffmpeg(), codec, 96, 44100, 2, on_data=chunks.append)
    for _ in range(20):
        enc.write(np.random.uniform(-0.2, 0.2, (4410, 2)).astype(np.float32))
    enc.close()
    data = b"".join(chunks)
    assert len(data) > 1000
    if magic:
        assert data.startswith(magic)


def _fake_shoutcast(port_holder, received, password="secret"):
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # SHOUTcast source port is base port + 1
    for base in range(18000, 18100, 2):
        try:
            srv.bind(("127.0.0.1", base + 1))
            break
        except OSError:
            continue
    port_holder.append(base)
    srv.listen(1)
    conn, _ = srv.accept()
    pwd = conn.recv(100)
    received["password"] = pwd
    conn.sendall(b"OK2\r\nicy-caps:11\r\n\r\n")
    data = b""
    conn.settimeout(3)
    try:
        while len(data) < 20000:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
    except OSError:
        pass
    received["data"] = data
    conn.close()
    srv.close()


@pytest.mark.skipif(not find_ffmpeg(), reason="FFmpeg not available")
def test_shoutcast_session():
    from trip_stream.stream import StreamSession, CONNECTED
    ports, received = [], {}
    th = threading.Thread(target=_fake_shoutcast, args=(ports, received), daemon=True)
    th.start()
    while not ports:
        time.sleep(0.01)
    cfg = config.load("/nonexistent")
    server = config.normalize_server({"name": "sc", "type": "shoutcast", "host": "127.0.0.1", "port": ports[0],
                                      "password": "secret", "sc_sid": 2})
    logs = []
    session = StreamSession(server, cfg, find_ffmpeg(), 44100, 2, logs.append)
    session.start()
    for _ in range(100):
        if session.state == CONNECTED:
            break
        time.sleep(0.05)
    assert session.state == CONNECTED, logs
    for _ in range(30):
        session.feed(np.random.uniform(-0.2, 0.2, (4410, 2)).astype(np.float32))
        time.sleep(0.02)
    th.join(5)
    session.stop()
    assert received["password"] == b"secret:#2\r\n"
    header, _, audio = received["data"].partition(b"\r\n\r\n")
    assert b"content-type: audio/mpeg" in header and b"icy-name:" in header
    assert len(audio) > 1000
