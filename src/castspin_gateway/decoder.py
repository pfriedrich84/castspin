# SPDX-License-Identifier: Apache-2.0
"""Bounded direct HTTP(S) media decoding, not a Cast protocol implementation.

HTTP is owned by aiohttp for certificate AND hostname verification. FFmpeg sees
only a pipe and cannot follow network/file references embedded in a playlist.
Consequently remote HLS/DASH manifests are deliberately unsupported in this slice.
"""

import asyncio
import math
import ssl
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlsplit

import aiohttp

SAMPLE_RATE = 48000
CHANNELS = 2
FRAME_BYTES = CHANNELS * 2
CHUNK_FRAMES = 960  # 20 ms, signed 16-bit little-endian stereo
CHUNK_BYTES = CHUNK_FRAMES * FRAME_BYTES


class DecodeError(RuntimeError):
    """Sanitized decoder error: never contains a signed media URL or raw stderr."""


class HttpPcmDecoder:
    """One owned FFmpeg process per route, with pull-based PCM backpressure."""

    def __init__(self, *, ffmpeg="ffmpeg", tls_context=None, timeout=10.0):
        if not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError("decoder timeout must be in (0, 30] seconds")
        self.ffmpeg = str(ffmpeg)
        self.tls_context = tls_context or ssl.create_default_context()
        if not self.tls_context.check_hostname or self.tls_context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError("HTTPS certificate and hostname verification are required")
        self.timeout = timeout
        self.process_id = None
        self._busy = False

    @asynccontextmanager
    async def open(self, url, *, start_time=0.0):
        """Yield frame-aligned PCM chunks; exiting ALWAYS closes fetch and decoder.

        Only direct HTTP(S) audio/container streams are accepted. Seeking decodes
        and discards preceding audio: it is correct for finite fixtures, not an
        efficient live/DASH seeking implementation. The caller owns stream timing.
        """
        try:
            parsed = urlsplit(url)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None):
                raise ValueError
            # Validate invalid port syntax without including the input in errors.
            parsed.port
            if isinstance(start_time, bool) or not math.isfinite(start_time) or start_time < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise DecodeError("invalid media source or start position") from None
        if self._busy:
            raise DecodeError("decoder is already active")
        self._busy = True
        process = None
        feeder = None
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=self.timeout,
                                           sock_read=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout, trust_env=False,
                                             read_bufsize=65536) as session:
                async with session.get(url, ssl=self.tls_context, max_redirects=5) as response:
                    if response.status != 200:
                        raise DecodeError("media HTTP request failed")
                    command = [
                        self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                        "-protocol_whitelist", "pipe", "-probesize", "524288",
                        "-analyzeduration", "1000000", "-threads", "1", "-i", "pipe:0",
                        "-ss", str(float(start_time)), "-map", "0:a:0", "-vn", "-sn", "-dn",
                        "-threads", "1", "-acodec", "pcm_s16le", "-ar", str(SAMPLE_RATE),
                        "-ac", str(CHANNELS), "-f", "s16le", "pipe:1",
                    ]
                    process = await asyncio.create_subprocess_exec(
                        *command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL, limit=65536,
                    )
                    self.process_id = process.pid
                    feeder = asyncio.create_task(self._feed(response, process))
                    yield self._chunks(process, feeder)
        except (aiohttp.ClientError, OSError, TimeoutError):
            raise DecodeError("media fetch or decoder failed") from None
        finally:
            try:
                if feeder is not None:
                    feeder.cancel()
                    with suppress(asyncio.CancelledError, DecodeError, OSError):
                        await feeder
                if process is not None:
                    if process.stdin is not None:
                        process.stdin.close()
                    if process.returncode is None:
                        with suppress(ProcessLookupError):
                            process.terminate()
                    try:
                        async with asyncio.timeout(3):
                            await process.wait()
                    except TimeoutError:
                        with suppress(ProcessLookupError):
                            process.kill()
                        await process.wait()
            finally:
                self.process_id = None
                self._busy = False

    async def _feed(self, response, process):
        try:
            async for data in response.content.iter_chunked(65536):
                process.stdin.write(data)
                await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            # The decoder's exit code, not an optimistic feed result, decides success.
            pass
        except (aiohttp.ClientError, TimeoutError, OSError):
            raise DecodeError("media body transfer failed") from None
        finally:
            process.stdin.close()

    async def _chunks(self, process, feeder):
        while True:
            try:
                async with asyncio.timeout(self.timeout):
                    data = await process.stdout.readexactly(CHUNK_BYTES)
            except asyncio.IncompleteReadError as end:
                data = end.partial
                if len(data) % FRAME_BYTES:
                    raise DecodeError("decoder produced an incomplete PCM frame") from None
                if data:
                    yield data
                break
            except TimeoutError:
                raise DecodeError("decoder output timed out") from None
            yield data
        async with asyncio.timeout(self.timeout):
            await feeder
            code = await process.wait()
        if code != 0:
            raise DecodeError("media could not be decoded")
