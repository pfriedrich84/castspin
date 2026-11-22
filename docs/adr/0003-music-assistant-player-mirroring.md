# ADR 0003 — Mirror Music Assistant playback targets for YouTube Music

- Date: 2026-11-22
- Status: Accepted direction; native/MA runtime integrated in source, real phone/audio acceptance open
- Tracks: [Issue #7](https://github.com/pfriedrich84/castspin/issues/7)
- Refines: [ADR 0002](0002-reuse-cast-audio-receiver-lab.md), especially its first
  output route and sequencing, not the receiver-reuse, licensing or auth gates

## User-visible requirement

The owner's goal is **all Music Assistant playback devices appearing as separate
Cast targets in the YouTube Music application on their phone**. An HA
`media_player` entity, one permanently configured test receiver, or visibility
in a generic discovery utility is not this result.

Music Assistant is the inventory and output owner. Initially proving one route
is an acceptance step, not a restriction to one selectable player. The path is:

```text
YouTube Music on phone
  → selected virtual Cast target (e.g. Sauna [CastSpin])
  → reused Cast Audio Receiver Lab / Vibecast session and player
  → official Music Assistant client / selected target's queue
  → MA-managed transport (Sendspin, AirPlay, another configured output)
  → actual player / speaker
```

## Decision

1. Automatically mirror MA's enabled, non-private audio targets (`player`,
   `stereo_pair`, `group`), not just Sendspin devices. Mirror existing MA groups;
   do not construct or claim native Google Home groups. Keep offline targets in
   the inventory, but fail playback closed when unavailable. Internal protocol,
   display, source, light and visualizer objects are not separate audio targets.
2. Use one MA connection and an isolated original backend plus actual upstream
   `VibecastAudioPlayer` per target. Add/remove/rename from MA events. Derive the
   bridge player ID from MA server ID and MA player ID, never an address or room
   name. The native frontend's installation state must also be persisted when
   packaged; a stable bridge ID alone does not prove persistent Cast UUIDs.
3. Append the reserved ` [CastSpin]` marker, disambiguate duplicate MA names, and
   exclude that marker and the `CastSpin` device model/manufacturer from export.
   The eventual native frontend must report that model/manufacturer, so renaming
   a receiver in MA does not cause an infinite Cast → MA → Cast export loop.
4. MA owns fetching/decoding the media URL and delivering audio. CastSpin does
   not steal/re-pair MA-owned Sendspin clients and does not need a second Sendspin
   server for this path. The independent-server experiment in #5 / draft PR #6
   remains separate groundwork, not the immediate product acceptance route.
5. A Cast LOAD explicitly replaces the selected MA target's queue. Test with a
   dedicated target first; do not promise preservation/restoration of the prior
   MA queue. Preserve MA volume and mute at session initialization, including
   zero volume; do not adopt the upstream default of unmuting at 25%.
6. Before playback controls or Stop, check the active queue and exact queue-item
   identity. Never stop unrelated playback merely because the URL is identical.
   Do not automatically ungroup synced children; a child can remain visible but
   cannot become an independent output while MA assigns it to another group.
7. MA's API does not offer transactional queue-item compare-and-swap or remote
   RPC cancellation. A request may apply after a local timeout/cancellation.
   Report unconfirmed outcomes/cleanup, refuse an unconfirmed replacement and
   never replay it automatically. This prototype cannot guarantee cleanup of a
   remotely delayed operation or eliminate the check/control race with another
   controller. Those are explicit operational acceptance risks, not solved by
   green socket tests.
8. Reuse the selected receiver, including its YouTube Music app/session handling.
   Its selected source supports app ID `2DB7CC49`; upstream compatibility reports
   are evidence about upstream, not CastSpin. Do not substitute a synthetic LOAD
   or a generic media receiver for real YouTube Music app acceptance.
9. Keep the Home Assistant App primary. This slice does **not** enable an
   untested receiver in the App, reuse upstream's bootstrap entrypoint, acquire
   an auth bundle, ship a native binary, or add a parallel mapping UI. App
   packaging/configuration and real sender acceptance follow this small
   software-composition slice.

## Evidence and remaining gates

`castspin/app/music_assistant.py` and `ma_mirror.py` compose original Apache-2.0
code with the unmodified, revision/hash-pinned MPL Python player and the pinned
official MA client. `tests/ma` exercises those actual Python libraries over real
loopback WebSockets against an explicitly labeled **MA API simulator**. This
proves inventory registration, control dispatch/isolation, SDK authentication
handling, volume policy, timeout/cancellation outcomes and lifecycle contracts.
It neither runs a real MA server nor transfers/decodes audio.

Still required before saying the owner's goal works:

- Build/inventory the chosen native frontend and ship applicable licenses/source
  without authentication bootstrap or unrelated output tools.
- Provide a reviewed authorized authentication configuration; self-signed TLS is
  not Google-rooted Cast device authentication. No credentials were acquired.
- Configure the App, persistent native state, host networking/mDNS and MA access.
  Do not expose tokens or signed URLs in Ingress, diagnostics or logs.
- Verify URL reachability **from MA** (including receiver-local proxy URLs,
  headers and any DASH/HLS variants). Receiving a URL in Python is not an audio
  bridge; an MA server elsewhere cannot fetch a loopback-only receiver URL.
- Prove one phone's actual YouTube Music picker → auth/session → decoded and
  audible MA-managed output, then all eligible targets, groups, lifecycle and
  two simultaneous independent routes. Record app/server/firmware versions.
- Test inventory recursion safeguards against real MA discovery, not only the
  model/name fixtures. Test duplicate names, unavailable targets, restart/rename
  identity stability and real controller contention.

### Runtime integration follow-up

The own App runtime now starts the pinned native component and MA mirror, with
HA options, read-only App configuration, persisted native state and diagnostic
Ingress. Missing authorized credentials block startup; upstream auth bootstrap
is never invoked. See `castspin/DOCS.md` and `castspin/UPSTREAM.md` for the actual
configuration, license/source retention and immutable component provenance.

The native player's existing progressive-audio cache is enabled; binding its
bridge to the configured HA LAN address makes its URLs reachable from MA. This
also exposes the upstream unauthenticated bridge to the trusted LAN; it must not
be exposed publicly. Existing receiver/mirror self-exclusion now includes nested
groups containing CastSpin targets, rechecked before output commands.

Native amd64 software tests observe real mDNS, permissive Cast V2/TLS LOAD,
SDK commands and exact HTTP audio bytes fetched by an MA simulator, plus controls,
cleanup and stable native UUIDs across restart. Generated TLS is deliberately
not Google-rooted authentication. The complete new App image is not locally built.
No Supervisor installation, stock phone YTM discovery/authentication, real MA
output, physical Sendspin or audible end-to-end acceptance is claimed.
