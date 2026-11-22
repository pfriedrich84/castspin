# ADR 0002 — Reuse the existing receiver; build the Sendspin output

- Date: 2026-11-22
- Status: Accepted direction; component composition requires an executable spike
- Tracks: [Issue #1](https://github.com/pfriedrich84/castspin/issues/1)
- Supersedes: receiver-selection and sequencing decisions 2 and 5 in
  [ADR 0001](0001-cast-feasibility-before-gateway.md), not its authentication,
  licensing or evidence safeguards

## Context

The owner directs CastSpin to reuse Cast Audio Receiver Lab while it can meet
requirements. CastSpin's contribution is Sendspin output, not another Cast
implementation. The Home Assistant App is the primary product; standalone Docker
is secondary. PRs #2 and #3 already provide the App foundation and research. They
do not provide Cast-to-Sendspin playback.

The [pinned source analysis](../receiver-reuse-analysis.md) confirms a versioned
player bridge, Python output contract, persistent route identities, session and
control handling, and HA packaging. The source is reusable independently of the
separately distributed authentication artifacts. Source licenses do not grant
rights to those artifacts. Neither availability nor upstream compatibility
reports establish CastSpin's stock-sender compatibility or redistribution rights.

## Options

| Option | Maintenance and constraints | Decision |
| --- | --- | --- |
| Consume pinned receiver components, compose the existing Python player with an original Sendspin backend | Reuses Cast/session/status code without a product fork. Public-looking Python classes are not a stability promise; pin and contract-test them. Existing managed-output registry has no external plugin hook. | First implementation spike. |
| Targeted fork adding a Sendspin output and only necessary lifecycle/registration seams | Integrates naturally with upstream manager/UI but adds MPL file maintenance and multi-process/server coordination. Upstream's per-route processes do not automatically share a Sendspin server. | Fallback only for a demonstrated composition blocker; keep minimal diff and submit reusable seams upstream. |
| Contribute the adapter upstream | Potentially lowest long-term duplication and benefits from existing HA management. Acceptance, API stability and maintainer capacity are not established. Contributions to MPL files remain MPL. | Preferred long-term destination, after a working adapter and maintainer agreement; not a prerequisite to the first audio proof. |
| Build a new Cast receiver or continue the openchromecast runtime as the product path | Duplicates the available receiver/session stack and misses the requested reuse priority. | Rejected for now. Keep existing unmerged lab work as research only. Reconsider only with documented unmet requirements. |

## Decision and boundaries

1. Reuse Cast Audio Receiver Lab at a reviewed immutable revision, including its
   maintained Vibecast frontend and required source patch set. Do not substitute
   vanilla Vibecast and assume its external-player behavior is identical.
2. Compose the existing `VibecastAudioPlayer` with a CastSpin `AudioBackend`
   implementation. Do not recreate Cast V2, discovery, application namespaces,
   session management, player protocol v2 or its status/command correlation.
   Do not monkey-patch the static output registry. Prove composition before
   treating it as a supported upstream extension API.
3. Decode the supplied media URL through a bounded decoder pipeline. The bridge
   supplies URLs/MIME/metadata, **not decoded PCM**. Use a real pinned
   `aiosendspin[server]` server API for negotiated audio and timing; do not create
   a Sendspin-like transport or client-to-client relay. Verify HTTPS and do not
   emit signed URLs or media payloads in diagnostics.
4. First prove one receiver → one explicitly admitted client → audible output.
   The intended multi-route design has one Sendspin server with isolated
   per-route client groups/streams, stable receiver/client IDs and no shared
   decoder or playback queue. Do not derive identity from a mutable room name or
   address. Discovery alone must not authorize playback/takeover from Music
   Assistant; unavailable or unassigned clients fail closed.
5. Start with a bounded, non-UI adapter spike. Do not enlarge the foundation UI
   or build another mapping manager before the first audio milestone. Reuse
   upstream route persistence, management and HA components where their actual
   contracts permit it. If necessary, propose the smallest shared-runtime seam
   upstream instead of a second full management implementation.
6. Keep original CastSpin files Apache-2.0; retain MPL for copied/modified MPL
   files, MIT for the Vibecast fork, and all other applicable source/notice
   obligations. Follow the [third-party review](../third-party.md). No source or
   runtime artifacts are incorporated by this documentation-only decision.
7. Do not use the reference image's automatic authentication-bundle bootstrap.
   No private keys, credentials, proprietary captures or unreviewed bundles are
   fetched, committed or redistributed. A rights-cleared authentication path
   for the chosen real sender is a separate unresolved gate. If unavailable,
   report the goal blocked rather than silently lowering sender requirements.

## Delivery order and evidence

- **P0:** This decision, pinned seam/license analysis and coordinated ownership.
- **P1:** Original Sendspin backend, real library/decoder tests, then a real Cast
  sender through the reused receiver to an actual Sendspin client and audible
  playback. Software-only testing may proceed while hardware/auth gates remain
  open; it cannot close those gates.
- **P2:** Two independent receiver/client routes, routing and control isolation.
- **P3:** HA App integration with device discovery and persisted mapping, reusing
  existing upstream structures where feasible. HA remains the product target
  even though a polished configuration UI follows the first stream.
- **P4:** Reconnect, cleanup, power-cycle/restart/upgrade acceptance, tests and
  release/source-license inventories. Bounds and cleanup belong in P1 already.
- **P5:** Standalone Docker packaging.

Always distinguish implemented, automatically tested, started under HA
Supervisor, tested with a real Cast sender, tested with a real Sendspin client,
and end-to-end accepted. No Spotify Cast, DRM or native Google Home group support
is claimed. The [validation gates](../validation.md) remain mandatory.

## Consequences and reconsideration

There is no current live playback claim and no permission to acquire unknown
credential material. An auth blocker is not evidence that the output adapter
seam is unsuitable. Conversely, a working Sendspin test cannot demonstrate Google
Cast authentication. Pin upgrades, client firmware/protocol compatibility,
upstream contribution acceptance and complete shipped-artifact licensing remain
explicit work, not assumptions.

If the component spike fails, record its precise failing API/lifecycle contract
and tests in Issue #1 before choosing the targeted fork. A wholesale receiver
rewrite requires a separate decision with evidence that adaptation cannot meet
the requirement.
