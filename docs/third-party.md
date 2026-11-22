# Third-party and license review

Date: 2026-11-22. This is a source-inspection inventory for the reuse decision,
not a complete bill of materials or legal clearance for a future image.
CastSpin's own files remain [Apache-2.0](../LICENSE).

## Material currently adopted by the P0 reuse change

Original analysis and ADR text only. No upstream implementation, patch, binary,
authentication artifact, key, certificate, media capture or runtime dependency
is copied into CastSpin by this change. Links and names identify sources; they
do not imply endorsement. The existing HA foundation and its packaged base image
remain separate from this planned receiver/Sendspin integration.

## Planned component boundaries

| Component / exact inspected source | License evidence | Required treatment before incorporation |
| --- | --- | --- |
| Cast Audio Receiver Lab `e56aa32df13168657a70ba42d97fd5821d8533cc`, Python player/backend/manager and HA material | [`LICENSING.md`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/LICENSING.md), root MPL-2.0 and file SPDX headers | Preserve MPL notices and license. Copied or modified MPL files remain MPL; identify changes and provide corresponding covered source as required. Separate original adapter files can remain Apache-2.0; importing MPL code does not relicense it. Review contribution terms before upstreaming. |
| Maintained Vibecast fork: base `83ba470158189de3bc223701decdc4c502d47644` plus reference project's `vibecast-0.8.0.dev2-current.patch` | Reference `LICENSING.md` and [`THIRD_PARTY_NOTICES.md`](https://github.com/Allcrafter1/cast-audio-receiver-lab/blob/e56aa32df13168657a70ba42d97fd5821d8533cc/THIRD_PARTY_NOTICES.md): MIT for fork and modifications | Retain actual copyright/MIT text, exact base/patch provenance and embedded notices. Do not label the whole patch or binary Apache-2.0. Verify the patch and source locks at build time. |
| Vendored `mdns-sd` and Chromium `cast_channel.proto` in frontend source | Reference scope records Apache-2.0 OR MIT and BSD-3-Clause respectively | Preserve chosen applicable license and embedded notices; neither the root MPL nor Vibecast MIT replaces these. Audit Cargo dependencies/native artifacts too. |
| `aiosendspin` stable 10.3.0, `fcc01251d4818dd31561490c0b1678603577e2f9` | [Source and LICENSE](https://github.com/Sendspin/aiosendspin/tree/fcc01251d4818dd31561490c0b1678603577e2f9), Apache-2.0 | Preserve license/notices and pin the installed artifact. Inventory server extras and transitive wheels/native libraries; top-level licensing is not the complete runtime inventory. |
| FFmpeg/PyAV and codec libraries | Exact packaged build not selected yet | Record build flags, native linkage, licenses, notices and any applicable source obligations. Do not claim that every FFmpeg/PyAV distribution has identical license coverage. Choose only needed codecs/features. |
| Existing HA base and any reused output tools | Existing foundation pins and future artifact inventory | Audit exact shipped packages. Do not include unrelated AirPlay/mpv/yt-dlp/Deno components merely because the reference image contains them. If included, retain their distinct licenses and corresponding-source obligations. |
| Third-party Cast authentication bundles / credentials | Reference `LICENSING.md` explicitly excludes them from source-license grants | Not adopted or rights-cleared. No download, import, extraction, redistribution or implicit bootstrap. Public availability is not a grant. Resolve an authorized authentication path separately; do not equate code reuse permission with credential rights. |

Historical source snapshots before the reference project's MPL transition may
have GPL-3.0-or-later terms. Do not fetch an older release and assume the current
MPL scope applies retroactively. The source revision, not just project name,
is part of the review.

## Shipped-artifact release gate

Before publishing a receiver/Sendspin App image:

- Record direct and transitive source revisions, patch hashes, binary/wheel
  hashes and build recipes for amd64 and aarch64.
- Include unmodified license/notice texts in the source and installed image;
  identify changes to third-party covered files. Preserve Apache NOTICE files
  where present and applicable.
- Make required corresponding source and modifications available in the manner
  required by each actual license. Document where recipients obtain it.
- Inventory native FFmpeg/codec and Rust dependencies, not only Python metadata.
- Check images, archives, Git history and logs for secrets and proprietary or
  copyrighted captures. Test with generated or expressly authorized audio.
- Verify that the runtime cannot automatically fetch an unreviewed auth bundle.
- Describe mixed-license image contents accurately rather than using CastSpin's
  Apache-2.0 license as a blanket assertion over the complete image.

Unresolved rights or missing artifact provenance block distribution of the
relevant material. This document does not grant permission to access user
credentials or relax the separate real-device acceptance gates.
