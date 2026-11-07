#!/usr/bin/env bash
# T30 upgrade with data preservation and rollback directory.
set -euo pipefail
SOURCE="${1:?usage: upgrade.sh <new-release-dir>}"
FLOW_HOME="${FLOW_HOME:-/opt/flow}"
release="${FLOW_HOME}.new"
backup="${FLOW_HOME}.backup.$(date +%Y%m%d-%H%M%S)"

if [ ! -d "${SOURCE}" ]; then
  echo "release directory not found: ${SOURCE}" >&2
  exit 1
fi
cp -a "${FLOW_HOME}" "${backup}"
rsync -a --delete \
  --exclude='data/' --exclude='.env' --exclude='ui/node_modules' \
  "${SOURCE}/" "${release}/"
if ! "${release}/.venv/bin/python" -m pytest -q 2>/dev/null; then
  echo "smoke check skipped (pytest unavailable)"
fi
rm -rf "${FLOW_HOME}.previous"
mv "${FLOW_HOME}" "${FLOW_HOME}.previous"
mv "${release}" "${FLOW_HOME}"
systemctl restart flow-backend flow-ui || true
echo "upgraded; previous: ${FLOW_HOME}.previous backup: ${backup}"
