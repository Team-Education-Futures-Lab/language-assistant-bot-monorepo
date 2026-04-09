#!/usr/bin/env bash
# reconcile.sh — converges systemd state to match deploy/services.json
# Run as root or with sudo privileges, from anywhere in the repo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/deploy/services.json"
SYSTEMD_SRC="$REPO_ROOT/deploy/systemd"
SYSTEMD_DEST="/etc/systemd/system"

if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required but not installed" >&2
  exit 1
fi

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: manifest not found at $MANIFEST" >&2
  exit 1
fi

# ── 1. Install unit files ────────────────────────────────────────────────────
echo "==> Copying unit files to $SYSTEMD_DEST"
sudo cp "$SYSTEMD_SRC/yonder.target" "$SYSTEMD_DEST/"
sudo cp "$SYSTEMD_SRC/yonder-gateway.service" "$SYSTEMD_DEST/"
sudo cp "$SYSTEMD_SRC/yonder-service@.service" "$SYSTEMD_DEST/"

echo "==> Reloading systemd daemon"
sudo systemctl daemon-reload

# ── 2. Derive desired service set from manifest ──────────────────────────────
mapfile -t desired < <(jq -r '.services[].name' "$MANIFEST")

echo "==> Desired services: ${desired[*]:-<none>}"

# ── 3. Discover currently enabled yonder-service@* instances ────────────────
mapfile -t active_units < <(
  systemctl list-units --all --plain --no-legend 'yonder-service@*.service' 2>/dev/null \
    | awk '{print $1}' \
    | sed 's/yonder-service@\(.*\)\.service/\1/'
)
mapfile -t enabled_units < <(
  systemctl list-unit-files --plain --no-legend 'yonder-service@*.service' 2>/dev/null \
    | awk '$2 == "enabled" {print $1}' \
    | sed 's/yonder-service@\(.*\)\.service/\1/'
)

# Union of active + enabled (deduplicated)
mapfile -t current < <(printf '%s\n' "${active_units[@]:-}" "${enabled_units[@]:-}" | sort -u | grep -v '^$' || true)

echo "==> Currently tracked services: ${current[*]:-<none>}"

# ── 4. Disable + stop services removed from manifest ────────────────────────
for svc in "${current[@]:-}"; do
  [[ -z "$svc" ]] && continue
  if ! printf '%s\n' "${desired[@]:-}" | grep -qx "$svc"; then
    echo "==> Removing stale service: $svc"
    sudo systemctl stop "yonder-service@${svc}.service" 2>/dev/null || true
    sudo systemctl disable "yonder-service@${svc}.service" 2>/dev/null || true
  fi
done

# ── 5. Enable + start services added to manifest ────────────────────────────
for svc in "${desired[@]:-}"; do
  [[ -z "$svc" ]] && continue
  unit="yonder-service@${svc}.service"

  if ! printf '%s\n' "${current[@]:-}" | grep -qx "$svc"; then
    echo "==> Enabling new service: $svc"
    sudo systemctl enable "$unit"
    sudo systemctl start "$unit"
  else
    echo "==> Reloading existing service: $svc"
    sudo systemctl restart "$unit"
  fi
done

# ── 6. Ensure gateway and target are enabled + running ──────────────────────
echo "==> Ensuring yonder-gateway.service is enabled and running"
sudo systemctl enable yonder-gateway.service
sudo systemctl restart yonder-gateway.service

echo "==> Ensuring yonder.target is enabled"
sudo systemctl enable yonder.target

echo ""
echo "==> Reconcile complete. Current status:"
sudo systemctl status --no-pager yonder.target yonder-gateway.service \
  $(printf 'yonder-service@%s.service ' "${desired[@]:-}") 2>/dev/null || true
