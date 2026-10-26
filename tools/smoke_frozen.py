"""Smoke test of a built (PyInstaller) TRIP executable: headless start, record with several codecs via the
remote-control port, quit, then check the recorded files. Used by CI on Windows, macOS and Linux.

Usage: python tools/smoke_frozen.py path/to/trip-streaming-tool[.exe]
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

PORT = 12999


def command(cmd):
    with socket.create_connection(("127.0.0.1", PORT), timeout=10) as sock:
        sock.sendall((cmd + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
    reply = json.loads(data)
    assert reply["ok"], reply
    return reply["result"]


def main():
    exe = Path(sys.argv[1]).resolve()
    work = Path(tempfile.mkdtemp())
    rec_dir = work / "registrazioni con spazi"
    cfg = {"audio": {"primary_device": "__tone__"},
           "advanced": {"remote_enabled": True, "remote_host": "127.0.0.1", "remote_port": PORT},
           "record": {"folder": str(rec_dir), "filename": "smoke_%i"}, "gui": {"language": "it"}}
    failures = []
    for codec in ["wav", "mp3", "flac", "opus"]:
        cfg["record"]["codec"] = codec
        cfg_path = work / f"{codec}.json"
        cfg_path.write_text(json.dumps(cfg))
        env = dict(os.environ)
        # make sure the FFmpeg bundled with the build is used, not one installed on the machine
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                      if not (Path(p) / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")).exists())
        proc = subprocess.Popen([str(exe), "-c", str(cfg_path), "--headless"], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                try:
                    command("status")
                    break
                except OSError:
                    time.sleep(0.5)
            assert command("record_start"), "record_start failed"
            time.sleep(4)
            status = command("status")
            print(codec, "recording:", status["recording"], status["record_file"], status["record_bytes"], "bytes",
                  "error:", status["record_error"])
            assert status["recording"] and status["record_bytes"] > 0, status
            command("record_stop")
            command("quit")
            proc.wait(timeout=30)
        except Exception as exc:  # report and keep testing the other codecs
            failures.append(f"{codec}: {exc!r}")
            proc.kill()
        output = proc.communicate()[0].decode("utf-8", "replace") if proc.stdout else ""
        print(output)
    files = sorted(rec_dir.iterdir()) if rec_dir.exists() else []
    for f in files:
        print("file:", f.name, f.stat().st_size)
    by_ext = {f.suffix.lstrip("."): f for f in files}
    for ext in ["wav", "mp3", "flac", "opus"]:
        f = by_ext.get(ext)
        if f is None or f.stat().st_size < 5000:
            failures.append(f"missing or empty .{ext} recording")
    if "wav" in by_ext:
        with wave.open(str(by_ext["wav"])) as w:
            secs = w.getnframes() / w.getframerate()
            print("wav duration", secs)
            if secs < 3:
                failures.append(f"wav too short: {secs}")
    if failures:
        print("FAILURES:", *failures, sep="\n  ")
        sys.exit(1)
    print("smoke test passed")


if __name__ == "__main__":
    main()
