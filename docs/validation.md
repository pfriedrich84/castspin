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

The image uses Home Assistant's released multi-architecture Alpine 3.24 base
(`2026.11.0`), pinned to its OCI index digest. The old Alpine 3.20 base is EOL.
Review and update both `castspin/Dockerfile` and `castspin/build.yaml` together.

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

## Reused receiver / Sendspin adapter (not implemented)

Follow [ADR 0002](adr/0002-reuse-cast-audio-receiver-lab.md): compose the existing
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
| Implemented | Reviewed executable adapter and dependency pins | Not implemented |
| Automatically tested | Real library/decoder tests; mocks labeled as mocks | No adapter tests yet; foundation tests only |
| Started in Home Assistant | Supervisor install/start/Ingress/restart evidence | Not tested; CI image start is not Supervisor |
| Real Google Cast sender | Sender/device/app versions, actual LAN discovery/auth/load/controls | Not tested for selected reused receiver |
| Real Sendspin client | Firmware/protocol, negotiated audio and actual output | Not tested |
| End-to-end accepted | Same session from real sender to audible target, plus controls/cleanup | Not accepted |

Do not download or bootstrap separately distributed Cast authentication material
without a reviewed authorized path. Check [license and artifact gates](third-party.md)
before packaging dependencies or publishing an image.

The final gate is a phone discovering virtual `Sauna`, with real audio reaching
`sauna-esp32` and its Bluetooth A2DP speaker, plus an independent track on
`garten-player`. Power-cycle each output and check recovery and routing
isolation. Persist IDs/mappings across App restart and upgrade. None of these
outcomes follows from green unit tests or an App shell.
