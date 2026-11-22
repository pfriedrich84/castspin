# SPDX-License-Identifier: Apache-2.0
"""Automatic MA inventory → independent reused Cast player registrations.

This component needs an already running, correctly configured Vibecast frontend.
It does not install one, fetch authentication material or prove phone playback.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from cast_audio_lab.vibecast_player import VibecastAudioPlayer
from music_assistant_models.enums import EventType, PlayerType

from .music_assistant import MusicAssistantBackend

MARKER = " [CastSpin]"


def receiver_id(server_id, player_id):
    """Keep device identity independent of names, addresses and list order."""
    return "castspin-ma-" + uuid5(
        NAMESPACE_URL, f"https://castspin.invalid/ma/{len(server_id)}:{server_id}/{player_id}"
    ).hex


def exportable(player):
    """Mirror user-facing MA playback targets, not hidden/internal/own devices."""
    return (player.type in {PlayerType.PLAYER, PlayerType.STEREO_PAIR, PlayerType.GROUP}
            and player.enabled and not player.private and MARKER not in player.name
            and not (player.device_info.model or "").casefold().startswith("castspin")
            and not (player.device_info.manufacturer or "").casefold().startswith("castspin"))


@dataclass
class Route:
    name: str
    backend: MusicAssistantBackend
    player: VibecastAudioPlayer
    task: asyncio.Task


class MusicAssistantMirror:
    """One MA connection, one isolated backend/player per public MA target."""

    def __init__(self, client, *, bridge_url="ws://127.0.0.1:8010/player", timeout=10):
        self.client = client
        self.bridge_url = bridge_url
        self.timeout = timeout
        self.routes: dict[str, Route] = {}
        self.cleanup_unconfirmed = False

    async def run(self, initialized=None):
        ready, changed = asyncio.Event(), asyncio.Event()
        reader = asyncio.create_task(self.client.start_listening(ready))
        waiter = asyncio.create_task(ready.wait())
        unsubscribe = None
        try:
            async with asyncio.timeout(self.timeout):
                await asyncio.wait((reader, waiter), return_when=asyncio.FIRST_COMPLETED)
                if reader.done():
                    reader.result()
                    raise RuntimeError("Music Assistant disconnected during initialization")
            unsubscribe = self.client.subscribe(lambda _: changed.set(), (
                EventType.PLAYER_ADDED, EventType.PLAYER_UPDATED, EventType.PLAYER_REMOVED))
            while not reader.done():
                changed.clear()
                await self.reconcile()
                if initialized:
                    initialized.set()  # Inventory initialized, NOT Cast/audio readiness.
                try:
                    async with asyncio.timeout(2):
                        await changed.wait()
                except TimeoutError:
                    pass
            raise RuntimeError("Music Assistant disconnected; no playback is replayed")
        except asyncio.CancelledError:
            raise
        except Exception:
            raise RuntimeError("Music Assistant mirror failed") from None
        finally:
            if unsubscribe:
                unsubscribe()
            await asyncio.gather(*(self._remove(key) for key in list(self.routes)))
            waiter.cancel()
            reader.cancel()
            await asyncio.gather(waiter, reader, return_exceptions=True)
            try:
                async with asyncio.timeout(self.timeout):
                    await self.client.disconnect()
            except Exception:
                self.cleanup_unconfirmed = True

    async def reconcile(self):
        targets = {player.player_id: player for player in self.client.players
                   if exportable(player)}
        duplicates = Counter(player.name for player in targets.values())
        names = {key: player.name + (" · " + receiver_id(
            self.client.server_info.server_id, key)[-6:] if duplicates[player.name] > 1 else "")
                 + MARKER for key, player in targets.items()}
        obsolete = [key for key, route in self.routes.items()
                    if key not in targets or route.name != names[key] or route.task.done()]
        await asyncio.gather(*(self._remove(key) for key in obsolete))
        for key in targets:
            if key in self.routes:
                continue
            backend = MusicAssistantBackend(self.client, key, timeout=self.timeout,
                                            manage_connection=False)
            await backend.start()
            player = VibecastAudioPlayer(
                self.bridge_url, receiver_id(self.client.server_info.server_id, key),
                names[key], backend)
            self.routes[key] = Route(names[key], backend, player,
                                     asyncio.create_task(player.run()))

    async def _remove(self, key):
        route = self.routes.pop(key)
        route.task.cancel()
        await asyncio.gather(route.task, return_exceptions=True)
        try:
            await route.backend.shutdown()
        except Exception:
            # A disconnected server cannot confirm a Stop; never claim cleanup
            # or stop an arbitrary replacement item on the next connection.
            self.cleanup_unconfirmed = True

    def status(self):
        """Safe diagnostics: no token, media URL, metadata or raw SDK errors."""
        return {"cleanup_unconfirmed": self.cleanup_unconfirmed, "routes": [
            {"music_assistant_player_id": key, "name": route.name,
             "receiver_id": route.player.player_id,
             "playback_state": route.backend.status().state,
             "command_outcome_unknown": route.backend.command_outcome_unknown,
             "notification_failed": route.backend.notification_failed}
            for key, route in self.routes.items()
        ]}
