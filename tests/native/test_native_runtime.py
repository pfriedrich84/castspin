# SPDX-License-Identifier: Apache-2.0
"""Native reused receiver + permissive controller + real SDK + MA API simulator.

Uses locally GENERATED TLS (not Google-rooted identity) and synthetic WAV. This
is not YouTube Music, a real MA server, HA Supervisor or audible acceptance.
"""
import asyncio
import base64
import io
import json
import math
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import unittest
from uuid import UUID
import wave

from aiohttp import web
import pychromecast
from music_assistant_models.enums import PlaybackState
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ma"))
from test_music_assistant import MaApiSimulator
from castspin.app.runtime import Runtime
from castspin.app.settings import Settings


async def wait_for(predicate, timeout=15):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.05)


def generated_manifest(directory):
    certificate, key = directory / "peer.pem", directory / "peer.key"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=CastSpin generated software fixture", "-keyout", str(key),
                    "-out", str(certificate)], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    pem = certificate.read_text()
    # Placeholder auth signatures are deliberately NOT a device-auth proof.
    signature = base64.b64encode(b"generated-non-google-fixture").decode()
    manifest = directory / "certs.json"
    manifest.write_text(json.dumps({"cpu": pem, "ica": pem, "crl": "AA==", "certs": [{
        "pu": pem, "pr": key.read_text(), "sig_sha1": signature, "sig_sha256": signature}]}))
    manifest.chmod(0o600)
    return manifest


def generated_audio():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((2, 2, 48000, 48000, "NONE", "not compressed"))
        wav.writeframes(b"".join(struct.pack("<hh", value, value) for value in (
            int(10000 * math.sin(2 * math.pi * 440 * n / 48000)) for n in range(48000))))
    return output.getvalue()


