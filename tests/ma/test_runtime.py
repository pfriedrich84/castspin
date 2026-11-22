# SPDX-License-Identifier: Apache-2.0
"""Runtime lifecycle/configuration tests, not stock-sender acceptance."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from music_assistant_models.enums import PlayerType
from music_assistant_models.player import DeviceInfo

from castspin.app.ma_mirror import exportable
from castspin.app.runtime import Runtime, background_error
from castspin.app.settings import Settings
from test_music_assistant import make_player


class SettingsTests(unittest.TestCase):
    def test_background_exception_does_not_log_remote_details(self):
        with self.assertLogs("castspin", level="ERROR") as captured:
            background_error(None, {"message": "private-test-token",
                                    "exception": RuntimeError("private-test-token")})
        self.assertIn("RuntimeError", captured.output[0])
        self.assertNotIn("private-test-token", "".join(captured.output))

    def test_secret_is_not_represented_and_configuration_is_strict(self):
        value = Settings(True, "https://ma.example", "private-test-token", "192.0.2.10")
        value.validate()
        self.assertNotIn("private-test-token", repr(value))
        for changes in ({"music_assistant_url": "https://user:secret@ma.example"},
                        {"music_assistant_url": "https://ma.example?token=secret"},
                        {"network_address": "0.0.0.0"}, {"network_address": "224.0.0.1"},
                        {"player_port": True}, {"player_port": 8099},
                        {"enabled": "yes"}, {"music_assistant_token": "line\nbreak"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Settings(**(value.__dict__ | changes)).validate()

    def test_loading_missing_invalid_or_unknown_options(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"
            self.assertFalse(Settings.load(path).enabled)
            for text in ('{', '[]', '{"unknown": "private-test-token"}',
                         '{"enabled": "private-test-token"}'):
                path.write_text(text)
                with self.assertRaises(ValueError) as error:
                    Settings.load(path)
                self.assertNotIn("private-test-token", str(error.exception))

    def test_feedback_loop_groups_are_excluded_including_nested_groups(self):
        own = make_player("own", device_info=DeviceInfo(model="CastSpin"))
        nested = make_player("nested", type=PlayerType.GROUP, group_members=["own"])
        group = make_player("group", type=PlayerType.GROUP, group_members=["group", "nested"])
        self.assertFalse(exportable(group, [own, nested, group]))
        self.assertTrue(exportable(make_player("regular", type=PlayerType.GROUP), [own]))


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_or_missing_certificate_starts_no_native_process(self):
        with tempfile.TemporaryDirectory() as directory:
            for settings, expected in (
                (Settings(), "disabled"),
                (Settings(True, "https://ma.example", "private-test-token", "192.0.2.10"), "waiting_for_certificate")):
                with self.subTest(expected=expected):
                    stop = asyncio.Event()
                    runtime = Runtime(settings, data=Path(directory), certificate=Path(directory) / "certs.json")
                    task = asyncio.create_task(runtime.run(stop))
                    try:
                        await asyncio.sleep(0.02)
                        self.assertEqual(runtime.snapshot["cast_receiver"], expected)
                        self.assertIsNone(runtime.process)
                        self.assertNotIn("private-test-token", json.dumps(runtime.snapshot))
                    finally:
                        stop.set()
                        await task

    async def test_unexpected_value_error_is_not_exposed_as_safe_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            certificate = Path(directory) / "certs.json"
            certificate.write_text("{}")
            runtime = Runtime(Settings(True, "https://ma.example", "private-test-token", "192.0.2.10"),
                              data=Path(directory), certificate=certificate)
            with patch.object(runtime, "_configuration", side_effect=ValueError("private-test-token")):
                await runtime.run(asyncio.Event())
            self.assertEqual(runtime.snapshot["cast_receiver"], "error")
            self.assertNotIn("private-test-token", json.dumps(runtime.snapshot))

    async def test_native_failure_is_cleaned_immediately_without_automatic_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            certificate = Path(directory) / "certs.json"
            certificate.write_text("{}")
            runtime = Runtime(Settings(True, "http://127.0.0.1:1", "private-test-token", "127.0.0.1"),
                              data=Path(directory), certificate=certificate, binary="/bin/false")
            await asyncio.wait_for(runtime.run(asyncio.Event()), 3)
            self.assertEqual(runtime.snapshot["cast_receiver"], "error")
            self.assertIsNotNone(runtime.process.returncode)
            self.assertFalse(runtime.snapshot["audio_verified"])
            self.assertNotIn("private-test-token", json.dumps(runtime.snapshot))
            toml = (Path(directory) / "receiver" / "config.toml").read_text()
            self.assertIn('player_bind_host = "127.0.0.1"', toml)
            self.assertIn('manufacturer = "CastSpin"', toml)
            self.assertNotIn("private-test-token", toml)
            self.assertEqual((Path(directory) / "receiver").stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
