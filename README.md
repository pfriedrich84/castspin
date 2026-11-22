# CastSpin

**Experimental Google Cast → Sendspin audio gateway**, with **Home Assistant App first** development.

Goal: expose independent Sendspin audio players (Sauna, Garden, etc.) as individually selectable virtual Google Cast targets. An ESP32 A2DP source can optionally forward Sendspin audio to a Bluetooth sauna speaker.

> **Current status: foundation only.** No working virtual Google Cast receiver, Sendspin transport, or playback yet. Cast authentication and app compatibility are feasibility risks.

## Home Assistant App (preview)

After this branch merges, add `https://github.com/pfriedrich84/castspin` as a custom repository under Home Assistant Settings → Apps → Install app → Repositories. Install and start CastSpin, then open its Ingress UI.

The UI reports current implementation status. See [app documentation](castspin/DOCS.md).

## Roadmap

1. Home Assistant App packaging, Ingress UI and health endpoint.
2. Prove a real virtual Google Cast receiver against sender applications and authentication/discovery.
3. Sendspin output server, audio pipeline, independent playback sessions.
4. Automatic discovery, persistent mapping and status/volume/playback controls.
5. Sauna ESP32-A2DP and Garden end-to-end validation.
6. Optional standalone Docker Compose deployment.

A Google Cast controller library is **not** a Cast receiver.

## License

Original CastSpin code: [Apache License 2.0](LICENSE). Third-party components retain their own licenses. In particular, code adapted from MPL-2.0 projects requires compliance with MPL-2.0 for the relevant files.
