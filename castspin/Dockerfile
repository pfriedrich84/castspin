ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.20
FROM ${BUILD_FROM}
RUN apk add --no-cache python3
WORKDIR /opt/castspin
COPY app/ /opt/castspin/
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
