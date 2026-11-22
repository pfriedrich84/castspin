# SPDX-License-Identifier: Apache-2.0
"""Real SDK + reused player over loopback sockets against an MA API simulator.

The simulator is NOT Music Assistant, a Cast sender, a decoder or an audio
endpoint. These tests prove the composition/commands, not YouTube Music playback.
"""
import asyncio
import json
import sys
import unittest
from uuid import uuid4

from aiohttp import web
from cast_audio_lab.vibecast_player import VibecastAudioPlayer
from music_assistant_client import MusicAssistantClient
from music_assistant_models.enums import EventType, PlaybackState, PlayerType
from music_assistant_models.media_items import Radio
from music_assistant_models.player import DeviceInfo, Player
from music_assistant_models.player_queue import PlayerQueue
from music_assistant_models.queue_item import QueueItem
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from castspin.app.ma_mirror import MARKER, MusicAssistantMirror, receiver_id
from castspin.app.music_assistant import MusicAssistantBackend, http_url


async def until(predicate):
    async with asyncio.timeout(3):
        while not predicate():
            await asyncio.sleep(0.01)


def make_player(key, **kwargs):
    defaults = dict(player_id=key, provider="sendspin", type=PlayerType.PLAYER,
                    name=key.title(), available=True, device_info=DeviceInfo(),
                    volume_level=0, volume_muted=True)
    return Player(**(defaults | kwargs))


class MaApiSimulator:
    def __init__(self):
        self.players = {key: make_player(key) for key in ("sauna", "garten")}
        self.queues = {}
        self.calls = []
        self.sockets = set()
        self.error_command = None
        self.stall_command = None
        self.ignore_load = False
        self.release = asyncio.Event()
        self.authorized = False

    def queue(self, key):
        return self.queues.setdefault(key, PlayerQueue(
            key, active=False, display_name=key, available=True, items=0))

    async def event(self, kind, key, data):
        for socket in list(self.sockets):
            await socket.send_json({"event": kind.value, "object_id": key, "data": data})

    async def publish(self, key):
        await self.event(EventType.PLAYER_UPDATED, key, self.players[key].to_dict())
        await self.event(EventType.QUEUE_UPDATED, key, self.queue(key).to_dict())

    async def ws(self, request):
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        self.sockets.add(socket)
        await socket.send_json(dict(server_id="ma-server-test", server_version="test",
                                    schema_version=101, min_supported_schema_version=101))
        try:
            async for raw in socket:
                message = json.loads(raw.data)
                command, args = message["command"], message["args"] or {}
                self.calls.append((command, args))
                if self.error_command == command:
                    await socket.send_json({"message_id": message["message_id"],
                                            "error_code": 999,
                                            "details": "secret-token-and-signed-url"})
                    continue
                result = None
                if command == "auth":
                    self.authorized = args["token"] == "test-token"
                    result = self.authorized
                elif not self.authorized:
                    raise AssertionError("SDK sent command before authentication")
                elif command == "players/all":
                    result = [player.to_dict() for player in self.players.values()]
                elif command == "player_queues/all":
                    result = [self.queue(key).to_dict() for key in self.players]
                elif command in {"providers", "providers/manifests", "dashboard/dashboards",
                                 "dashboard/sessions"}:
                    result = []
                elif command == "player_queues/get_active_queue":
                    result = self.queue(args["player_id"]).to_dict()
                elif command.startswith("player_queues/"):
                    key = args["queue_id"]
                    queue = self.queue(key)
                    if command == "player_queues/play_media" and self.ignore_load:
                        pass
                    elif command == "player_queues/play_media":
                        assert args["option"] == "replace"
                        queue.current_item = QueueItem(
                            key, uuid4().hex, "Test", 60,
                            media_item=Radio(item_id=args["media"], provider="builtin",
                                             name="Test", provider_mappings=set()))
                        queue.active, queue.items, queue.state = True, 1, PlaybackState.PLAYING
                        self.players[key].active_source = key
                    elif command == "player_queues/pause":
                        queue.state = PlaybackState.PAUSED
                    elif command == "player_queues/play":
                        queue.state = PlaybackState.PLAYING
                    elif command == "player_queues/stop":
                        queue.state = PlaybackState.IDLE
                    elif command == "player_queues/seek":
                        queue.elapsed_time = args["position"]
                    else:
                        raise AssertionError(command)
                    await self.publish(key)
                elif command.startswith("players/cmd/"):
                    key = args["player_id"]
                    player = self.players[key]
                    if command.endswith("/volume_set"):
                        player.volume_level = args["volume_level"]
                    elif command.endswith("/volume_mute"):
                        player.volume_muted = args["muted"]
                    elif command.endswith("/group_volume"):
                        player.group_volume = args["volume_level"]
                    elif command.endswith("/group_volume_mute"):
                        player.group_volume_muted = args["muted"]
                    else:
                        raise AssertionError(command)
                    await self.publish(key)
                else:
                    raise AssertionError(command)
                if self.stall_command == command:
                    await self.release.wait()
                await socket.send_json({"message_id": message["message_id"], "result": result})
        finally:
            self.sockets.discard(socket)
        return socket

    def writes(self):
        return [(command, args) for command, args in self.calls
                if command.startswith("players/cmd/")
                or command in {"player_queues/play_media", "player_queues/play",
                               "player_queues/pause", "player_queues/stop", "player_queues/seek"}]


class MusicAssistantTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.api = MaApiSimulator()
        app = web.Application()
        app.router.add_get("/ws", self.api.ws)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        self.backend = None
        self.mirror_task = None

    def client(self, token="test-token"):
        return MusicAssistantClient(self.url, None, token=token)

    async def backend_for(self, key="sauna", **kwargs):
        self.backend = MusicAssistantBackend(self.client(), key, **kwargs)
        await self.backend.start()
        return self.backend

    async def asyncTearDown(self):
        self.api.release.set()
        if self.mirror_task:
            self.mirror_task.cancel()
            await asyncio.gather(self.mirror_task, return_exceptions=True)
        if self.backend:
            try:
                await self.backend.shutdown()
            except RuntimeError:
                pass
        for socket in list(self.api.sockets):
            await socket.close()
        await self.runner.cleanup()

    async def test_reused_player_dispatches_load_controls_and_actual_ma_state(self):
        backend = await self.backend_for()
        player = VibecastAudioPlayer("ws://127.0.0.1:1/player", "id", "Sauna", backend)
        await player.handle_message({"type": "load", "sessionId": "session", "media": {
            "mediaSessionId": 1, "streams": [{"url": "https://audio.example/song.flac"}],
            "autoplay": True, "startTime": 12}})
        self.assertEqual(backend.status().state, "PLAYING")
        self.assertEqual(self.api.queue("sauna").elapsed_time, 12)
        # Initializing a Cast session must preserve MA's zero volume and mute.
        self.assertEqual(backend.status().volume, 0)
        self.assertTrue(backend.status().muted)
        await player.handle_message({"type": "pause", "sessionId": "session"})
        self.assertEqual(backend.status().state, "PAUSED")
        await player.handle_message({"type": "play", "sessionId": "session"})
        await backend.set_volume(0.37, False)
        self.assertEqual(backend.status().volume, 0.37)
        self.assertFalse(backend.status().muted)
        await player.handle_message({"type": "stop", "sessionId": "session"})
        self.assertEqual(backend.status().state, "IDLE")
        self.assertFalse(any(args.get("player_id") == "garten"
                             or args.get("queue_id") == "garten"
                             for _, args in self.api.writes()))

    async def test_staged_load_does_not_start_or_stop_unrelated_audio(self):
        backend = await self.backend_for()
        await backend.initialize_volume()
        await backend.load("http://audio.example/a.mp3", "audio/mpeg", False, 0)
        self.assertEqual(self.api.writes(), [])
        await backend.play()
        self.assertEqual(backend.status().state, "PLAYING")

    async def test_stop_does_not_stop_a_replacement_item_even_at_same_url(self):
        backend = await self.backend_for()
        await backend.stop()
        self.assertEqual(self.api.writes(), [])
        await backend.load("http://audio.example/a.mp3", "audio/mpeg", True, 0)
        self.api.queue("sauna").current_item.queue_item_id = "external-selection"
        await self.api.publish("sauna")
        await until(lambda: backend.status().state == "IDLE")
        await backend.stop()
        self.assertNotIn("player_queues/stop", [command for command, _ in self.api.writes()])

    async def test_already_applied_cancelled_load_can_be_stopped_without_replay(self):
        backend = await self.backend_for()
        self.api.stall_command = "player_queues/play_media"
        task = asyncio.create_task(backend.load("http://audio.example/a.mp3", "audio/mpeg", True, 0))
        await until(lambda: self.api.queue("sauna").current_item is not None)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.api.release.set()
        await backend.stop()
        self.assertEqual(self.api.queue("sauna").state, PlaybackState.IDLE)
        self.assertEqual(sum(command == "player_queues/play_media"
                             for command, _ in self.api.writes()), 1)

    async def test_unknown_ma_playback_state_is_an_error_not_fake_playing(self):
        backend = await self.backend_for()
        await backend.load("http://audio.example/a.mp3", "audio/mpeg", True, 0)
        self.api.queue("sauna").state = PlaybackState.UNKNOWN
        await self.api.publish("sauna")
        await until(lambda: backend.client.player_queues.get("sauna").state == PlaybackState.UNKNOWN)
        self.assertEqual(backend.status().state, "IDLE")
        self.assertEqual(backend.status().idle_reason, "ERROR")

    async def test_timeout_and_remote_errors_are_bounded_and_redacted(self):
        backend = await self.backend_for(timeout=0.15)
        self.api.error_command = "players/cmd/volume_set"
        with self.assertRaisesRegex(RuntimeError, "^Music Assistant command failed$"):
            await backend.set_volume(0.2, False)
        self.api.error_command = None
        self.api.stall_command = "players/cmd/volume_set"
        with self.assertRaisesRegex(RuntimeError, "^Music Assistant command failed$"):
            await backend.set_volume(0.2, False)
        self.api.release.set()

    async def test_disconnected_or_grouped_individual_player_fails_closed(self):
        backend = await self.backend_for()
        self.api.players["sauna"].synced_to = "garten"
        await self.api.publish("sauna")
        await until(lambda: backend.client.players.get("sauna").synced_to == "garten")
        with self.assertRaises(RuntimeError):
            await backend.load("https://audio.example/a.flac", "audio/flac", True, 0)
        self.assertEqual(self.api.writes(), [])
        for socket in list(self.api.sockets):
            await socket.close()
        await until(lambda: backend._reader.done())
        self.assertEqual(backend.status().idle_reason, "ERROR")

    async def test_unconfirmed_load_never_claims_old_item_at_same_url(self):
        url = "http://audio.example/a.mp3"
        queue = self.api.queue("sauna")
        queue.current_item = QueueItem("sauna", "old-item", "Old", 60,
            media_item=Radio(item_id=url, provider="builtin", name="Old", provider_mappings=set()))
        queue.state = PlaybackState.PLAYING
        self.api.players["sauna"].active_source = "sauna"
        self.api.ignore_load = True
        backend = await self.backend_for()
        with self.assertRaisesRegex(RuntimeError, "did not confirm"):
            await backend.load(url, "audio/mpeg", True, 0)
        self.assertTrue(backend.command_outcome_unknown)
        self.assertEqual(backend.status().idle_reason, "ERROR")
        with self.assertRaisesRegex(RuntimeError, "unconfirmed"):
            await backend.stop()
        self.assertNotIn("player_queues/stop", [command for command, _ in self.api.writes()])
        self.assertEqual(queue.current_item.queue_item_id, "old-item")

    async def test_failed_authentication_is_redacted_and_closes_the_session(self):
        self.backend = MusicAssistantBackend(self.client(token="wrong-test-token"), "sauna")
        with self.assertRaisesRegex(RuntimeError, "^Music Assistant initialization failed$"):
            await self.backend.start()
        await self.backend.shutdown()
        self.assertFalse(self.backend.client.connection.connected)
        self.assertEqual(self.api.writes(), [])

    async def test_async_notifications_are_bounded_and_cleaned_up(self):
        backend = await self.backend_for()
        entered, wait = asyncio.Event(), asyncio.Event()
        async def listener(_status):
            entered.set()
            await wait.wait()
        backend.add_status_listener(listener)
        for _ in range(100):
            backend._emit()
        await asyncio.wait_for(entered.wait(), 1)
        self.assertEqual(len(backend._notifications), 1)
        await backend.shutdown()
        self.assertEqual(backend._notifications, {})

    async def test_explicit_ma_group_uses_group_volume_api(self):
        self.api.players["sauna"].type = PlayerType.GROUP
        self.api.players["sauna"].group_volume = 10
        self.api.players["sauna"].group_volume_muted = False
        backend = await self.backend_for()
        await backend.initialize_volume()
        await backend.set_volume(0.2, True)
        self.assertEqual(backend.status().volume, 0.2)
        self.assertTrue(backend.status().muted)
        self.assertEqual([command for command, _ in self.api.writes()],
                         ["players/cmd/group_volume", "players/cmd/group_volume_mute"])

    async def test_inventory_registers_every_public_target_and_reconciles(self):
        self.api.players.update({
            "group": make_player("group", type=PlayerType.GROUP),
            "offline": make_player("offline", available=False),
            "internal": make_player("internal", private=True),
            "disabled": make_player("disabled", enabled=False),
            "own": make_player("own", name="Sauna" + MARKER),
            "renamed-own": make_player("renamed-own", device_info=DeviceInfo(model="CastSpin")),
            "lamp": make_player("lamp", type=PlayerType.LIGHT),
        })
        registrations, reports, sockets = [], [], {}

        async def bridge(socket):
            registration = json.loads(await socket.recv())["player"]
            key = registration["playerId"]
            registrations.append(registration)
            sockets[key] = socket
            try:
                async for raw in socket:
                    reports.append(json.loads(raw))
            except ConnectionClosed:
                pass  # A cancelled upstream player closes its socket with 1011.
            finally:
                if sockets.get(key) is socket:
                    sockets.pop(key)

        async with serve(bridge, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            mirror = MusicAssistantMirror(self.client(), bridge_url=f"ws://127.0.0.1:{port}/player")
            initialized = asyncio.Event()
            self.mirror_task = asyncio.create_task(mirror.run(initialized))
            await asyncio.wait_for(initialized.wait(), 3)
            await until(lambda: len(sockets) == 4)
            self.assertEqual(set(mirror.routes), {"sauna", "garten", "group", "offline"})
            self.assertEqual(self.api.writes(), [])
            sauna = receiver_id("ma-server-test", "sauna")
            garten = receiver_id("ma-server-test", "garten")
            self.assertNotEqual(sauna, garten)
            for key, url in ((sauna, "https://audio.example/a.flac"),
                             (garten, "https://audio.example/b.flac")):
                await sockets[key].send(json.dumps({"type": "load", "sessionId": key, "media": {
                    "mediaSessionId": 1, "streams": [{"url": url}], "autoplay": True}}))
            await until(lambda: all(self.api.queue(key).current_item
                                   for key in ("sauna", "garten")))
            await until(lambda: all(mirror.routes[key].backend.status().state == "PLAYING"
                                   for key in ("sauna", "garten")))
            await sockets[sauna].send(json.dumps({"type": "stop", "sessionId": sauna}))
            await until(lambda: self.api.queue("sauna").state == PlaybackState.IDLE)
            self.assertEqual(self.api.queue("garten").state, PlaybackState.PLAYING)
            self.api.players["sauna"].name = "Sauna Neu"
            await self.api.publish("sauna")
            await until(lambda: any(item["name"] == "Sauna Neu" + MARKER for item in registrations))
            self.assertEqual(mirror.routes["sauna"].player.player_id, sauna)
            self.api.players["garten"].enabled = False
            with self.assertLogs("cast_audio_lab.vibecast_player", level="WARNING") as logs:
                await self.api.publish("garten")
                await until(lambda: "garten" not in mirror.routes)
                await until(lambda: mirror.cleanup_unconfirmed)
            self.assertIn("Output cleanup failed", "\n".join(logs.output))
            self.api.players["new"] = make_player("new")
            await self.api.event(EventType.PLAYER_ADDED, "new", self.api.players["new"].to_dict())
            await until(lambda: "new" in mirror.routes)
            self.assertNotIn("test-token", json.dumps(mirror.status()))
            self.assertNotIn("https://audio.example", json.dumps(mirror.status()))
            self.mirror_task.cancel()
            await asyncio.gather(self.mirror_task, return_exceptions=True)
            self.mirror_task = None
            self.assertEqual(mirror.routes, {})

    async def test_duplicate_names_have_distinct_names_and_stable_ids(self):
        backend = await self.backend_for()
        self.api.players["garten"].name = "Sauna"
        await self.api.publish("garten")
        await until(lambda: backend.client.players.get("garten").name == "Sauna")
        mirror = MusicAssistantMirror(backend.client, bridge_url="ws://127.0.0.1:1/player")
        try:
            await mirror.reconcile()
            names = [route.name for route in mirror.routes.values()]
            self.assertEqual(len(set(names)), 2)
            self.assertTrue(all(name.startswith("Sauna · ") and name.endswith(MARKER)
                                for name in names))
            self.assertEqual(mirror.routes["sauna"].player.player_id,
                             receiver_id("ma-server-test", "sauna"))
            self.assertNotEqual(receiver_id("different-ma-server", "sauna"),
                                receiver_id("ma-server-test", "sauna"))
            self.assertEqual(self.api.writes(), [])
        finally:
            await asyncio.gather(*(mirror._remove(key) for key in list(mirror.routes)))

    def test_input_urls_and_no_bootstrap_import(self):
        for url in ("file:///etc/passwd", "ftp://audio/a", "http://u:p@host/a",
                    "http://host:invalid/a", "http://host/a\n", "http://host/#secret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                http_url(url)
        self.assertEqual(http_url("https://host/a?signature=x"), "https://host/a?signature=x")
        for module in ("container_bootstrap", "bundle_artifact", "container_entrypoint", "runtime"):
            self.assertNotIn("cast_audio_lab." + module, sys.modules)


if __name__ == "__main__":
    unittest.main()
