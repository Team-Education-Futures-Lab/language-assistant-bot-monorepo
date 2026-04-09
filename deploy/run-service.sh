#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/deploy/services.json"
SERVICE="${1:-}"

if [[ -z "$SERVICE" ]]; then
  echo "ERROR: no service name given" >&2
  echo "Usage: $0 <service-name>" >&2
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required but not installed" >&2
  exit 1
fi

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: manifest not found at $MANIFEST" >&2
  exit 1
fi

# Look up workdir and start command — gateway is a top-level key,
# all other services live in the .services array.
if [[ "$SERVICE" == "gateway" ]]; then
  workdir="$(jq -r '.gateway.workdir // empty' "$MANIFEST")"
  start_cmd="$(jq -r '.gateway.start // empty' "$MANIFEST")"
else
  workdir="$(jq -r --arg svc "$SERVICE" '.services[] | select(.name == $svc) | .workdir // empty' "$MANIFEST")"
  start_cmd="$(jq -r --arg svc "$SERVICE" '.services[] | select(.name == $svc) | .start // empty' "$MANIFEST")"
fi

if [[ -z "$workdir" || -z "$start_cmd" ]]; then
  echo "ERROR: service '$SERVICE' not found in $MANIFEST" >&2
  exit 1
fi

target="$REPO_ROOT/$workdir"

if [[ ! -d "$target" ]]; then
  echo "ERROR: workdir '$target' does not exist" >&2
  exit 1
fi

cd "$target"
echo "Starting $SERVICE from $target: $start_cmd"
exec $start_cmd
