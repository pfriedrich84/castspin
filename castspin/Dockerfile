# Reuse only the reviewed native component, never the upstream entrypoint.
ARG BUILD_FROM=ghcr.io/home-assistant/base-debian:trixie-2026.11.0@sha256:d996c8f8ef0096a1ac3756766149b31b8171afc663068cc192f2bcab20f1b8c9
FROM ghcr.io/allcrafter1/cast-audio-receiver:0.8.0-dev2@sha256:c3ee8a484939512fe57a9dcb763804c5a01542243489bdc8ab396934bb93b2b8 AS receiver
FROM ${BUILD_FROM}
LABEL org.opencontainers.image.source="https://github.com/pfriedrich84/castspin" \
      org.opencontainers.image.licenses="NOASSERTION" \
      io.castspin.project-license="Apache-2.0"
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /opt/castspin
COPY requirements.txt build-requirements.txt /opt/castspin/dependencies/
RUN python3 -m pip install --no-cache-dir --require-hashes -r dependencies/build-requirements.txt \
    && python3 -m pip install --no-cache-dir --require-hashes --no-build-isolation -r dependencies/requirements.txt \
    && python3 -m pip check
COPY --from=receiver /usr/local/bin/vibecast /usr/local/bin/vibecast
COPY --from=receiver /usr/share/doc/cast-audio-receiver/licenses/Vibecast-MIT.txt /usr/share/licenses/castspin/native/
COPY --from=receiver /usr/share/doc/cast-audio-receiver/licenses/Chromium-BSD.txt /usr/share/licenses/castspin/native/
COPY --from=receiver /usr/share/doc/cast-audio-receiver/licenses/mdns-sd-MIT.txt /usr/share/licenses/castspin/native/
COPY --from=receiver /usr/share/doc/cast-audio-receiver/licenses/mdns-sd-APACHE.txt /usr/share/licenses/castspin/native/
COPY LICENSE UPSTREAM.md /usr/share/licenses/castspin/
COPY sources.json build_sources.py /opt/castspin/build/
RUN python3 build/build_sources.py build/sources.json /usr/share/licenses/castspin/sources \
    && dpkg-query -W > /usr/share/licenses/castspin/debian-packages.txt \
    && vibecast --help > /dev/null
COPY app/ /opt/castspin/castspin/app/
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
