# SPDX-License-Identifier: Apache-2.0
"""One Cast Audio Receiver Lab output backed by the official MA client.

MA fetches/decodes the URL and owns the player's audio transport. This is not a
Sendspin server. A LOAD replaces the explicitly selected MA target's queue.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import replace
from urllib.parse import urlsplit

from cast_audio_lab.backend import MediaMetadata, PlaybackStatus
from music_assistant_client import MusicAssistantClient
from music_assistant_models.enums import EventType, PlayerType, QueueOption


def http_url(value: str) -> str:
    """Reject userinfo, local files, custom schemes and URL fragments."""
    try:
        parts = urlsplit(value)
        valid = (parts.scheme in {"http", "https"} and parts.hostname
                 and parts.username is None and parts.password is None
                 and not parts.fragment and parts.port != 0
                 and not any(character.isspace() for character in value))
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError("Expected an absolute HTTP(S) URL without userinfo or fragment")
    return value


class MusicAssistantBackend:
    """Implement the pinned upstream AudioBackend; never claim optimistic audio."""

    def __init__(self, client: MusicAssistantClient, player_id: str, *, timeout=10,
                 manage_connection=True):
        self.client = client
        self.player_id = player_id
        self.timeout = timeout
        self.manage_connection = manage_connection
        self.metadata = MediaMetadata()
        self._status = PlaybackStatus(volume=0)
        self._listeners = []
        self._notifications = {}
        self.notification_failed = False
        self.command_outcome_unknown = False
        self._controls = []
        self._reader = None
        self._shutdown_task = None
        self._unsubscribe = None
        self._item_id = None
        self._previous_item_id = None
        self._submitted = False
        self._start_time = 0
        self._closed = False
        self._lock = asyncio.Lock()

    async def start(self):
        if not self.manage_connection:
            self._subscribe()
            return
        ready = asyncio.Event()
        self._reader = asyncio.create_task(self.client.start_listening(ready))
        waiter = asyncio.create_task(ready.wait())
        try:
            async with asyncio.timeout(self.timeout):
                await asyncio.wait((self._reader, waiter), return_when=asyncio.FIRST_COMPLETED)
                if self._reader.done():
                    self._reader.result()
                    raise RuntimeError("Music Assistant disconnected during initialization")
            self._player()
            self._subscribe()
        except asyncio.CancelledError:
            raise
        except Exception:
            raise RuntimeError("Music Assistant initialization failed") from None
        finally:
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)

    def _subscribe(self):
        self._unsubscribe = self.client.subscribe(self._updated, (
            EventType.PLAYER_UPDATED, EventType.PLAYER_REMOVED,
            EventType.QUEUE_UPDATED, EventType.QUEUE_TIME_UPDATED,
        ), id_filter=self.player_id)

    def _player(self):
        player = self.client.players.get(self.player_id)
        if (self._closed or not self.client.connection.connected or player is None
                or not player.available or not player.enabled or player.private
                or player.needs_setup
                or (player.type == PlayerType.PLAYER
                    and (player.synced_to or player.active_group
                         or len(player.group_members) > 1))):
            raise RuntimeError("Selected Music Assistant player is unavailable or grouped")
        return player

    async def _call(self, operation):
        try:
            async with asyncio.timeout(self.timeout):
                return await operation
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            raise RuntimeError("Music Assistant connection closed") from None
        except Exception:
            # Neither an SDK/server exception nor its traceback may disclose a
            # token, signed URL, metadata or a remote error response.
            raise RuntimeError("Music Assistant command failed") from None

    async def _owned_queue(self):
        self._player()
        if not self._submitted:
            return None
        queue = await self._call(self.client.player_queues.get_active_queue(self.player_id))
        item = queue.current_item if queue else None
        if (queue and queue.queue_id == self.player_id and item
                and item.media_item and item.media_item.item_id == self._status.url
                and item.queue_item_id != self._previous_item_id
                and (self._item_id is None or item.queue_item_id == self._item_id)):
            self._item_id = item.queue_item_id
            return queue
        return None

    async def set_metadata(self, metadata):
        # Cast metadata stays in the reused player's session; MA extracts its
        # own metadata for external URLs. Do not add items to MA's library.
        self.metadata = metadata

    async def load(self, url, content_type, autoplay, start_time):
        http_url(url)
        if not math.isfinite(start_time) or start_time < 0:
            raise ValueError("Invalid start time")
        async with self._lock:
            self._player()
            await self._stop_owned()
            self._status = replace(self._status, url=url, content_type=content_type,
                                   state="PAUSED", current_time=start_time, idle_reason=None)
            self._start_time = int(start_time)
            if autoplay:
                await self._begin()
            self._emit()

    async def _begin(self):
        self._player()
        before = await self._call(self.client.player_queues.get_active_queue(self.player_id))
        self._previous_item_id = (before.current_item.queue_item_id
                                  if before and before.current_item else None)
        self._submitted = True  # A cancelled/failed request may have been applied.
        self.command_outcome_unknown = True
        self._status.state = "BUFFERING"
        await self._call(self.client.player_queues.play_media(
            self.player_id, self._status.url, option=QueueOption.REPLACE))
        if await self._owned_queue() is None:
            raise RuntimeError("Music Assistant did not confirm the requested queue item")
        self.command_outcome_unknown = False
        if self._start_time:
            await self._call(self.client.player_queues.seek(self.player_id, self._start_time))

    async def play(self):
        async with self._lock:
            self._player()
            if not self._status.url:
                return
            if not self._submitted:
                await self._begin()
            elif await self._owned_queue():
                await self._call(self.client.player_queues.play(self.player_id))
            else:
                raise RuntimeError("Music Assistant queue ownership changed")
            self._emit()

    async def pause(self):
        async with self._lock:
            if await self._owned_queue():
                await self._call(self.client.player_queues.pause(self.player_id))
            self._emit()

    async def seek(self, position):
        if not math.isfinite(position) or position < 0:
            raise ValueError("Invalid seek position")
        async with self._lock:
            self._player()
            if not self._submitted:
                self._start_time = int(position)
                self._status.current_time = position
            elif await self._owned_queue():
                await self._call(self.client.player_queues.seek(self.player_id, int(position)))
            else:
                raise RuntimeError("Music Assistant queue ownership changed")
            self._emit()

    async def _stop_owned(self):
        if self._submitted:
            if await self._owned_queue():
                await self._call(self.client.player_queues.stop(self.player_id))
                self.command_outcome_unknown = False
            elif self.command_outcome_unknown:
                # MA has no RPC cancellation/CAS: a request may still apply
                # remotely. Do not stop the old item or claim cleanup succeeded.
                raise RuntimeError("Music Assistant load outcome is unconfirmed")
        self._submitted = False
        self._item_id = None
        self._previous_item_id = None
        self._status = replace(self._status, url=None, state="IDLE", current_time=0,
                               idle_reason="CANCELLED")

    async def stop(self):
        async with self._lock:
            await self._stop_owned()
            self._emit()

    async def initialize_volume(self):
        # MA owns volume policy: preserve zero/mute; never unmute or jump to 25%.
        player = self._player()
        level, muted = self._volume(player)
        if level is None or muted is None:
            raise RuntimeError("Music Assistant cannot report the player's volume")
        self._emit()

    async def set_volume(self, level, muted):
        if not math.isfinite(level) or not 0 <= level <= 1 or not isinstance(muted, bool):
            raise ValueError("Invalid volume")
        async with self._lock:
            player = self._player()
            group = player.type != PlayerType.PLAYER
            volume_set = self.client.players.group_volume if group else self.client.players.volume_set
            volume_mute = (self.client.players.group_volume_mute if group
                           else self.client.players.volume_mute)
            await self._call(volume_set(self.player_id, round(level * 100)))
            await self._call(volume_mute(self.player_id, muted))
            self._emit()

    @staticmethod
    def _volume(player):
        if player.type != PlayerType.PLAYER:
            return player.group_volume, player.group_volume_muted
        return player.volume_level, player.volume_muted

    def status(self):
        status = replace(self._status)
        try:
            player = self._player()
        except RuntimeError:
            return replace(status, state="IDLE", idle_reason="ERROR")
        level, muted = self._volume(player)
        if level is not None:
            status.volume = level / 100
        if muted is not None:
            status.muted = muted
        if self.command_outcome_unknown:
            return replace(status, state="IDLE", idle_reason="ERROR")
        if self._submitted:
            queue = self.client.player_queues.get(self.player_id)
            if (queue and queue.current_item and self._item_id is not None
                    and queue.current_item.queue_item_id == self._item_id
                    and player.active_source == self.player_id):
                status.state = queue.state.value.upper()
                if status.state not in {"IDLE", "PLAYING", "PAUSED"}:
                    status.state, status.idle_reason = "IDLE", "ERROR"
                status.current_time = max(0, queue.corrected_elapsed_time)
                if status.state == "IDLE" and status.idle_reason != "ERROR":
                    status.idle_reason = "FINISHED" if queue.ended else "CANCELLED"
            elif self._item_id is not None:
                status.state, status.idle_reason = "IDLE", "CANCELLED"
        return status

    def add_status_listener(self, listener):
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_status_listener(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def add_control_listener(self, listener):
        if listener not in self._controls:
            self._controls.append(listener)

    def remove_control_listener(self, listener):
        if listener in self._controls:
            self._controls.remove(listener)

    def _updated(self, _event):
        self._emit()

    def _emit(self):
        # Bound asynchronous notifications to one task per listener. The pinned
        # VibecastAudioPlayer installs synchronous callbacks and reads current
        # state again when reporting, rather than replaying stale snapshots.
        for listener in tuple(self._listeners):
            if listener in self._notifications:
                continue
            result = listener(self.status())
            if result is not None:
                task = asyncio.create_task(result)
                self._notifications[listener] = task
                task.add_done_callback(lambda done, key=listener: self._notification_done(key, done))

    def _notification_done(self, listener, task):
        self._notifications.pop(listener, None)
        if not task.cancelled() and task.exception() is not None:
            self.notification_failed = True

    async def shutdown(self):
        if self._shutdown_task is None:
            self._shutdown_task = asyncio.create_task(self._shutdown_resources())
        await asyncio.shield(self._shutdown_task)

    async def _shutdown_resources(self):
        try:
            await self.stop()
        finally:
            self._closed = True
            if self._unsubscribe:
                self._unsubscribe()
                self._unsubscribe = None
            pending = list(self._notifications.values())
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if self.manage_connection:
                if self._reader:
                    self._reader.cancel()
                    await asyncio.gather(self._reader, return_exceptions=True)
                await self._call(self.client.disconnect())
