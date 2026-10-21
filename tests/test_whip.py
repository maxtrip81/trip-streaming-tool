"""End-to-end WHIP test: a local WHIP endpoint built with aiortc receives the Opus audio track."""
import asyncio
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

aiortc = pytest.importorskip("aiortc")
from aiortc import RTCPeerConnection, RTCSessionDescription  # noqa: E402

from trip_stream import config  # noqa: E402
from trip_stream.stream import CONNECTED, StreamSession  # noqa: E402


class Endpoint:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.frames = 0
        self.token = None
        self.deleted = False

    async def answer(self, offer_sdp):
        pc = RTCPeerConnection()
        self.pc = pc

        @pc.on("track")
        def on_track(track):
            async def consume():
                while True:
                    try:
                        await track.recv()
                    except Exception:
                        return
                    self.frames += 1
            asyncio.ensure_future(consume())

        await pc.setRemoteDescription(RTCSessionDescription(offer_sdp, "offer"))
        await pc.setLocalDescription(await pc.createAnswer())
        return pc.localDescription.sdp


def test_whip_publish():
    ep = Endpoint()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            ep.token = self.headers.get("Authorization")
            offer = self.rfile.read(int(self.headers["Content-Length"])).decode()
            answer = asyncio.run_coroutine_threadsafe(ep.answer(offer), ep.loop).result(20)
            self.send_response(201)
            self.send_header("Content-Type", "application/sdp")
            self.send_header("Location", "/whip/resource/1")
            self.end_headers()
            self.wfile.write(answer.encode())

        def do_DELETE(self):
            ep.deleted = True
            self.send_response(200)
            self.end_headers()

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/whip"
    cfg = config.load("/nonexistent")
    server = config.normalize_server({"name": "whip", "type": "whip", "whip_url": url, "whip_token": "tok"})
    logs = []
    session = StreamSession(server, cfg, "", 48000, 2, logs.append)
    session.start()
    for _ in range(200):
        if session.state == CONNECTED:
            break
        time.sleep(0.05)
    assert session.state == CONNECTED, logs
    t0 = time.time()
    while time.time() - t0 < 4 and ep.frames < 20:
        session.feed(np.random.uniform(-0.2, 0.2, (960, 2)).astype(np.float32))
        time.sleep(0.02)
    session.stop()
    httpd.shutdown()
    assert ep.token == "Bearer tok"
    assert ep.frames >= 20, logs
    assert ep.deleted
