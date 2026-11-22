# CastSpin

**Experimental Google Cast gateway for Music Assistant playback devices**, with **Home Assistant App first** development.

Goal: automatically show all public audio playback targets from Music Assistant
as individually selectable Cast devices in **YouTube Music on a phone**. For
example, selecting `Sauna [CastSpin]` should play through MA's sauna player;
selecting `Garten [CastSpin]` should use its garden player. Music Assistant keeps
ownership of Sendspin and other configured audio transports. An MA-managed ESP32
A2DP source may forward audio to a Bluetooth speaker.

> **Current App status: foundation only.** No operational receiver or playback
> yet. A software mirroring/control prototype is tested separately; it is not
> enabled in the App. Real YouTube Music discovery, Cast authentication and
> audible playback remain unverified.

## Home Assistant App (preview)

Add `https://github.com/pfriedrich84/castspin` as a custom repository under Home Assistant Settings → Apps → Install app → Repositories. Install and start CastSpin, then open its Ingress UI.

The UI reports current implementation status. See [app documentation](castspin/DOCS.md).

## Architecture and roadmap

Reuse [Cast Audio Receiver Lab](https://github.com/Allcrafter1/cast-audio-receiver-lab)
for the existing Cast receiver/session/player implementation, not another Cast
receiver. The immediate output route uses the official Music Assistant client;
CastSpin does not take over MA-owned Sendspin clients. See
[ADR 0003](docs/adr/0003-music-assistant-player-mirroring.md) for this user-refined
product direction, [ADR 0002](docs/adr/0002-reuse-cast-audio-receiver-lab.md) for
receiver reuse, and the [pinned component analysis](docs/receiver-reuse-analysis.md).
The independent Sendspin-server experiment remains separate groundwork.

0. **P0:** Reuse decision, output seams and licensing review.
1. **P1:** Actual phone YouTube Music → reused receiver → Music Assistant → one
   existing player → audible playback. A one-device test is a first proof, not
   the final scope. Minimal HA runtime/configuration belongs to this slice.
2. **P2:** Automatically mirror all eligible MA audio targets, with independent
   playback/controls and stable identities; accept the real multi-room behavior.
3. **P3:** Home Assistant setup, discovery feedback and lifecycle refinements,
   reusing existing upstream structures where feasible. HA is the primary product.
4. **P4:** Reconnect, stability, hardware/upgrade tests, release and documentation.
5. **P5:** Optional standalone Docker Compose deployment.

Bounds, HTTPS verification and cleanup are part of the first audio slice, not
postponed hardening. Source reuse does not authorize the reference project's
separate authentication bundle; no such material is adopted. A Google Cast
controller library is **not** a Cast receiver. Spotify Cast, DRM and native
Google Home speaker groups are not claimed as supported.

## Development and validation

Run `python3 -m unittest discover -s tests -v` and `sh -n castspin/run.sh`.
CI runs the HTTP contract tests on Python 3.13–3.15 and builds and starts the
actual App image on native amd64 and aarch64 runners. These are **not** a
Home Assistant Supervisor installation or a Cast/Sendspin audio acceptance test.
For the separate real-library/loopback mirroring tests, use the hashed dependency
installation procedure in [validation](docs/validation.md#music-assistant-mirroring-software-prototype).
Their MA server is a simulator, not a live MA installation or an audio endpoint.
See [validation](docs/validation.md) for the remaining gates.

## License

Original CastSpin code: [Apache License 2.0](LICENSE). Third-party components retain their own licenses. In particular, code adapted from MPL-2.0 projects requires compliance with MPL-2.0 for the relevant files. See the [third-party review and release obligations](docs/third-party.md). The mirroring prototype imports unmodified, pinned upstream Python components in its test environment; no native receiver or new audio transport is shipped in the App yet.
