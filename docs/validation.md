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

## Sendspin / final acceptance (not implemented)

Only after a useful Cast receive path is demonstrated, integrate an actual
Sendspin **server**, negotiate formats, bound buffering and handle timestamps,
backpressure and reconnect. Define explicit client ownership with Music
Assistant; do not silently steal clients.

The final gate is a phone discovering virtual `Sauna`, with real audio reaching
`sauna-esp32` and its Bluetooth A2DP speaker, plus an independent track on
`garten-player`. Power-cycle each output and check recovery and routing
isolation. Persist IDs/mappings across App restart and upgrade. None of these
outcomes follows from green unit tests or an App shell.
