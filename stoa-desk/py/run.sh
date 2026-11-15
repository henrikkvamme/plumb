#!/bin/sh
# Start the Python service that runs the bp agent for the desk. It listens on 127.0.0.1:${DESK_PY_PORT:-4722}.
# The model keys come from the environment. The service uses the Python environment of ../stoa.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
if [ -f "$here/.env" ]; then
  set -a
  . "$here/.env"
  set +a
fi
# More than one model service, so a service with no credit does not stop the desk (py/desk/providers.py).
export HOSTINGER_ROUTER_BASE_URL="${AI_ROUTER_BASE_URL:-}" HOSTINGER_ROUTER_API_KEY="${AI_ROUTER_API_KEY:-}"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" VERDA_INFERENCE_API_KEY="${VERDA_INFERENCE_API_KEY:-}"
if [ -n "$OPENROUTER_API_KEY" ]; then
  export AI_ROUTER_BASE_URL="https://openrouter.ai/api/v1" AI_ROUTER_API_KEY="$OPENROUTER_API_KEY"
fi
export PYTHONPATH="$here"
exec uv run --project "$repo/stoa" --with starlette --with uvicorn python -m desk.service
