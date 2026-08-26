#!/usr/bin/env bash
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

# Deploy pyne (pynescript) Pro API to the Hetzner VPS (pynescript.online).
# AXIS PWA is served from Cloudflare Pages (axis.hoox.sh) — skip dist by default.
#
# Usage:
#   ./scripts/deploy_vps.sh
#   # password auth (optional override):
#   SSHPASS='…' ./scripts/deploy_vps.sh
#
# Defaults to key auth with ~/.ssh/id_ed25519 (matches Host "pynescript" in
# ~/.ssh/config). Prefer identity file when connecting by IP so HostName
# matching is not required.
#
# Env overrides:
#   VPS_HOST=pynescript       # or 204.168.138.51
#   VPS_USER=root
#   VPS_PORT=22
#   VPS_PATH=/root/pynescript
#   VPS_IDENTITY_FILE=~/.ssh/id_ed25519
#   AXIS_REPO=/path/to/axis   (default: sibling ../axis)
#   AXIS_BUILD=1              # run `bun run build` in AXIS_REPO before rsync
#   AXIS_SKIP_DIST=1          # skip rsync of axis dist/ (default on this host)
#
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VPS_HOST="${VPS_HOST:-pynescript}"
VPS_USER="${VPS_USER:-root}"
VPS_PORT="${VPS_PORT:-22}"
VPS_PATH="${VPS_PATH:-/root/pynescript}"
AXIS_REPO="${AXIS_REPO:-$(cd "${ROOT}/../axis" 2>/dev/null && pwd || true)}"
TARGET="${VPS_USER}@${VPS_HOST}:${VPS_PATH}/"

# Expand ~ in identity path; default ed25519 key used for namecheap VPS.
_default_id="${HOME}/.ssh/id_ed25519"
VPS_IDENTITY_FILE="${VPS_IDENTITY_FILE:-$_default_id}"
if [[ "${VPS_IDENTITY_FILE}" == ~* ]]; then
  VPS_IDENTITY_FILE="${VPS_IDENTITY_FILE/#\~/${HOME}}"
fi

RSYNC_SSH=(
  ssh
  -p "${VPS_PORT}"
  -o StrictHostKeyChecking=accept-new
  -o ConnectTimeout=30
)

# Prefer key auth unless SSHPASS is explicitly set.
if [[ -n "${SSHPASS:-}" ]] && command -v sshpass >/dev/null 2>&1; then
  export SSHPASS
  RSYNC_SSH+=(
    -o PreferredAuthentications=password
    -o PubkeyAuthentication=no
  )
  RSYNC_E=(sshpass -e "${RSYNC_SSH[@]}")
  REMOTE() {
    sshpass -e "${RSYNC_SSH[@]}" "${VPS_USER}@${VPS_HOST}" "$@"
  }
  echo "==> auth: SSHPASS (password)"
elif [[ -f "${VPS_IDENTITY_FILE}" ]]; then
  RSYNC_SSH+=(
    -i "${VPS_IDENTITY_FILE}"
    -o IdentitiesOnly=yes
    -o PreferredAuthentications=publickey
    -o PubkeyAuthentication=yes
  )
  RSYNC_E=("${RSYNC_SSH[@]}")
  REMOTE() {
    "${RSYNC_SSH[@]}" "${VPS_USER}@${VPS_HOST}" "$@"
  }
  echo "==> auth: key ${VPS_IDENTITY_FILE}"
else
  # Fall back to ssh agent / config Host entries (e.g. Host namecheap).
  RSYNC_E=("${RSYNC_SSH[@]}")
  REMOTE() {
    "${RSYNC_SSH[@]}" "${VPS_USER}@${VPS_HOST}" "$@"
  }
  echo "==> auth: default ssh (no ${VPS_IDENTITY_FILE}; using agent/config)"
fi

