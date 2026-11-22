# Validation gates

A passing process health check is not audio readiness. Keep these gates separate.

## Foundation

- `python3 -m unittest discover -s tests -v`: actual HTTP requests, explicit
  unimplemented status, mappings preview, escaped HTML, bad files and 404s.
- `sh -n castspin/run.sh`.
- `cmp LICENSE castspin/LICENSE`: the App build context needs its own copy so
  the distributed container includes the Apache-2.0 license.
- CI: native amd64/aarch64 container build, start through the inherited S6
  entrypoint, HTTP health response and bundled license. No image publication.
- Manual **not yet performed**: custom repository installation on Home Assistant
  Supervisor, Ingress access, stop/start, host reboot, update and uninstall.

The runtime image recipe uses Home Assistant's released multi-architecture
Debian Trixie base (`2026.11.0`), pinned to its OCI index digest. This replaces
the Alpine foundation so the pinned glibc-based native receiver and Python wheels
can be reused without compatibility shims. Update `castspin/Dockerfile` and
`castspin/build.yaml` together. No local Docker daemon is available: the new
image recipe itself has not been built locally; configured CI is not a result.

## Cast feasibility (blocks compatibility claims)

Record hardware, OS and sender-app versions, receiver revision, timestamps and
sanitized logs. At minimum:

1. A stock Android sender discovers the **virtual** receiver through mDNS on
   the actual LAN. An explicit-IP controller connection is not this proof.
2. Record the TLS and Cast device-auth result separately. Self-signed TLS alone
   does not establish Google-issued Cast device authentication.
3. Record app ID, namespace, media load, URL retrieval (HTTP and HTTPS), decoded
   non-empty audio, and audible playback. Never publish signed media URLs,
   private keys, bearer tokens, or captured copyrighted audio.
4. Check play, pause, stop, volume, disconnect and repeated sessions.
5. Maintain a per-app compatibility matrix. YouTube Music, Spotify, DRM, screen
   mirroring and Google Home groups must not inherit a result from a generic
   media sender.

A generated fixture, synthetic sender, permissive controller, or mocked output
can test code paths, but cannot pass this gate.

## Music Assistant mirroring

[ADR 0003](adr/0003-music-assistant-player-mirroring.md) makes all public MA audio
targets in the phone's YouTube Music picker the current product requirement. A
single test receiver is only the first acceptance step. The independent
Sendspin-server slice below is not required for MA-owned playback.

Use a fresh Python >=3.13 virtual environment. The App recipe installs these same
hashed dependencies; it stays disabled until configured, and never auto-acquires
Cast identity material:

```sh
python3 -m venv .venv-ma
.venv-ma/bin/python -m pip install --require-hashes -r castspin/build-requirements.txt
.venv-ma/bin/python -m pip install --require-hashes --no-build-isolation -r castspin/requirements.txt
.venv-ma/bin/python -m pip check
.venv-ma/bin/python -W error::ResourceWarning -m unittest discover -s tests/ma -v
```

Build requirements are separately hashed and installed first: the upstream
source wheel must not acquire unpinned build dependencies. `requirements.in`
selects the reviewed source archive by revision and SHA-256; `requirements.txt`
locks the transitive runtime artifacts. Regenerate each lock with
`uv pip compile INPUT --python-version 3.13 --generate-hashes --no-header --no-annotate --output-file OUTPUT`.

The tests use the **actual official MA client and actual upstream
VibecastAudioPlayer** over loopback WebSockets, with an explicitly labeled MA API
simulator. They cover inventory additions/removal/renaming, stable bridge IDs,
private/disabled/internal/own-device exclusion, offline target registration,
two independent routes, controls, MA volume/mute preservation, explicit MA group
volume, initial authentication failure, remote errors, deadlines, cancellation,
unconfirmed outcomes and listener/session cleanup. They do not run a native Cast
receiver or real MA server and do not transfer or decode audio.

A timeout/cancellation cannot cancel a remote MA operation. An already-applied
LOAD can be identified and stopped; a still-unconfirmed LOAD reports an error
rather than claiming cleanup or taking ownership of a prior identical URL.
App status exposes `command_outcome_unknown`, `command_pending`,
`requires_attention` and `cleanup_unconfirmed`; it does not replay or silently
recover ambiguous writes. Failed runtimes withdraw native receivers while
keeping diagnostic Ingress available.
The API's check/control race with other controllers is not eliminated.

Cancellation regression: the pinned SDK 1.8.1 can receive a reply while its
cancelled future is still registered, raising `InvalidStateError` and tearing
down the shared reader before other routes can stop. Tests reproduce that defect
in the unmodified SDK and check the narrow subclass guard used by the runtime,
including late success/error/partial replies and subsequent live results. This
guard does not replay a request or claim to cancel a remote operation.

