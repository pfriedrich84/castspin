# CastSpin

**Experimental Google Cast → Sendspin audio gateway**, with **Home Assistant App first** development.

Goal: expose independent Sendspin audio players (Sauna, Garden, etc.) as individually selectable virtual Google Cast targets. An ESP32 A2DP source can optionally forward Sendspin audio to a Bluetooth sauna speaker.

> **Current status: foundation only.** No working virtual Google Cast receiver, Sendspin transport, or playback yet. Cast authentication and app compatibility are feasibility risks.

## Home Assistant App (preview)

Add `https://github.com/pfriedrich84/castspin` as a custom repository under Home Assistant Settings → Apps → Install app → Repositories. Install and start CastSpin, then open its Ingress UI.

The UI reports current implementation status. See [app documentation](castspin/DOCS.md).

## Architecture and roadmap

Reuse [Cast Audio Receiver Lab](https://github.com/Allcrafter1/cast-audio-receiver-lab)
for the existing Cast receiver/session/player implementation. CastSpin's primary
contribution is a Sendspin output backend using the real Sendspin server library,
not another Cast receiver. See [ADR 0002](docs/adr/0002-reuse-cast-audio-receiver-lab.md)
and the [pinned component analysis](docs/receiver-reuse-analysis.md).

0. **P0:** Reuse decision, output seams and licensing review.
1. **P1:** One actual Cast sender → reused receiver → Sendspin client → audible
   playback. The HA foundation is already present, but this audio milestone is not.
2. **P2:** Independent receiver/client routing and controls for multiple rooms.
3. **P3:** Home Assistant App discovery and persistent device mapping, reusing
   existing upstream structures where feasible. HA is the primary product.
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
See [validation](docs/validation.md) for the remaining gates.

## License

Original CastSpin code: [Apache License 2.0](LICENSE). Third-party components retain their own licenses. In particular, code adapted from MPL-2.0 projects requires compliance with MPL-2.0 for the relevant files. See the [third-party review and release obligations](docs/third-party.md); no third-party receiver or Sendspin implementation has been incorporated yet.
