# SPDX-License-Identifier: Apache-2.0
"""Real native receiver + decoder, LOCAL synthetic-controller evidence ONLY.

Opt-in requires CASTSPIN_LAB_RECEIVER and CASTSPIN_LAB_MPV. No phone, Google
device authentication, audible output or Sendspin client is exercised here.
"""

import functools
import ipaddress
import json
import math
import os
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
import wave
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIVER = os.environ.get("CASTSPIN_LAB_RECEIVER")
MPV = os.environ.get("CASTSPIN_LAB_MPV")


def wait_for(check, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError("timed out waiting for local lab condition")


class FixtureHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.server.requests_seen.append(self.path)
        return super().do_GET()

    def log_message(self, *_args):
        pass


@unittest.skipUnless(RECEIVER and MPV, "explicit external-receiver/decoder opt-in required")
class NativeAudioLabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "tone.wav"
        with wave.open(str(self.source), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(48000)
            stream.writeframes(b"".join(
                struct.pack("<hh", sample, sample)
                for n in range(48000)
                for sample in (int(10000 * math.sin(2 * math.pi * 440 * n / 48000)),)
            ))
        # Real FLAC encoding, so the receive path must really decode compression.
        subprocess.run([
            MPV, "--no-config", "--load-scripts=no", "--no-video",
            f"--o={self.root / 'tone.flac'}", "--of=flac", "--oac=flac", str(self.source),
        ], check=True, capture_output=True, timeout=15)

    def start_media(self, https=False):
        handler = functools.partial(FixtureHandler, directory=str(self.root))
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        httpd.requests_seen = []
        self.addCleanup(httpd.server_close)
        ca = None
        if https:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Local media fixture")])
            now = datetime.now(timezone.utc)
            cert = (
                x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=1))
                .not_valid_after(now + timedelta(days=1))
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName([
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]), critical=False).sign(key, hashes.SHA256())
            )
            ca = self.root / "media-ca.pem"
            ca.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path = self.root / "media-key.pem"
            key_path.write_bytes(key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
            key_path.chmod(0o600)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(ca, key_path)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(httpd.shutdown)
        url = f"{'https' if https else 'http'}://127.0.0.1:{httpd.server_port}/tone.flac"
        return httpd, url, ca

    def exercise(self, *, https=False, trust_media=True, send_load=True):
        from pychromecast import Chromecast
        from pychromecast.models import CastInfo, HostServiceInfo

        httpd, url, ca = self.start_media(https=https)
        output = self.root / "capture"
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        device_id = uuid.uuid4()
        command = [
            sys.executable, str(ROOT / "tools/cast_audio_lab.py"),
            "--enable-network-receiver", "--receiver", RECEIVER, "--mpv", MPV,
            "--output", str(output), "--duration", "9", "--port", str(port),
            "--device-id", str(device_id), "--name", f"CastSpin CI Lab {device_id.hex[:8]}",
        ]
        if ca and trust_media:
            command += ["--media-ca", str(ca)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())

        def listening():
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(f"lab exited before listening: {stdout} {stderr}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return True
            except OSError:
                return False

        wait_for(listening)
        if send_load:
            # Explicit host + declared cast type: deliberately NO mDNS acceptance proof.
            info = CastInfo({HostServiceInfo("127.0.0.1", port)}, device_id,
                            "CastSpin Audio Lab", "Local synthetic sender test",
                            "127.0.0.1", port, "audio", "CastSpin")
            cast = Chromecast(info, tries=1, timeout=2, retry_wait=0.1)
            try:
                cast.wait(timeout=3)
                self.assertIsNotNone(cast.status)
                cast.media_controller.play_media(url, "audio/flac")
                if not https or trust_media:
                    wait_for(lambda: bool(httpd.requests_seen), timeout=3)
                    time.sleep(0.8)
                    cast.media_controller.stop(timeout=3)
            finally:
                cast.disconnect(timeout=3)
        stdout, stderr = process.communicate(timeout=18)
        self.assertTrue((output / "summary.json").exists(), stderr)
        result = json.loads((output / "summary.json").read_text())
        self.assertEqual(json.loads(stdout), result)
        self.assertEqual(result["google_device_auth"], "not_proven")
        self.assertEqual(result["phone_discovery"], "not_tested")
        self.assertEqual(result["audible_playback"], "not_tested")
        self.assertEqual(result["sendspin"], "not_implemented")
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        return process.returncode, result, httpd.requests_seen

    def assert_exact_decode(self, https):
        from tools.cast_audio_lab import pcm_measurements

        code, result, requests = self.exercise(https=https)
        self.assertEqual(code, 0, result)
        self.assertIn("/tone.flac", requests)
        self.assertTrue(result["decoded_pcm_observed"], result)
        self.assertFalse(result["backend_failure_detected"])
        original = pcm_measurements(self.source)
        self.assertEqual(result["frames"], original["frames"])
        self.assertEqual(result["pcm_sha256"], original["pcm_sha256"])

    def test_http_cast_load_retrieves_and_decodes_exact_flac(self):
        self.assert_exact_decode(https=False)

    def test_https_cast_load_with_explicit_trusted_ca(self):
        self.assert_exact_decode(https=True)

    def test_untrusted_https_media_does_not_report_audio_success(self):
        code, result, requests = self.exercise(https=True, trust_media=False)
        self.assertEqual(code, 1, result)
        self.assertFalse(result["decoded_pcm_observed"])
        self.assertEqual(requests, [])

    def test_no_media_load_is_not_audio_success(self):
        code, result, requests = self.exercise(send_load=False)
        self.assertEqual(code, 1, result)
        self.assertFalse(result["decoded_pcm_observed"])
        self.assertEqual(requests, [])


if __name__ == "__main__":
    unittest.main()
