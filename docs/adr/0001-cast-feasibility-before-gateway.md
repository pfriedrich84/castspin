# ADR 0001 — Gate the gateway on real Cast reception

- Date: 2026-11-22
- Status: Partially superseded by [ADR 0002](0002-reuse-cast-audio-receiver-lab.md)
  for receiver selection and implementation sequencing (decisions 2 and 5).
  Authentication, licensing and evidence safeguards remain in force.
- Tracks: [Issue #1](https://github.com/pfriedrich84/castspin/issues/1)

## Context

The primary deployment is a Home Assistant App. Independent named receivers
must eventually drive actual Sendspin players, including an ESP32 A2DP output.
A controller, a pre-existing Chromecast web receiver, or a status UI does not
satisfy that goal. Receiver discovery does not prove device authentication, and
a protocol status reporting PLAYING does not prove decoded audio.

The [source inventory](../cast-receiver-research.md) identifies native receiver
implementations but no rights-cleared Google device-auth material we can ship.
The current development environment has no phone, Supervisor or audio hardware.

## Decision

1. Merge only the honestly labeled, tested HA foundation first.
2. Build a bounded, opt-in lab using the stable, unmodified MIT
   `openchromecast` receiver and real mpv decoding. Do not start this receiver
   from the primary App or interpret its media status as proof of audio.
3. Use only self-generated receiver credentials. Do not download experimental
   third-party authentication bundles or import material from proprietary apps.
4. Report local/controller, stock-phone and physical-output evidence separately.
   The lab is not a supported CastSpin receiver distribution.
5. Defer the Sendspin runtime, multi-device routing and richer Ingress features
   until an actually useful Cast sender path is verified. When it is, prefer
   the maintained Apache-2.0 aiosendspin **server**, not a client relay.
6. Keep CastSpin's own code Apache-2.0. No third-party source is copied by this
   decision. Any future MPL reuse needs file-level license/notice preservation
   and corresponding source availability; no blanket Apache relicensing.

## Consequences

This deliberately postpones visible gateway features. It gives a reproducible
way to detect true decoding versus null-player success and avoids committing to
an architecture that cannot accept the intended senders. Universal Cast support
is not promised. Stock Google app authentication and physical E2E acceptance
remain blockers rather than work items we can mark complete through mocks.

If self-signed authentication permits a real VLC/DMR audio session on the target
LAN, a limited compatibility product can be considered explicitly. If the user
requires Google-only apps and no authorized identity path becomes available,
record that requirement as blocked instead of silently substituting DIAL,
Spotify Connect or an existing physical Chromecast.