Remaining acceptance: real App installation/native state persistence and mDNS;
reviewed authorized Cast authentication; actual YouTube Music app ID/session and
picker visibility; media URL/header/proxy reachability **from MA**; decoded and
audible output; every eligible target and existing MA group; recursion safeguards
against actual MA discovery; simultaneous routes and restart/upgrade behavior.
There is no live MA, phone, HA Supervisor or audible evidence for this slice.

## Reused native receiver software acceptance

Install `tests/native/requirements.txt` into the same environment. Set
`CASTSPIN_NATIVE_BINARY` to the exact reviewed frontend binary (from the pinned
component image), then run:

```sh
CASTSPIN_NATIVE_BINARY=/path/to/reviewed/vibecast .venv-ma/bin/python -W error::ResourceWarning -m unittest discover -s tests/native -v
```

The test requires local multicast, an assigned IPv4 interface and OpenSSL for
**locally generated** one-day fixture TLS. It runs the actual native receiver,
observes its real mDNS records, uses permissive PyChromecast for Cast V2 over
TLS with the Default Media Receiver, and makes the real SDK instruct an **MA API
simulator** to fetch synthetic WAV over HTTP. Two targets receive exact source
bytes; pause/volume/stop are isolated, native cleanup is observed, and persistent
Cast UUIDs plus no media replay are checked across runtime restart.

Locally observed: native amd64 component at the index in `castspin/sources.json`,
Python 3.13, generated media and real local sockets. This is not phone YTM or
Google-rooted authentication, not real MA decoding/output, not a Sendspin client,
and not sound. The native cache's YTM resolver/header/range path and a remote MA
server are still separate acceptance gates. The native arm64 image and complete
new App image have not been locally tested.

Build-time source retention has been executed locally: all 21 selected source
archives passed their pinned SHA-256 checks, including full vendored native
source and Python covered sources. Static packaging tests check lock/source/base
consistency; neither result proves a successful container build.

## Reused receiver / independent Sendspin adapter (not implemented)

For the separate direct-output experiment in #5 / draft PR #6, follow
[ADR 0002](adr/0002-reuse-cast-audio-receiver-lab.md): compose the existing
Cast Audio Receiver Lab player with an original Sendspin output backend and an
actual `aiosendspin` **server**. Software adapter testing can proceed while the
real sender/authentication gate is open; it does not pass that gate. Prove the
pinned component seam instead of reimplementing the v2 player protocol.

The bridge provides media URLs, not PCM. Test real decode with generated audio,
HTTPS verification, frame alignment, negotiated formats, bounded buffering,
timestamps, backpressure and reconnect. Test replacement loads, stale callbacks,
EOF, slow clients, pause/stop/volume and cancellation; release decoders, streams,
connections and subprocesses within explicit bounds. Check observed output state
rather than returning PLAYING just because a load command was accepted.

Persist server identity, pairing and receiver/client mapping under private App
data. Check stable client IDs across discovery address changes. Use an explicit
admission/ownership policy with Music Assistant; discovery must not silently
steal a client. Test two independent groups without cross-route audio or controls.
Do not enable legacy unencrypted client mode silently to make a test pass.

## Evidence levels and final acceptance

For every result record these separately:

| Level | Required evidence | Current receiver/Sendspin status |
| --- | --- | --- |
| Implemented | Executable adapter/runtime and dependency pins | MA-backed runtime implemented in source; independent Sendspin server not implemented |
| Automatically tested | Real library/decoder tests; mocks labeled as mocks | Native amd64 mDNS/Cast/HTTP-fetch and SDK contracts with simulated MA; no MA output/decoder/Sendspin audio acceptance |
| Started in Home Assistant | Supervisor install/start/Ingress/restart evidence | Not tested; CI image start is not Supervisor |
| Real Google Cast sender | Sender/device/app versions, actual LAN discovery/auth/load/controls | Not tested for selected reused receiver |
| Real Sendspin client | Firmware/protocol, negotiated audio and actual output | Not tested |
| End-to-end accepted | Same session from real sender to audible target, plus controls/cleanup | Not accepted |

Do not download or bootstrap separately distributed Cast authentication material
without a reviewed authorized path. Check [license and artifact gates](third-party.md)
before packaging dependencies or publishing an image.

The current product gate is the real phone's **YouTube Music picker** showing
all eligible Music Assistant audio targets, with `Sauna [CastSpin]` selected and
real audio reaching the MA-managed `sauna-esp32` and its Bluetooth A2DP speaker,
plus an independent track on the MA-managed `garten-player`. A Home Assistant
entity or generic mDNS entry does not pass this gate. Power-cycle each output and check recovery and routing
isolation. Persist IDs/mappings across App restart and upgrade. None of these
outcomes follows from green unit tests or an App shell.
