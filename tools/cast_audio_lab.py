#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Opt-in, Linux-only Cast receive/PCM lab. Not a production gateway.

Uses unmodified openchromecast 1.0.5 and a real mpv decoder. No credential
imports, null output, synthetic sender, or automatic downloads in this tool.
"""

import argparse
import hashlib
import json
import math
import os
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
import time
import uuid
import wave
from pathlib import Path

RECEIVER_VERSION = "openchromecast 1.0.5"
MAX_CAPTURE_BYTES = 64 * 1024 * 1024


def pcm_measurements(path):
    """Measure actual finalized PCM, never a player-reported PLAYING state."""
    result = {"decoded_pcm_observed": False}
    try:
        if path.stat().st_size > MAX_CAPTURE_BYTES:
            raise ValueError("capture exceeds size limit")
        with wave.open(str(path), "rb") as stream:
            channels = stream.getnchannels()
            rate = stream.getframerate()
            if stream.getsampwidth() != 2 or channels != 2 or rate != 48000:
                raise ValueError("expected signed 16-bit stereo PCM at 48000 Hz")
            frames = 0
            nonzero = 0
            peak = 0
            squares = 0
            digest = hashlib.sha256()
            while data := stream.readframes(4096):
                if len(data) % (2 * channels):
                    raise ValueError("partial PCM frame")
                frames += len(data) // (2 * channels)
                digest.update(data)
                for (sample,) in struct.iter_unpack("<h", data):
                    peak = max(peak, abs(sample))
                    nonzero += sample != 0
                    squares += sample * sample
            if frames != stream.getnframes():
                raise ValueError("truncated or unfinalized WAV")
        result.update({
            "decoded_pcm_observed": frames > 0 and peak > 0,
            "frames": frames,
            "sample_rate": rate,
            "channels": channels,
            "duration_seconds": frames / rate,
            "nonzero_samples": nonzero,
            "peak_s16": peak,
            "rms_s16": math.sqrt(squares / (frames * channels)) if frames else 0,
            "pcm_sha256": digest.hexdigest(),
        })
    except (OSError, EOFError, wave.Error, ValueError):
        # Do not include filenames, media URLs or decoder logs in public summaries.
        result["measurement_error"] = "missing, invalid or incomplete PCM capture"
    return result


def executable(value):
    resolved = shutil.which(str(value))
    if resolved is None:
        raise ValueError("required executable not found")
    return Path(resolved).resolve()


def version(path):
    completed = subprocess.run(
        [str(path), "--version"], capture_output=True, text=True, timeout=10, check=True,
    )
    return completed.stdout.splitlines()[0]


def stop_player(ipc):
    """Ask mpv to finalize its WAV before the receiver kills its child."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(2)
            connection.connect(str(ipc))
            connection.sendall(b'{"command":["quit"]}\n')
            while connection.recv(4096):
                pass
    except OSError:
        pass


