# Shipped component provenance and source access

Original CastSpin files are Apache-2.0. This is a mixed-license image, not an
Apache license grant over third-party code. Python wheel notices are retained
under `sources/python-notices`, and exact source archives and installed package
inventories are available under `/usr/share/licenses/castspin/` in the image.
The Debian base/packages also retain `/usr/share/doc/*/copyright`.

## Reused Cast component

Only `/usr/local/bin/vibecast` and its required notices are copied from:

`ghcr.io/allcrafter1/cast-audio-receiver:0.8.0-dev2@sha256:c3ee8a484939512fe57a9dcb763804c5a01542243489bdc8ab396934bb93b2b8`

The index pins native amd64 and arm64 artifacts. The image's source revision is
`8be809bbef191e32ad083f2dee8c6ed3b7973a51`. Comparison with reviewed Python revision
`e56aa32df13168657a70ba42d97fd5821d8533cc` changes only README and App-installation
metadata; the native recipe, patch and Python implementation are identical.

Native source is Vibecast base `83ba470158189de3bc223701decdc4c502d47644` plus
`patches/vibecast-0.8.0.dev2-current.patch` (SHA-256
`afbb9f5086641c3e2546e5e2bb79f4cbfcc7c4dfffb7fed4b9ebc19be1916434`). The unmodified
release's complete vendored native-source archive, Cargo dependencies and build
recipe are retained in `sources/vibecast-vendored-source-0.8.0-dev2.tar.gz`.
Native notices include Vibecast MIT, Chromium BSD and mdns-sd Apache/MIT; further
component license texts are in that retained vendored source.

The MPL-2.0 Python player is installed unmodified from the reviewed, SHA-256
pinned source archive. The full corresponding archive, original licenses and
notices are retained as `sources/cast-audio-receiver-lab-e56aa32.tar.gz` and in the
installed distribution. Separate original adapters remain Apache-2.0.

## Python dependencies

`requirements.txt` locks runtime artifacts; `build-requirements.txt` locks the
source-wheel build backend. `sources.json` records exact version/URL/SHA-256 for
every selected runtime/build source distribution, including LGPL-2.1-or-later
zeroconf and mixed MPL/Apache/MIT orjson. Their corresponding source is retained
without modification. These sources and notices are not relabeled Apache-2.0.
The manifest and `installed-python.json` accompany the archives in the image.

Source archives can contain optional components that are not installed here.
No AirPlay CLI, mpv, FFmpeg, yt-dlp or Deno executable is copied from the reference
image. MA owns media decoding/delivery. Native optional resolver fallbacks that
require absent executables are not claimed to work.

## Authentication and entrypoint exclusion

The upstream image is only a build-stage component source. Its entrypoint is
never run or inherited. The App invokes CastSpin's own runtime, not
`cast-audio-bootstrap`, the upstream container manager, or any auth importer.
No operational Cast authentication bundle, captured device identity, device
private key or user state is acquired or shipped. Retained upstream source does
include public, non-production TLS/test fixtures; these are never adopted as a
receiver identity. Source-license permissions do not grant rights to separate
authentication artifacts. The operator must supply an authorized manifest in the
App configuration directory; stock-sender acceptance remains unverified.
