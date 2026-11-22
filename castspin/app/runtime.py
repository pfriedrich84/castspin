# SPDX-License-Identifier: Apache-2.0
"""Own HA lifecycle; reuse receiver/player, never invoke upstream auth bootstrap."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path
import signal
import tempfile
import threading

from aiohttp import ClientSession, ClientTimeout

from . import server
from .ma_client import MusicAssistantClient
from .ma_mirror import MusicAssistantMirror
from .settings import ConfigurationError, Settings


class Runtime:
    def __init__(self, settings, *, data=Path("/data"), certificate=Path("/config/certs.json"),
                 binary="/usr/local/bin/vibecast", publish=None):
        self.settings = settings
        self.data = data
        self.certificate = certificate
        self.binary = binary
        self.publish = publish or (lambda value: None)
        self.process = None
        self.mirror = None
        self.snapshot = {}

    def report(self, state, **extra):
        self.snapshot = {"status": "ok", "cast_receiver": state,
                         "sendspin": "managed_by_music_assistant", "audio_verified": False,
                         "message": "", **extra}
        self.publish(self.snapshot)

    def _configuration(self):
        state = self.data / "receiver"
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        state.chmod(0o700)
        # This also controls native media-proxy URL generation: MA must reach
        # the address. Never pass a loopback-only cache URL to a remote server.
        content = ('[device]\nmodel = "CastSpin"\nmanufacturer = "CastSpin"\n'
                   '[network]\n'
                   f'bind_host = "{self.settings.network_address}"\n'
                   f'player_bind_host = "{self.settings.network_address}"\n'
                   f'player_port = {self.settings.player_port}\n')
        with tempfile.NamedTemporaryFile(mode="w", dir=state, delete=False) as out:
            out.write(content)
            temporary = Path(out.name)
        temporary.replace(state / "config.toml")
        return state

    async def run(self, stop: asyncio.Event):
        task = stopped = exited = session = None
        try:
            self.settings.validate()
            if not self.settings.enabled:
                self.report("disabled", message="Configure Music Assistant and enable the App receiver.")
                await stop.wait()
                return
            if not self.certificate.is_file():
                self.report("waiting_for_certificate", message=(
                    "Provide your authorized Cast certificate manifest as /config/certs.json. "
                    "No authentication bundle is acquired automatically."))
                await stop.wait()
                return
            if not 0 < self.certificate.stat().st_size <= 16 * 1024 * 1024:
                raise ConfigurationError("Cast certificate manifest is empty or too large")
            state = self._configuration()
            self.report("starting", message="Starting the reused Cast frontend and MA connection.")
            self.process = await asyncio.create_subprocess_exec(
                self.binary, "--data-dir", str(state), "--certs", str(self.certificate),
                "--log-level", "error", stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True)
            # Debug/INFO from upstream may contain tokens/metadata/signed URLs.
            logging.getLogger("music_assistant_client").setLevel(logging.CRITICAL)
            logging.getLogger("cast_audio_lab").setLevel(logging.CRITICAL)
            session = ClientSession(timeout=ClientTimeout(total=15), trust_env=False)
            client = MusicAssistantClient(self.settings.music_assistant_url.rstrip("/"), session,
                                          token=self.settings.music_assistant_token)
            address = self.settings.network_address
            self.mirror = MusicAssistantMirror(
                client, bridge_url=f"ws://{address}:{self.settings.player_port}/player")
            initialized = asyncio.Event()
            task = asyncio.create_task(self.mirror.run(initialized))
            exited = asyncio.create_task(self.process.wait())
            stopped = asyncio.create_task(stop.wait())
            while not stop.is_set():
                if exited.done():
                    raise RuntimeError("Native receiver exited")
                if task.done():
                    task.result()
                    raise RuntimeError("Music Assistant mirror stopped")
                inventory = self.mirror.status()
                connected = sum(route.player._websocket is not None
                                for route in self.mirror.routes.values())
                uncertain = (inventory["cleanup_unconfirmed"] or inventory["requires_attention"]
                             or any(r["command_outcome_unknown"] and not r["command_pending"]
                                    for r in inventory["routes"]))
                self.report("attention_required" if uncertain else (
                    "player_bridge_connected" if initialized.is_set() and connected else "starting"),
                    music_assistant="connected" if initialized.is_set() else "connecting",
                    connected_bridges=connected, **inventory,
                    message=("Local control bridge only; phone discovery/authentication and audible playback are unverified."
                             if not uncertain else "An MA command outcome or cleanup is unconfirmed. Inspect MA before restarting; do not replay it."))
                await asyncio.wait((task, exited, stopped), timeout=1,
                                   return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            raise
        except ConfigurationError as error:
            self.report("configuration_error", message=str(error))
        except Exception:
            self.report("error", message=(
                "Receiver or Music Assistant connection failed. Check LAN address/ports, authorized certificate validity "
                "and MA URL/token/version. Inspect MA for unresolved playback before explicitly restarting; no automatic replay."))
        finally:
            # Cancel/clean the mirror while its MA session is still usable.
            # Withdraw the native receivers even on errors, not only App stop.
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if session:
                await session.close()
            if self.process and self.process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    self.process.send_signal(signal.SIGINT)
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=12)
                except TimeoutError:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(self.process.pid, signal.SIGKILL)
                    await self.process.wait()
            for pending in (stopped, exited):
                if pending:
                    pending.cancel()
            await asyncio.gather(*(p for p in (stopped, exited) if p), return_exceptions=True)
            uncertain = bool(self.mirror and (self.mirror.cleanup_unconfirmed or self.mirror.requires_attention))
            if self.snapshot.get("cast_receiver") in {"error", "configuration_error"}:
                self.report(self.snapshot["cast_receiver"], message=self.snapshot["message"],
                            cleanup_unconfirmed=uncertain)
            else:
                self.report("stopped", cleanup_unconfirmed=uncertain,
                            message="Cleanup is unconfirmed; inspect Music Assistant." if uncertain else "Stopped.")


def background_error(_loop, context):
    # Upstream initialization creates background tasks. The default asyncio
    # handler can print raw server error bodies even when SDK logging is muted.
    logging.getLogger("castspin").error("Background task failed (%s); inspect runtime status",
                                       type(context.get("exception")).__name__)


async def serve():
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(background_error)
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    httpd = server.ThreadingHTTPServer(("0.0.0.0", server.PORT), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    def publish(value):
        server.RUNTIME_STATUS = value
    publish({"status": "ok", "cast_receiver": "starting", "audio_verified": False})
    thread.start()
    try:
        try:
            settings = Settings.load(Path(os.environ.get("CASTSPIN_OPTIONS", "/data/options.json")))
        except (ValueError, OSError):
            publish({"status": "ok", "cast_receiver": "configuration_error", "audio_verified": False,
                     "message": "Invalid App options. Correct the App configuration and restart."})
        else:
            await Runtime(settings, data=Path(os.environ.get("CASTSPIN_DATA", "/data")), publish=publish).run(stop)
        await stop.wait()  # Keep diagnostic Ingress alive after a runtime error.
    finally:
        await asyncio.to_thread(httpd.shutdown)
        httpd.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    asyncio.run(serve())