def stop_receiver(process):
    # The launcher owns this newly created process group, not other receivers.
    try:
        os.killpg(process.pid, signal.SIGINT)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    except ProcessLookupError:
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def run_capture(*, receiver, mpv, output, duration, port, name, device_id, media_ca=None):
    """Run the real external receiver. Caller must obtain explicit network opt-in."""
    if not 1 <= duration <= 300 or not 1024 <= port <= 65535:
        raise ValueError("duration must be 1–300 seconds and port 1024–65535")
    receiver = executable(receiver)
    mpv = executable(mpv)
    receiver_version = version(receiver)
    if receiver_version != RECEIVER_VERSION:
        raise ValueError("unsupported receiver version; reviewed version is 1.0.5")
    mpv_version = version(mpv)
    if not mpv_version.startswith("mpv "):
        raise ValueError("not an mpv executable")
    if media_ca is not None:
        media_ca = Path(media_ca).resolve(strict=True)
    device_id = uuid.UUID(str(device_id)).hex
    output = Path(output).resolve()
    # Never overwrite prior evidence. New directory and all files are private.
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    result = {
        "evidence_kind": "decoded_pcm_only",
        "receiver_version": receiver_version,
        "mpv_version": mpv_version,
        "device_id": device_id,
        "sender": "not_attested",
        "phone_discovery": "not_tested",
        "google_device_auth": "not_proven",
        "audible_playback": "not_tested",
        "sendspin": "not_implemented",
        "backend_failure_detected": False,
        "receiver_exited_early": False,
        "interrupted": False,
    }
    with tempfile.TemporaryDirectory(prefix="castspin-lab-") as temp:
        runtime = Path(temp)
        ipc = runtime / "mpv.sock"
        wrapper = runtime / "mpv-capture"
        mpv_args = [
            str(mpv), "--no-config", "--load-scripts=no", "--vid=no",
            "--tls-verify=yes", "--ao=pcm", f"--ao-pcm-file={output / 'capture.wav'}",
            "--ao-pcm-waveheader=yes", "--ao-pcm-append=no", "--audio-format=s16",
            "--audio-samplerate=48000", "--audio-channels=stereo",
        ]
        if media_ca is not None:
            mpv_args.append(f"--tls-ca-file={media_ca}")
        # POSIX shell wrapper only adds real decoder options; it does not fake IPC.
        # dash/bash ulimit -f uses 1024-byte blocks: 65536 blocks caps a file at 64 MiB.
        wrapper.write_text(
            "#!/bin/sh\nset -eu\numask 077\nulimit -f 65536\nexec "
            + shlex.join(mpv_args) + ' "$@"\n', encoding="utf-8",
        )
        wrapper.chmod(0o700)
        command = [
            str(receiver), "--no-tray", "--player", "mpv", "--mpv", str(wrapper),
            "--ipc", str(ipc), "--friendly-name", name, "--model", "CastSpin Audio Lab",
            "--capabilities", "4", "--device-id", device_id, "--port", str(port),
        ]
        stdio = output / "private-stdio.log"
        with stdio.open("x", encoding="utf-8") as log:
            stdio.chmod(0o600)
            process = subprocess.Popen(
                command, stdout=log, stderr=log, start_new_session=True,
                env={**os.environ, "TMPDIR": temp},
            )
            try:
                deadline = time.monotonic() + duration
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        result["receiver_exited_early"] = True
                        break
                    time.sleep(0.1)
            except KeyboardInterrupt:
                result["interrupted"] = True
            finally:
                stop_player(ipc)
                stop_receiver(process)
        for filename in ("openchromecast.log", "openchromecast-mpv.log"):
            source = runtime / filename
            if source.exists():
                target = output / ("private-" + filename)
                shutil.copyfile(source, target)
                target.chmod(0o600)
        # Upstream can silently fall back to null playback. Never accept that.
        for logfile in output.glob("private-*.log"):
            text = logfile.read_text(encoding="utf-8", errors="replace").lower()
            if any(marker in text for marker in (
                "falling back to null player", "using null player", "mpv command failed",
                "reason=error", "audio output truncated",
            )):
                result["backend_failure_detected"] = True
    result.update(pcm_measurements(output / "capture.wav"))
    result["decoded_pcm_observed"] &= not (
        result["backend_failure_detected"] or result["receiver_exited_early"]
    )
    summary = output / "summary.json"
    summary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    summary.chmod(0o600)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-network-receiver", action="store_true",
                        help="explicitly allow LAN-wide Cast listener and mDNS advertisement")
    parser.add_argument("--receiver", default="openchromecast")
    parser.add_argument("--mpv", default="mpv")
    parser.add_argument("--output", required=True, type=Path, help="new private evidence directory")
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--port", type=int, default=8009)
    parser.add_argument("--name", default="CastSpin Audio Lab")
    parser.add_argument("--device-id", default=str(uuid.uuid4()))
    parser.add_argument("--media-ca", type=Path, help="optional trusted CA for HTTPS media")
    args = parser.parse_args()
    if not args.enable_network_receiver:
        parser.error("LAN listening/mDNS requires --enable-network-receiver; trusted LAN only")
    try:
        result = run_capture(
            receiver=args.receiver, mpv=args.mpv, output=args.output, duration=args.duration,
            port=args.port, name=args.name, device_id=args.device_id, media_ca=args.media_ca,
        )
    except (ValueError, OSError, subprocess.SubprocessError):
        parser.exit(2, "Lab failed preflight or process startup; check binaries and a NEW output directory.\n")
    print(json.dumps(result, indent=2))
    return 0 if result["decoded_pcm_observed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
