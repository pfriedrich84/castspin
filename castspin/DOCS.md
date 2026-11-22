# CastSpin — Home Assistant App (experimental)

This release is an **experimental foundation**, not yet a working Google Cast receiver or Sendspin audio server. Container build/start checks do not establish that installation under Home Assistant Supervisor works; a real Supervisor install remains an acceptance gate.

## Install

1. In Home Assistant, navigate to **Settings → Apps → App Store → ⋮ → Repositories**.
2. Add `https://github.com/pfriedrich84/castspin`.
3. Install **CastSpin**, start it, then open the web UI via Ingress.

The initial page displays service status and labels all unimplemented functions explicitly.

## Limitations and next work

Google Cast discovery, receiver authentication, app-specific playback, Sendspin transport, device selection and Bluetooth A2DP are **not implemented**. Virtual Cast devices must not be advertised before a conforming receiver exists. Validate multicast, certificates, and receiver capabilities before enabling discovery.

`/healthz` provides a simple process health check; it is not proof of audio readiness.
