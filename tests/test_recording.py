import json
import os
import time
import wave
from pathlib import Path

import numpy as np
import pytest

from trip_stream import config
from trip_stream.audio.engine import AudioEngine
from trip_stream.controller import Controller
from trip_stream.encoders import EncoderError, FFmpegEncoder, WavWriter, find_ffmpeg
from trip_stream.recorder import Recorder
import trip_stream.recorder as recorder_mod


def tone(frames=4410):
    t = np.arange(frames) / 44100
    return np.stack([0.3 * np.sin(2 * np.pi * 440 * t)] * 2, axis=1).astype(np.float32)


def test_wav_is_playable_while_recording(tmp_path):
    """Even if the program dies before closing, the WAV header describes the audio written so far."""
    path = tmp_path / "live.wav"
    writer = WavWriter(str(path), 44100, 2)
    writer.HEADER_INTERVAL = 0
    for _ in range(10):
        writer.write(tone())
    # simulate a crash: read the file without closing the writer
    writer._fh.flush()
    with wave.open(str(path)) as wav:
        assert wav.getnframes() == 44100
        assert wav.getnchannels() == 2 and wav.getframerate() == 44100
    writer.close()
    with wave.open(str(path)) as wav:
        assert wav.getnframes() == 44100


def test_wav_rotates_before_4gb(tmp_path, monkeypatch):
    monkeypatch.setattr(WavWriter, "MAX_DATA_BYTES", 4410 * 4 * 3)
    cfg = config.load(tmp_path / "c.json")
    cfg["record"]["folder"] = str(tmp_path / "rec")
    cfg["record"]["filename"] = "part_%i"
    rec = Recorder(log=lambda m: None)
    assert rec.start(cfg, 44100, 2, "")
    for _ in range(10):
        rec.feed(tone())
    time.sleep(0.5)
    rec.stop()
    files = sorted(os.listdir(tmp_path / "rec"))
    assert len(files) >= 3, files
    total = 0
    for name in files:
        with wave.open(str(tmp_path / "rec" / name)) as wav:
            total += wav.getnframes()
    assert total == 44100


@pytest.mark.skipif(not find_ffmpeg(), reason="FFmpeg not available")
def test_ffmpeg_failure_is_reported(tmp_path):
    enc = FFmpegEncoder(find_ffmpeg(), "mp3", 128, 44100, 2, out_file=str(tmp_path / "missing" / "x.mp3"))
    with pytest.raises(EncoderError) as info:
        for _ in range(200):
            enc.write(tone())
            time.sleep(0.01)
    assert "x.mp3" in str(info.value) or "No such file" in str(info.value) or "exited" in str(info.value)
    enc.kill()


@pytest.mark.skipif(not find_ffmpeg(), reason="FFmpeg not available")
def test_recorder_stops_and_reports_when_ffmpeg_fails(tmp_path, monkeypatch):
    cfg = config.load(tmp_path / "c.json")
    cfg["record"]["codec"] = "mp3"
    cfg["record"]["folder"] = str(tmp_path)
    logs = []
    rec = Recorder(log=logs.append)
    # make the output impossible to create after the recorder has chosen the path
    real_open = recorder_mod.FFmpegEncoder

    def broken(*args, **kwargs):
        kwargs["out_file"] = str(tmp_path / "nope" / "x.mp3")
        return real_open(*args, **kwargs)
    monkeypatch.setattr(recorder_mod, "FFmpegEncoder", broken)
    assert rec.start(cfg, 44100, 2, find_ffmpeg())
    for _ in range(100):
        rec.feed(tone())
        time.sleep(0.02)
        if not rec.active:
            break
    assert not rec.active and rec.error
    assert any(isinstance(m, tuple) and m[0] == "msg.rec_error" for m in logs)


def test_stalled_recording_is_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder_mod, "STALL_SECONDS", 0.3)
    cfg = config.load(tmp_path / "c.json")
    cfg["record"]["folder"] = str(tmp_path)
    rec = Recorder(log=lambda m: None)
    rec.start(cfg, 44100, 2, "")
    assert rec.check_growth() == ""
    time.sleep(0.5)  # no audio arrives: the file does not grow
    assert rec.check_growth() == "stalled"
    rec.feed(tone())
    time.sleep(0.4)
    rec._writer._fh.flush()
    assert rec.check_growth() == "" and rec.warning == ""
    rec.stop()


@pytest.mark.parametrize("codec", ["wav", "mp3", "vorbis", "opus", "flac", "aac"])
def test_controller_records_every_codec(tmp_path, codec):
    if codec != "wav" and not find_ffmpeg():
        pytest.skip("FFmpeg not available")
    cfg = config.load(tmp_path / "c.json")
    cfg["audio"]["primary_device"] = "__tone__"
    cfg["advanced"]["remote_enabled"] = False
    cfg["record"]["folder"] = str(tmp_path / "rec")
    cfg["record"]["codec"] = codec
    ctl = Controller(cfg, tmp_path / "c.json")
    ctl.start()
    try:
        assert ctl.start_record()
        time.sleep(2.5)
        assert ctl.status()["record_bytes"] > 0
        ctl.stop_record()
    finally:
        ctl.shutdown()
    files = list((tmp_path / "rec").iterdir())
    assert len(files) == 1 and files[0].stat().st_size > 2000, files
    if codec == "wav":
        with wave.open(str(files[0])) as wav:
            assert wav.getnframes() / wav.getframerate() > 2.0


def test_default_folder_and_migration(tmp_path):
    folder = config.default_record_folder()
    assert folder.name == "TRIP streaming tool"
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"version": 1, "record": {"folder": str(Path.home())}}))
    cfg = config.load(old)
    assert cfg["record"]["folder"] == "" and cfg["version"] == config.CONFIG_VERSION
    custom = tmp_path / "custom.json"
    custom.write_text('{"version": 1, "record": {"folder": "/data/rec"}}')
    assert config.load(custom)["record"]["folder"] == "/data/rec"


def test_engine_not_running_when_device_fails(tmp_path):
    cfg = config.load(tmp_path / "c.json")
    cfg["audio"]["primary_device"] = "Device that does not exist [Nowhere]"
    engine = AudioEngine()
    assert not engine.start(cfg)
    assert not engine.running and engine.error
