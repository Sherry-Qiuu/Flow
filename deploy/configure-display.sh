#!/usr/bin/env bash
# Configure the Raspberry Pi boot display for the 720x720 Flow canvas.
# Usage: sudo flow-display hdmi720|dsi|none|--remove
set -euo pipefail

MODE="${1:-hdmi720}"
CONFIG=""
for candidate in /boot/firmware/config.txt /boot/config.txt; do
  if [ -f "${candidate}" ]; then
    CONFIG="${candidate}"
    break
  fi
done
if [ -z "${CONFIG}" ]; then
  echo "flow-display: cannot find /boot/firmware/config.txt" >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "flow-display: run with sudo" >&2
  exit 1
fi

BEGIN="# >>> flow display managed >>>"
END="# <<< flow display managed <<<"
BACKUP="${CONFIG}.flow-backup.$(date +%Y%m%d-%H%M%S)"
cp -a "${CONFIG}" "${BACKUP}"

# Remove a previous managed block idempotently.
awk -v begin="${BEGIN}" -v end="${END}" '
  $0 == begin { skip = 1; next }
  $0 == end   { skip = 0; next }
  !skip       { print }
' "${CONFIG}" > "${CONFIG}.flow-new"
mv "${CONFIG}.flow-new" "${CONFIG}"

if [ "${MODE}" = "--remove" ] || [ "${MODE}" = "none" ]; then
  echo "flow-display: managed block removed; backup=${BACKUP}"
  exit 0
fi

case "${MODE}" in
  hdmi720)
    cat >> "${CONFIG}" <<'EOF'
# >>> flow display managed >>>
# T01: 720x720 HDMI canvas. Revert with: sudo flow-display none
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=720 720 60 6 0 0 0
disable_overscan=1
# <<< flow display managed <<<
EOF
    ;;
  dsi)
    cat >> "${CONFIG}" <<'EOF'
# >>> flow display managed >>>
# DSI panel: keep the panel's native mode; T05 uses a 720x720 CSS canvas.
disable_overscan=1
# <<< flow display managed <<<
EOF
    ;;
  *)
    echo "flow-display: expected hdmi720, dsi or none" >&2
    exit 2
    ;;
esac

echo "flow-display: ${MODE} written to ${CONFIG}"
echo "flow-display: reboot required; backup=${BACKUP}"
