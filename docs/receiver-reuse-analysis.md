# Receiver reuse analysis

Date: 2026-11-22. Scope: P0 of [Issue #1](https://github.com/pfriedrich84/castspin/issues/1).
Decision: [ADR 0002](adr/0002-reuse-cast-audio-receiver-lab.md).
This is source inspection, not an installation or playback result.

## Pinned evidence

- Cast Audio Receiver Lab: [`e56aa32df13168657a70ba42d97fd5821d8533cc`](https://github.com/Allcrafter1/cast-audio-receiver-lab/tree/e56aa32df13168657a70ba42d97fd5821d8533cc), package `0.8.0.dev2`.
- Maintained Vibecast build input: base
  `83ba470158189de3bc223701decdc4c502d47644` **plus** the reference project's
  `patches/vibecast-0.8.0.dev2-current.patch`, as used by its `Containerfile`.
  The base commit alone is not the current receiver. Preserve and verify the
  reference project's source lock, patch hash, notices and transitive inventory
  before building/distributing it.
- Sendspin: stable `aiosendspin` tag
  [`10.3.0` / `fcc01251d4818dd31561490c0b1678603577e2f9`](https://github.com/Sendspin/aiosendspin/tree/fcc01251d4818dd31561490c0b1678603577e2f9).
  Also inspected current main `756eb2d7b84ec07de57491b1534cb5ce714f6ff0`; do not
  combine main's APIs with an older installed release. No dependency is added by
  this analysis. Actual wheel hashes and supported target firmware need tests.

Reference-project file links below all resolve to the pinned revision, not a
moving branch. Source was inspected selectively; no auth artifact was obtained.

## Existing seams and what they actually provide

| Source | Observed contract | CastSpin consequence |
| --- | --- | --- |
| [`backend.py`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/src/cast_audio_lab/backend.py), `AudioBackend` | Metadata, URL/MIME/autoplay/start-time load, play/pause/stop/seek, initial/output volume, observed status, status/control listeners and shutdown. | Implement Sendspin output against this contract. Do not reuse `NullAudioBackend` as evidence of playback; it advances an optimistic clock without audio. |
| [`vibecast_player.py`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/src/cast_audio_lab/vibecast_player.py), `VibecastAudioPlayer` | Accepts a backend instance. Registers player protocol v2, stable player ID/name and capabilities. Receives load/control, reports state/error/controlRequest, correlates Cast session/media-session IDs and volume revisions. | Prefer composition with this existing player. Registration currently advertises fixed audio/video codecs; prove that the decoder satisfies these claims or make a minimal upstream-supported adjustment. Do not advertise DRM support. |
| Same file, `_load_media`, `_serve_connection`, `run` | First stream URL is handed to the backend; 32-command queue, cancellation of superseded loads, disconnect stop, periodic/event reports, reconnect loop. | The boundary is resolved media, not PCM. Backend must release its decoder/push stream on cancellation, replacement, bridge loss and shutdown; avoid stale state after reconnect. |
| [`output_registry.py`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/src/cast_audio_lab/output_registry.py) | Explicitly static registry: mpv, AirPlay, DLNA, Sonos; target validation, factory, per-route arguments and singleton rules. Unknown outputs fail. | There is **no supported external plugin loading**. Importing a new backend does not make it selectable in upstream UI/CLI. First compose the player programmatically; use a targeted registry change only if needed for HA integration. |
| [`routes.py`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/src/cast_audio_lab/routes.py), `Route`, `RouteStore` | UUID route identities independent of names; bounded/versioned routes, atomic replacement, manager lock; targets validated through static registry. | Reuse stable-ID/persistence behavior where possible; extend target semantics for Sendspin client IDs rather than persisting only discovery IPs. Existing network-output target shape is not a Sendspin schema. Preserve Unicode explicitly when integrating persistence. |
| [`route_manager.py`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/src/cast_audio_lab/route_manager.py), `RouteManager.command/replace/health` | One adapter subprocess per enabled route, persists before replacement and fences uncertain cleanup. Health is bridge reachability plus player WebSocket pong. | Independent routes exist, but a singleton Sendspin server cannot be assumed to span these subprocesses. Component spike should host its player/backend objects in one async service. Pong is not audio delivery or audible readiness. |
| [`runtime.py`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/src/cast_audio_lab/runtime.py), `RuntimeSupervisor` | Starts frontend, waits for bridge, starts manager; shuts manager down before frontend, with bounded signal escalation. | Reuse lifecycle ownership rather than another Cast daemon. Composition with an adapter runner is a spike, not an already validated packaging recipe. |
| [`cast-audio-receiver/config.yaml`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/cast-audio-receiver/config.yaml) | Experimental amd64/aarch64 HA App, host networking, Ingress, persistent data and configurable certificate reference. | Reuse appropriate App/network/Ingress patterns, not new standalone-first packaging. Review each permission; do not blindly add audio/share access to a network-only Sendspin adapter. |
| [`Containerfile`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/Containerfile), [`container_bootstrap.py`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/src/cast_audio_lab/container_bootstrap.py) | Builds maintained Rust frontend and Python wheel; also includes unrelated output tools. Default entrypoint calls bootstrap, which can acquire a separate auth bundle when none is supplied. | Do **not** launch this image unchanged as the approved CastSpin runtime. A source/component build must omit automatic auth acquisition and audit exactly what it ships. This is not permission to read/import user credentials. |

Upstream `tests/test_vibecast_player.py` and `tests/test_output_registry.py` were
also inspected for existing command and registration behavior. Their existence
is not a claim that CastSpin ran the upstream suite or passed hardware acceptance.

## Sendspin server seam

At stable 10.3.0:

- [`SendspinServer`](https://github.com/Sendspin/aiosendspin/blob/fcc01251d4818dd31561490c0b1678603577e2f9/aiosendspin/server/server.py)
  owns real connection, discovery and reconnect machinery. `start_server` has
  discovery controls. Its constructor requires an identity and pairing store;
  persistent server identity/pairing lifecycle is work, not optional test glue.
  Legacy unencrypted mode is disabled by default; do not enable it silently for
  older clients. Client firmware/version acceptance must be explicit.
- [`SendspinGroup.start_stream`](https://github.com/Sendspin/aiosendspin/blob/fcc01251d4818dd31561490c0b1678603577e2f9/aiosendspin/server/group.py)
  returns a push stream. Groups are library-managed; do not call the internal
  constructor. `start_stream` may reconnect/reclaim disconnected group members,
  including clients that switched servers. Mapping, admission and exclusive
  ownership must therefore be checked before starting a stream.
- [`PushStream.prepare_audio/commit_audio`](https://github.com/Sendspin/aiosendspin/blob/fcc01251d4818dd31561490c0b1678603577e2f9/aiosendspin/server/push_stream.py)
  supply actual PCM ingestion, transforms, scheduling and buffer behavior. Use
  these library facilities instead of inventing binary messages or clocks.
  Preserve bounded decoder reads and backpressure outside the library too.
- `stop_stream` alone preserves the group's PLAYING state. Correct stop/pause,
  group state, progress and buffer clearing must be tested explicitly, not mapped
  to a method name by assumption. Volume and physical-control reporting require
  the actual player/controller role contracts and event listeners in the selected
  release; those are still implementation work.

## First executable slice (not yet implemented)

1. Pin receiver and server artifacts with notices; load only their reviewed
   components, never the automatic auth-bundle bootstrap.
2. Construct the upstream player with an original Sendspin backend in one async
   runner; use one actual server and one explicitly assigned test client.
3. Decode a generated local media fixture with real FFmpeg to frame-aligned PCM,
   negotiate with the actual library, and verify received audio content, controls
   and cleanup. A library test client is useful automated evidence, not hardware
   playback. HTTPS verification failures must fail closed; local CA trust is
   explicit and fixture-only.
4. Test load replacement, slow/disconnected clients, cancelled decode, STOP,
   EOF, stream errors and bridge reconnect before calling the adapter usable.
5. Then demonstrate a real stock Cast sender through the reused receiver to an
   actual Sendspin endpoint and audible output. Requires sender authentication
   rights/behavior to be resolved and real LAN/hardware access.

## Open gates and ownership

No HA Supervisor, phone, Sendspin endpoint or Bluetooth speaker is available in
this development environment. An independent receiver lab remains unpublished;
its limited permissive-controller/PCM observations do not prove the selected
receiver or stock Google sender acceptance. Issue #1 records that other agent's
checkpoint. This worktree owns the P0 reuse decision, not concurrent receiver or
UI implementation. Coordinate the next small adapter PR through Issue #1.

Unresolved: rights-cleared Cast authentication path; executable component API
compatibility; server/client firmware and pairing compatibility; decoder and
native dependency licensing on both App architectures; upstream maintainer
acceptance. Spotify Cast, DRM and native Google Home speaker groups are not
supported claims.
