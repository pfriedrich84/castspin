# Cast receiver feasibility — 2026-11-22

## What must be proved

Issue [#1](https://github.com/pfriedrich84/castspin/issues/1) requires a **native
network receiver**, not merely code controlling a Chromecast or a web application
running on an already authenticated Chromecast. Discovery, TLS, device auth,
application launch and actual decoded audio are separate milestones.

Sources below were read at the indicated revisions. Upstream README claims are
not CastSpin acceptance results. Recent commits indicate activity, not protocol
certification or production maturity.

## Inventory

| Implementation / inspected source | Actual role and license | Useful path / constraints | Decision |
| --- | --- | --- | --- |
| [openchromecast `c0c640c`](https://github.com/yukarikaname/openchromecast/tree/c0c640c6b97f2712991a3dbeba645654faafe612), stable [v1.0.5 `96bea1c`](https://github.com/yukarikaname/openchromecast/tree/96bea1cd6bededac802c6ce33ec99266b827070a) | Native CastV2 receiver, MIT | `src/mdns.rs`: DNS-SD; `src/server.rs`: TLS/protobuf/auth; `src/receiver.rs` + `media.rs`: DMR; `src/player/mpv.rs`: real decoder/output. Self-generated RSA/TLS identity supported. Upstream reports VLC Android audio but not stock Google auth. | Use stable v1.0.5 as an **external, unmodified lab receiver**, not a production gateway dependency yet. |
| [vibecast `4cde20b`](https://github.com/emilsvennesson/vibecast/tree/4cde20b3f49b296debec8cb9a2badb51c7bae940), stable v0.2.0 | Native receiver and per-player WebSocket bridge, MIT (retain embedded schema notices) | `crates/vibecast-discovery`, `vibecast-security`, `vibecast-bridge`. Attractive future multi-receiver boundary. Requires externally supplied device-auth manifest; no credentials included. | Strong architecture candidate **only after** a rights-cleared authentication path and actual audio proof. |
| [go-cast `6acdd29`](https://github.com/tristanpenman/go-cast/tree/6acdd297db1c4b4b3aae13b8d6591488de65130a) | Includes both sender and native receiver, MIT | README explicitly says receiver audio is unsupported; mainly VP8 streaming. Auth manifest requires real-device signing material. | Not an audio-PoC backend. Do not confuse its remote application with its receiver. |
| [cast-audio-receiver-lab `e56aa32`](https://github.com/Allcrafter1/cast-audio-receiver-lab/tree/e56aa32df13168657a70ba42d97fd5821d8533cc) | Native multi-output gateway: MPL-2.0 Python/product layer, MIT maintained Vibecast fork, other separately licensed tools | Existing HA packaging and real-output work. `LICENSING.md` distinguishes source from authentication bundles. `docs/how-it-works.md` describes time-windowed auth material collected from a purchased proprietary reference implementation. | Study source boundaries and architecture, **do not copy source or fetch its credential bundle**. Public distribution is not proof of permission to reuse credentials. MPL files could only be reused with MPL/source/notice obligations intact. |
| [ytcast-open `a8cf532`](https://github.com/mthwJsmith/ytcast-open/tree/a8cf53282f101c47525c8c90ca1bbf2b7459eace) | DIAL/SSDP + YouTube Lounge/SABR → MPD, not a general CastV2 receiver | README/Cargo metadata claim MIT, but no root LICENSE in inspected tree; embedded solver/dependency terms would need audit. No generic media receiver or Google-issued identity demonstrated by this transport. | Not a substitute for the required virtual Cast audio device. No code adopted. |
| [Open Screen](https://chromium.googlesource.com/openscreen/) | Native reference Cast **Streaming** receiver; BSD-family source notices | Standalone receiver handles mirroring/remoting/RTP; not a ready-to-use implementation of generic DMR media-URL flinging or YouTube Music. Certificate validator uses a trust store/path verification. | Protocol/security reference; different audio ingress model. No source copied. |
| [PyChromecast](https://github.com/home-assistant-libs/pychromecast), stable 14.1.1 | **Controller**, MIT; generated Chromium schema has its own BSD notice | Sends Cast commands; `socket_client.py` disables TLS certificate checking and does not demonstrate stock sender device-auth validation. | Lab sender only. A successful PyChromecast connection does **not** pass Android authentication. |
| [cast-sender](https://github.com/haecker-felix/cast-sender) / [node-castv2](https://github.com/thibauts/node-castv2) | Controller / low-level transport. node-castv2 has Client and Server, MIT | A TLS server is not a complete receiver. node-castv2 itself documents device authentication as the obstacle. | Not a turnkey receiver. |
| [Sendspin/cast](https://github.com/Sendspin/cast) | Apache-2.0 **web receiver app running on an existing Chromecast** | README requires an existing Cast/Google TV device; receives Sendspin and outputs on that device. | Opposite direction. Cannot expose a Sendspin player as a new network Cast receiver. |

## Authentication is the product feasibility blocker

A TLS server can use a self-signed, short-lived peer certificate. Cast's separate
`urn:x-cast:com.google.cast.tp.deviceauth` exchange authenticates device identity
through a Google-rooted chain and a signature binding the peer certificate
(and, for challenge-bound responses, the sender nonce). Making a self-signed
identity and signing it correctly does **not** grant a Google-rooted identity.

Evidence: openchromecast's [`src/crypto.rs`](https://github.com/yukarikaname/openchromecast/blob/96bea1cd6bededac802c6ce33ec99266b827070a/src/crypto.rs),
vibecast's [`vibecast-security`](https://github.com/emilsvennesson/vibecast/tree/4cde20b3f49b296debec8cb9a2badb51c7bae940/crates/vibecast-security),
and Open Screen's [`cast_cert_validator.cc`](https://chromium.googlesource.com/openscreen/+/refs/heads/main/cast/common/certificate/cast_cert_validator.cc).
The lab will use **only self-generated credentials**. It will not fetch replay
bundles, extract private keys, modify phones, bypass DRM, or ship proprietary SDKs.

This does not prove that every sender rejects every software receiver. It means
we do not currently have an authorized authentication mechanism or an observed
stock-Google-sender success. A permissive sender such as VLC may still provide
a useful, limited direct-media path, which must be tested in its own right.

## Why a limited executable lab first

Use an existing receiver and its real mpv output instead of implementing another
speculative Cast stack. Record decoded PCM and verify non-empty, non-silent data;
reject backend fallback and decode errors. Keep raw logs/captures private and
publish only sanitized measurements. A local generated-media test can exercise
TLS → DMR LOAD → HTTP retrieval → real decoding, but must be labeled **synthetic
controller / local transport evidence**, never phone discovery, authenticated
Google app compatibility, audible playback or Sendspin E2E acceptance.

The external receiver currently has a global single-instance guard, may
advertise before its player is ready, and can silently fall back to a null
player. Those are unsuitable production contracts. Isolate its temporary
state, fail the lab on null fallback, and do not embed it in the primary HA App
or start designing a multi-device UI around it yet.

## Compatibility matrix (CastSpin evidence, not upstream claims)

| Sender / feature | Status |
| --- | --- |
| Local permissive controller → DMR → decoded PCM | Pending executable lab verification |
| Stock Android VLC discovery / audio / controls | Not tested; needs physical sender on actual LAN |
| YouTube Music / YouTube device auth and app behavior | Blocked/unverified; no Google-rooted credentials adopted |
| Spotify, DRM, screen mirroring, Google Home adoption/groups | Unsupported/unverified; no claims |
| Cast → real Sendspin device → Bluetooth A2DP | Not implemented or tested |

## Sendspin direction and ownership

The maintained [aiosendspin `756eb2d`](https://github.com/Sendspin/aiosendspin/tree/756eb2d7b84ec07de57491b1534cb5ce714f6ff0)
(Apache-2.0; current PyPI stable 10.3.0) includes an actual server under
`aiosendspin/server/`, format negotiation, groups, clocking and push streams.
Prefer that server API over a custom protocol or a client-to-client relay when
the receive gate passes. No dependency is added in this phase. Client
ownership/admission with Music Assistant must be an explicit decision and test,
not an assumption that mDNS discovery grants permission to take over a player.
