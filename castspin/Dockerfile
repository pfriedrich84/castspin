ARG BUILD_FROM=ghcr.io/home-assistant/base:3.24-2026.11.0@sha256:58422480a299b16b6ea376c2167463206d430619ed02b40cd687c8bd6875519e
FROM ${BUILD_FROM}
LABEL org.opencontainers.image.source="https://github.com/pfriedrich84/castspin" \
      org.opencontainers.image.licenses="Apache-2.0"
COPY LICENSE /usr/share/licenses/castspin/LICENSE
RUN apk add --no-cache python3
WORKDIR /opt/castspin
COPY app/ /opt/castspin/
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
