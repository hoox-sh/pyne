#!/usr/bin/env bash
# Deploy pyne (pynescript) to the namecheap VPS and keep AXIS PWA alive.
#
# Usage:
#   SSHPASS='…' ./scripts/deploy_vps.sh
#   # or with key-based ssh (no SSHPASS):
#   ./scripts/deploy_vps.sh
#
# Env overrides:
#   VPS_HOST=162.254.38.194
#   VPS_USER=root
#   VPS_PORT=22
#   VPS_PATH=/root/pynescript
#   AXIS_REPO=/path/to/axis   (default: sibling ../axis)
#
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VPS_HOST="${VPS_HOST:-162.254.38.194}"
VPS_USER="${VPS_USER:-root}"
VPS_PORT="${VPS_PORT:-22}"
VPS_PATH="${VPS_PATH:-/root/pynescript}"
AXIS_REPO="${AXIS_REPO:-$(cd "${ROOT}/../axis" 2>/dev/null && pwd || true)}"
TARGET="${VPS_USER}@${VPS_HOST}:${VPS_PATH}/"

RSYNC_SSH=(ssh -p "${VPS_PORT}" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30)
if [[ -n "${SSHPASS:-}" ]] && command -v sshpass >/dev/null 2>&1; then
  export SSHPASS
  RSYNC_E=(sshpass -e "${RSYNC_SSH[@]}" -o PreferredAuthentications=password -o PubkeyAuthentication=no)
  REMOTE() { sshpass -e "${RSYNC_SSH[@]}" -o PreferredAuthentications=password -o PubkeyAuthentication=no "${VPS_USER}@${VPS_HOST}" "$@"; }
else
  RSYNC_E=("${RSYNC_SSH[@]}")
  REMOTE() { "${RSYNC_SSH[@]}" "${VPS_USER}@${VPS_HOST}" "$@"; }
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
  "${ROOT}/" "${TARGET}"

# AXIS static server lives in the sister axis repo (not in pyne after frontend extract).
# systemd unit: ExecStart=python3 /root/pynescript/frontend/axis_pwa_server.py
if [[ -n "${AXIS_REPO}" && -f "${AXIS_REPO}/axis_pwa_server.py" ]]; then
  echo "==> restore AXIS PWA server from ${AXIS_REPO}"
  rsync -az -e "${RSYNC_E[*]}" \
    "${AXIS_REPO}/axis_pwa_server.py" \
    "${VPS_USER}@${VPS_HOST}:${VPS_PATH}/frontend/axis_pwa_server.py"
else
  echo "!! AXIS_REPO not found or missing axis_pwa_server.py — skipping (axis-pwa may stay down)" >&2
fi

echo "==> remote: pip install + restart services"
REMOTE bash -s <<EOF
set -euo pipefail
cd "${VPS_PATH}"
if [[ -x .venv/bin/pip ]]; then
  # Editable package + Pro API deps (includes numba for compile mode)
  .venv/bin/pip install -e ".[lsp,compile]" -q
  .venv/bin/pip install -r backend/requirements.txt -q
  .venv/bin/python -c "import pynescript; import numba; from pynescript.compiler.engine import has_numba; print('venv', pynescript.__file__, 'numba', numba.__version__, 'has_numba', has_numba())"
else
  echo "no .venv/bin/pip — skip install" >&2
fi
systemctl reset-failed axis-pwa.service 2>/dev/null || true
systemctl restart pynescript-api.service
systemctl restart axis-pwa.service
sleep 1
systemctl is-active pynescript-api.service axis-pwa.service
curl -s -o /dev/null -w "api=%{http_code}\n" --max-time 5 http://127.0.0.1:5002/ || true
curl -s -o /dev/null -w "axis=%{http_code}\n" --max-time 5 http://127.0.0.1:8081/ || true
EOF

echo "==> done"
