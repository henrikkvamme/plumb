#!/bin/sh
# The production start: the desk Python service behind the Node server, in one container. See ../Dockerfile.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
(while true; do /opt/venv/bin/python -m desk.remote || true; sleep 2; done) &
cd "$here/.."
exec node node_modules/srvx/bin/srvx.mjs serve --prod --port 3000 --entry dist/server/server.js --static ../client
