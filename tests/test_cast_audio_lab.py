# SPDX-License-Identifier: Apache-2.0
"""Fixture/unit tests, not Cast, sender-authentication or audible-output proof."""

import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import uuid
import wave
from pathlib import Path

from tools.cast_audio_lab import pcm_measurements, run_capture

ROOT = Path(__file__).resolve().parents[1]


class AudioLabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_wav(self, samples):
        path = self.root / "fixture.wav"
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(48000)
            stream.writeframes(b"".join(struct.pack("<hh", n, n) for n in samples))
        return path

    def test_measure_real_pcm_bytes_not_declared_playing_state(self):
        samples = [int(12000 * math.sin(n * 2 * math.pi * 440 / 48000)) for n in range(4800)]
        result = pcm_measurements(self.make_wav(samples))
        self.assertTrue(result["decoded_pcm_observed"])
        self.assertEqual(result["frames"], 4800)
        self.assertEqual(result["duration_seconds"], 0.1)
        self.assertEqual(result["peak_s16"], 12000)
        self.assertGreater(result["rms_s16"], 8000)
        self.assertEqual(len(result["pcm_sha256"]), 64)

    def test_silent_or_empty_pcm_is_not_success(self):
        for samples in ([], [0] * 4800):
            self.assertFalse(pcm_measurements(self.make_wav(samples))["decoded_pcm_observed"])

    def test_missing_bad_and_truncated_wav_are_not_success(self):
        path = self.root / "bad.wav"
        self.assertFalse(pcm_measurements(path)["decoded_pcm_observed"])
        path.write_bytes(b"not a WAV")
        self.assertFalse(pcm_measurements(path)["decoded_pcm_observed"])
        path = self.make_wav([100] * 100)
        path.write_bytes(path.read_bytes()[:-8])
        self.assertFalse(pcm_measurements(path)["decoded_pcm_observed"])

    def test_network_is_explicitly_opt_in(self):
        output = self.root / "unused"
        command = [sys.executable, str(ROOT / "tools/cast_audio_lab.py"), "--output", str(output)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--enable-network-receiver", result.stderr)
        self.assertFalse(output.exists())

    def test_invalid_bounds_do_not_start_receiver(self):
        for duration, port in ((0, 8009), (301, 8009), (10, 22), (10, 65536)):
            with self.assertRaises(ValueError):
                run_capture(receiver="missing", mpv="missing", output=self.root / "unused",
                            duration=duration, port=port, name="Lab", device_id=uuid.uuid4())

    @unittest.skipUnless(os.name == "posix", "Linux lab uses POSIX executables")
    def test_existing_evidence_is_never_overwritten(self):
        receiver = self.root / "receiver"
        receiver.write_text("#!/bin/sh\necho 'openchromecast 1.0.5'\n")
        receiver.chmod(0o700)
        mpv = self.root / "mpv"
        mpv.write_text("#!/bin/sh\necho 'mpv v0.41.0'\n")
        mpv.chmod(0o700)
        marker = self.root / "summary.json"
        marker.write_text(json.dumps({"previous": True}))
        with self.assertRaises(FileExistsError):
            run_capture(receiver=receiver, mpv=mpv, output=self.root, duration=1,
                        port=18009, name="Lab", device_id=uuid.uuid4())
        self.assertEqual(json.loads(marker.read_text()), {"previous": True})


if __name__ == "__main__":
    unittest.main()
