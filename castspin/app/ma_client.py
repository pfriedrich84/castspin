# SPDX-License-Identifier: Apache-2.0
"""Small cancellation guard around the pinned official MA client, not a fork."""
from music_assistant_client import MusicAssistantClient as OfficialMusicAssistantClient


class MusicAssistantClient(OfficialMusicAssistantClient):
    def _handle_incoming_message(self, raw):
        # SDK 1.8.1 sets results on cancelled futures if a late RPC reply arrives
        # before send_command's finally removes its entry. InvalidStateError
        # then tears down the shared reader, preventing other targets' cleanup.
        # Match the SDK's missing-listener behavior without replaying the RPC or
        # implying that cancellation aborted its remote effect. This private
        # seam is pinned and regression-tested; remove when upstream fixes it.
        message_id = raw.get("message_id")
        if isinstance(message_id, str):
            future = self._result_futures.get(message_id)
            if future is not None and future.done():
                self._partial_results.pop(message_id, None)
                return
        super()._handle_incoming_message(raw)
