# CastSpin — Home Assistant App (experimental)

The `0.2.0-dev1` runtime automatically mirrors Music Assistant's public audio
playback targets into the reused Cast Audio Receiver Lab frontend. It does not
create another Sendspin server or take the players away from MA.

**This is not yet a YouTube Music compatibility or audible-playback release.**
The real native frontend has been tested with mDNS, a permissive software Cast
controller, generated TLS/audio and an MA API simulator. A real MA server,
Home Assistant Supervisor and phone YouTube Music still need acceptance.

## Before enabling

You need:

1. A running Music Assistant server and an **MA access token** for a user allowed
   to read/control the selected players and queues. The official client also
   initializes providers/dashboard state. This is not a Home Assistant token.
2. This Home Assistant host's actual LAN **IPv4 address**. Do not enter
   `0.0.0.0`, an App-container address, `localhost`, or the MA server's address.
3. An **authorized, compatible Cast certificate manifest** supplied by you in
   the App configuration folder, mounted inside this App as `/config/certs.json`.
   This project has not established a rights-cleared provisioning path for such
   material. Source-code licenses do not authorize reuse of third-party device
   credentials. Without that path, real phone casting remains blocked.

CastSpin never downloads an authentication bundle, imports another receiver's
identity, or substitutes generated TLS for Google-rooted device authentication.
Do not paste private keys or access tokens into issues or chat.

## Install and configure

1. Add `https://github.com/pfriedrich84/castspin` in **Settings → Apps → App Store
   → Repositories**. Install the version containing this runtime; an older
   installed version/default branch may still contain only the foundation shell.
2. In App configuration, set:
   - `music_assistant_url`: MA's HTTP(S) base URL reachable from the App.
   - `music_assistant_token`: your MA access token (password field).
   - `network_address`: this HA host's LAN IPv4 address.
   - `player_port`: `18010` unless already used on the host.
3. Place your rights-cleared manifest into this App's own configuration directory
   as `certs.json` (for example through your existing file/SSH tooling). The
   `app_config` mapping exposes only this App's directory read-only at `/config`;
   `/data/receiver` holds writable persistent receiver state. Keep the manifest
   private, restrict file permissions, and treat backups as credential-bearing.
4. Set `enabled: true`, save, and restart the App. Do not disable HA protection
   mode or grant host audio/Bluetooth/privileged access; this route needs none.
5. Open Ingress to inspect the state and MA target list. Device selection is
   automatic; there is no second mapping form. New/removal/rename events from MA
   update the receivers. Duplicate names get a stable short suffix.

Defaults are disabled. An empty configuration does not advertise Cast devices.
The `waiting_for_certificate` state is a real blocker, not a download invitation.

## Network and security boundary

The App uses host networking for mDNS and the native frontend's dynamically
assigned Cast/Eureka ports. The phone, HA host, MA server and player must have the
required LAN connectivity. Guest isolation or blocked multicast can hide targets.

The native player/media-proxy bridge binds `network_address:player_port`, not
loopback: an MA server elsewhere must be able to fetch the cached media URL and
its preserved request context. **That upstream bridge is unauthenticated and is
for a trusted LAN only.** Do not expose any CastSpin ports to the Internet, an
untrusted Wi-Fi network, or a public reverse proxy. Restrict the bridge to the
HA host/MA server using your existing network firewall if needed. Use verified
HTTPS to MA when crossing trust boundaries; TLS verification is not disabled.

Ingress/status HTTP accepts only Supervisor's proxy (`172.30.32.2`) and local
loopback, not arbitrary LAN clients. Tokens, media URLs, metadata and raw SDK or
native error output are not included in the status response or request logs.

## Expected behavior and limitations

- Intended names: `Sauna [CastSpin]`, `Garten [CastSpin]`, etc. The reused frontend
  also has its own YouTube-video alias policy; this is not a native Google group.
- Enabled public MA players, stereo pairs and groups are mirrored. Internal,
  private, disabled and CastSpin-owned devices are excluded, including groups
  containing CastSpin devices. Offline targets stay listed but cannot play.
- A synced individual child cannot play independently until you ungroup it in
  MA. CastSpin does not silently change another device's group membership.
- A Cast LOAD **replaces the selected MA queue**. Use a dedicated test target
  first. Existing volume/mute, including zero/mute, is preserved at startup.
- MA owns decoding and the final transport. The reused bounded native cache is
  enabled to preserve progressive YouTube audio request context. Actual YouTube
  Music resolution, proxy/header/range behavior, queue progression and server
  compatibility must still be tested with your real installation. Native
  optional yt-dlp fallbacks are not shipped or claimed to work.
- A connected player bridge is not proof of phone discovery/authentication or
  sound. `/healthz` is liveness; `/api/status` is sanitized runtime state. Both
  keep `audio_verified: false`; software tests do not upgrade that evidence.
- Runtime errors withdraw the native receivers and keep diagnostic Ingress
  available. There is no automatic restart/replay of uncertain MA writes. An
  unconfirmed request can still complete remotely: inspect MA before explicitly
  restarting. A Stop checks queue-item ownership; the API provides no atomic CAS.

## First real acceptance

With a reviewed authentication path, first select one virtual target from the
actual phone's **YouTube Music Cast picker** and confirm sound on its MA-managed
speaker. Then test the other targets, existing groups, controls/track progression,
two independent routes and App restart/upgrade. Record sender, MA and firmware
versions without sharing signed URLs, keys or captured copyrighted audio.

No Spotify, DRM, universal Cast, native Google Home groups or physical Bluetooth
acceptance is claimed. See repository `docs/validation.md` for evidence levels
and `/usr/share/licenses/castspin/` in the image for sources/notices/inventories.
