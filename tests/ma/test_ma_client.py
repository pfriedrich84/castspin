# SPDX-License-Identifier: Apache-2.0
"""Exercise the pinned SDK's late-reply seam; no real MA server involved."""
import asyncio
import unittest

from aiohttp import ClientSession
from music_assistant_client import MusicAssistantClient as OfficialClient

from castspin.app.ma_client import MusicAssistantClient


class LateReplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_pinned_sdk_exhibits_cancelled_future_race(self):
        async with ClientSession() as session:
            client = OfficialClient("http://ma.example", session)
            future = asyncio.get_running_loop().create_future()
            client._result_futures["cancelled"] = future
            future.cancel()
            with self.assertRaises(asyncio.InvalidStateError):
                client._handle_incoming_message({"message_id": "cancelled", "result": None})

    async def test_cancelled_and_completed_replies_are_ignored_without_losing_live_reply(self):
        async with ClientSession() as session:
            client = MusicAssistantClient("http://ma.example", session)
            for cancelled in (True, False):
                for reply in ({"result": None}, {"result": ["chunk"], "partial": True},
                              {"error_code": 999, "details": "private-test-token"}):
                    with self.subTest(cancelled=cancelled, reply=reply):
                        retired = asyncio.get_running_loop().create_future()
                        if cancelled:
                            retired.cancel()
                        else:
                            retired.set_result("already complete")
                        client._result_futures["retired"] = retired
                        client._partial_results["retired"] = ["previous chunk"]
                        client._handle_incoming_message({"message_id": "retired", **reply})
                        self.assertNotIn("retired", client._partial_results)
                        self.assertTrue(retired.done())
                        live = asyncio.get_running_loop().create_future()
                        client._result_futures["live"] = live
                        client._handle_incoming_message({"message_id": "live", "result": "ok"})
                        self.assertEqual(live.result(), "ok")
                        self.assertEqual(retired.cancelled(), cancelled)


if __name__ == "__main__":
    unittest.main()