echo "==> rsync ${ROOT}/ → ${TARGET}"
rsync -az --delete --info=stats1 \
  -e "${RSYNC_E[*]}" \
  --exclude '.cache/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude 'node_modules/' \
  --exclude '**/node_modules/' \
  --exclude '.mypy_cache/' \
  --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' \
  --exclude 'dist/' \
  --exclude 'build/' \
  --exclude '.coverage' \
  --exclude 'coverage.lcov' \
  --exclude 'tests/data/set0*/' \
  --exclude 'tests/data/library/' \
  --exclude '.opencode/' \
  --exclude 'logs/' \
  --exclude 'vscode-extension/*.vsix' \
  "${ROOT}/" "${TARGET}"

# AXIS static server lives in the sister axis repo (not in pyne after frontend extract).
# Hetzner origin is API-only (PWA on CF Pages). Opt in with AXIS_SKIP_DIST=0.
AXIS_SKIP_DIST="${AXIS_SKIP_DIST:-1}"
if [[ "${AXIS_SKIP_DIST}" != "1" && -n "${AXIS_REPO}" && -f "${AXIS_REPO}/axis_pwa_server.py" ]]; then
  echo "==> restore AXIS PWA server from ${AXIS_REPO}"
  rsync -az -e "${RSYNC_E[*]}" \
    "${AXIS_REPO}/axis_pwa_server.py" \
    "${VPS_USER}@${VPS_HOST}:${VPS_PATH}/frontend/axis_pwa_server.py"

  if [[ "${AXIS_SKIP_DIST:-0}" != "1" ]]; then
    if [[ "${AXIS_BUILD:-0}" == "1" ]]; then
      if command -v bun >/dev/null 2>&1; then
        echo "==> AXIS_BUILD=1 → bun run build in ${AXIS_REPO}"
        (cd "${AXIS_REPO}" && bun run build)
      else
        echo "!! bun not found — cannot AXIS_BUILD" >&2
        exit 1
      fi
    fi
    if [[ -d "${AXIS_REPO}/dist" && -f "${AXIS_REPO}/dist/index.html" ]]; then
      echo "==> rsync AXIS dist → ${VPS_PATH}/frontend/dist/"
      rsync -az --delete --info=stats1 \
        -e "${RSYNC_E[*]}" \
        "${AXIS_REPO}/dist/" \
        "${VPS_USER}@${VPS_HOST}:${VPS_PATH}/frontend/dist/"
    else
      echo "!! no ${AXIS_REPO}/dist/index.html — skip AXIS dist (run: cd axis && bun run build)" >&2
    fi
  fi
else
  echo "==> skip AXIS PWA rsync (API-only host; set AXIS_SKIP_DIST=0 to ship dist)"
fi

echo "==> remote: pip install + restart services"
REMOTE bash -s <<EOF
set -euo pipefail
cd "${VPS_PATH}"
if [[ -x .venv/bin/pip ]]; then
  # Editable package + Pro API deps (includes numba for compile mode)
  .venv/bin/pip install -e ".[lsp,compile,datafeed]" -q
  .venv/bin/pip install -r backend/requirements.txt -q
  .venv/bin/python -c "import pynescript; import numba; from pynescript.compiler.engine import has_numba; print('venv', pynescript.__file__, 'numba', numba.__version__, 'has_numba', has_numba())"
  .venv/bin/python -c "import ccxt; print('ccxt', ccxt.__version__, 'exchanges', len(ccxt.exchanges))"
else
  echo "no .venv/bin/pip — skip install" >&2
fi
systemctl reset-failed axis-pwa.service 2>/dev/null || true
systemctl restart pynescript-api.service
# AXIS PWA is on CF Pages; axis-pwa.service is optional on this host.
if systemctl list-unit-files axis-pwa.service >/dev/null 2>&1; then
  systemctl restart axis-pwa.service || true
fi
sleep 1
systemctl is-active pynescript-api.service
curl -s -o /dev/null -w "api=%{http_code}\n" --max-time 5 http://127.0.0.1:5002/health || true
curl -s -o /dev/null -w "nginx=%{http_code}\n" --max-time 5 -k https://127.0.0.1/health || true
EOF

echo "==> done"