@unittest.skipUnless(os.environ.get("CASTSPIN_NATIVE_BINARY"), "Set CASTSPIN_NATIVE_BINARY to the reviewed receiver")
class NativeRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.api = MaApiSimulator()
        self.api.fetch_audio = True
        self.audio = generated_audio()
        app = web.Application()
        app.router.add_get("/ws", self.api.ws)
        app.router.add_get("/audio.wav", lambda _: web.Response(body=self.audio, content_type="audio/wav"))
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))  # Local route selection; sends no packet.
            self.address = probe.getsockname()[0]
        with socket.socket() as probe:
            probe.bind((self.address, 0))
            player_port = probe.getsockname()[1]
        self.settings = Settings(True, f"http://127.0.0.1:{self.port}", "test-token", self.address, player_port)
        self.certificate = generated_manifest(self.directory)
        self.stop = asyncio.Event()
        self.runtime = Runtime(self.settings, data=self.directory / "data", certificate=self.certificate,
                               binary=os.environ["CASTSPIN_NATIVE_BINARY"])
        self.task = asyncio.create_task(self.runtime.run(self.stop))
        self.casts = []
        self.resolvers = set()
        self.found = {}
        self.zc = AsyncZeroconf(interfaces=[self.address])

        async def resolve(name):
            info = AsyncServiceInfo("_googlecast._tcp.local.", name)
            if await info.async_request(self.zc.zeroconf, 3000):
                friendly = info.properties.get(b"fn", b"").decode()
                if friendly in {"Sauna [CastSpin]", "Garten [CastSpin]"}:
                    self.found[friendly] = info

        def discovered(zeroconf, service_type, name, state_change):
            if state_change != ServiceStateChange.Removed:
                task = asyncio.create_task(resolve(name))
                self.resolvers.add(task)
                task.add_done_callback(self.resolvers.discard)
        self.browser = AsyncServiceBrowser(self.zc.zeroconf, "_googlecast._tcp.local.", handlers=[discovered])

    async def asyncTearDown(self):
        for cast in self.casts:
            await asyncio.to_thread(cast.disconnect, timeout=3)
        self.stop.set()
        await asyncio.wait_for(self.task, 20)
        await self.browser.async_cancel()
        for task in self.resolvers:
            task.cancel()
        await asyncio.gather(*self.resolvers, return_exceptions=True)
        await self.zc.async_close()
        self.api.release.set()
        for connection in list(self.api.sockets):
            await connection.close()
        await self.runner.cleanup()
        self.temp.cleanup()

    async def connect(self, friendly):
        info = self.found[friendly]
        cast = await asyncio.to_thread(pychromecast.get_chromecast_from_host,
            (self.address, info.port, UUID(info.properties[b"id"].decode()), "CastSpin", friendly),
            tries=1, retry_wait=0.1, timeout=5)
        self.casts.append(cast)
        await asyncio.to_thread(cast.wait, timeout=8)
        return cast

    async def test_actual_native_mdns_cast_load_ma_fetch_controls_and_shutdown(self):
        await wait_for(lambda: self.runtime.snapshot.get("connected_bridges") == 2)
        await wait_for(lambda: len(self.found) == 2)
        self.assertEqual(self.runtime.snapshot["cast_receiver"], "player_bridge_connected")
        self.assertFalse(self.runtime.snapshot["audio_verified"])
        self.assertEqual(self.api.writes(), [])
        for name in ("Sauna", "Garten"):
            cast = await self.connect(name + " [CastSpin]")
            await asyncio.to_thread(cast.media_controller.play_media,
                f"http://{self.address}:{self.port}/audio.wav", "audio/wav", title="Generated WAV fixture")
            await wait_for(lambda: name.lower() in self.api.received_audio)
            self.assertEqual(self.api.received_audio[name.lower()], self.audio)
        await wait_for(lambda: self.api.queue("garten").state == PlaybackState.PLAYING)
        await asyncio.to_thread(self.casts[0].media_controller.pause)
        await wait_for(lambda: self.api.queue("sauna").state == PlaybackState.PAUSED)
        self.assertEqual(self.api.queue("garten").state, PlaybackState.PLAYING)
        await asyncio.to_thread(self.casts[0].set_volume, 0.42)
        await wait_for(lambda: self.api.players["sauna"].volume_level == 42)
        await asyncio.to_thread(self.casts[0].media_controller.stop)
        await wait_for(lambda: self.api.queue("sauna").state == PlaybackState.IDLE)
        old_ids = {name: info.properties[b"id"] for name, info in self.found.items()}
        for cast in self.casts:
            await asyncio.to_thread(cast.disconnect, timeout=3)
        self.casts = []
        self.stop.set()
        await asyncio.wait_for(self.task, 20)
        self.assertIsNotNone(self.runtime.process.returncode)
        self.assertEqual(self.api.queue("garten").state, PlaybackState.IDLE,
                         {"runtime": self.runtime.snapshot,
                          "writes": [(command, args.get("queue_id", args.get("player_id")))
                                     for command, args in self.api.writes()]})
        self.assertFalse(self.runtime.snapshot["cleanup_unconfirmed"])
        self.assertFalse(self.runtime.snapshot["audio_verified"])
        # Native installation state plus stable bridge IDs must preserve Cast
        # UUIDs across runtime restart, without replaying either media selection.
        self.found.clear()
        self.stop = asyncio.Event()
        self.runtime = Runtime(self.settings, data=self.directory / "data", certificate=self.certificate,
                               binary=os.environ["CASTSPIN_NATIVE_BINARY"])
        self.task = asyncio.create_task(self.runtime.run(self.stop))
        await wait_for(lambda: self.runtime.snapshot.get("connected_bridges") == 2)
        await wait_for(lambda: len(self.found) == 2)
        self.assertEqual({name: info.properties[b"id"] for name, info in self.found.items()}, old_ids)
        self.assertEqual(sum(command == "player_queues/play_media"
                             for command, _ in self.api.writes()), 2)


if __name__ == "__main__":
    unittest.main()
