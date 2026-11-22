#!/bin/sh
set -eu
cd /opt/castspin
exec python3 -m castspin.app.runtime
